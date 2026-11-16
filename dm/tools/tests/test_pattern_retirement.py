"""Execute production pattern replacement and retirement fence with a C model.

No Metal allocations/compilation: the native t_copy_alias case checks the driver.
"""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class PatternRetirement(unittest.TestCase):
    def test_production_replacement_survives_delayed_completion(self):
        text = (ROOT / 'dm/gfx/nvn/nvn_mtl.m').read_text()
        fill = text[text.index('void mtl_sub_fill('):]
        body = fill[fill.index('    enum { PAT = '):fill.index('    for (uint64_t off = ')]
        body = body.replace('__strong ', '').replace('id<MTLBuffer>', 'struct pattern *')
        body = body.replace('[g_dev newBufferWithLength:PAT options:MTLResourceStorageModeShared]', 'new_pattern(PAT)')
        body = body.replace('next.contents', 'next->contents')
        signature = 'static void defer_obj_release(id obj) {'
        start = text.index(signature)
        retirement = text[start:text.index('\n', start)].replace('id obj', 'struct pattern *obj')
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
struct pattern { uint32_t *contents; int resident; };
static struct pattern *made[16], *queued[16];
static uint64_t fences[16], g_fence = 10, done = 10;
static unsigned nm, nq, released, fail_new;
static jmp_buf failed_allocation;
static struct pattern *new_pattern(size_t size) {
    if (fail_new) return NULL;
    struct pattern *p = calloc(1, sizeof *p); assert(p);
    p->contents = calloc(1, size); assert(p->contents); made[nm++] = p; return p;
}
static void res_add(struct pattern *p) { assert(p && !p->resident); p->resident = 1; }
static void defer_obj_at(struct pattern *p, int keep_resident, uint64_t fence) {
    if (!p) return;
    assert(!keep_resident && p->resident && fence > done);
    queued[nq] = p; fences[nq++] = fence;
}
''' + retirement + r'''
#define MDIE(...) longjmp(failed_allocation, 1)
static struct pattern *initialize(uint32_t value) {
''' + body + r'''
    return pat;
}
static void complete(uint64_t fence) {
    done = fence;
    for (unsigned i = 0; i < nq; i++) if (queued[i] && fences[i] <= done) {
        assert(queued[i]->resident); queued[i]->resident = 0;
        free(queued[i]->contents); queued[i]->contents = NULL;
        queued[i] = NULL; released++;
    }
}
static void bytes(struct pattern *p, uint32_t value) {
    assert(p && p->resident && p->contents);
    for (unsigned k = 0; k < 0x10000 / 4; k++) assert(p->contents[k] == value);
}
int main(void) {
    struct pattern *a = initialize(0x78563412), *b = initialize(0x01234567);
    assert(nm == 2 && nq == 1 && fences[0] == 11);
    assert(initialize(0x01234567) == b && nm == 2 && nq == 1);
    bytes(a, 0x78563412); bytes(b, 0x01234567);
    fail_new = 1;
    if (!setjmp(failed_allocation)) { initialize(0xdeadbeef); return 8; }
    fail_new = 0;
    assert(nm == 2 && nq == 1); // failure did not retire or replace current b
    assert(initialize(0x01234567) == b);
    struct pattern *c = initialize(0xdeadbeef);
    assert(nm == 3 && nq == 2);
    complete(10); assert(released == 0);
    bytes(a, 0x78563412); bytes(b, 0x01234567); bytes(c, 0xdeadbeef);
    complete(11); assert(released == 2 && !a->resident && !b->resident);
    bytes(c, 0xdeadbeef);
    g_fence = 11;
    struct pattern *d = initialize(0x11112222);
    assert(fences[2] == 12); complete(11); bytes(c, 0xdeadbeef);
    complete(12); assert(released == 3 && !c->resident); bytes(d, 0x11112222);
    for (unsigned i = 0; i < nm; i++) { free(made[i]->contents); free(made[i]); }
    return 0;
}
'''
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('clang') or 'cc']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, code in (('production', program), ('no_retirement', program.replace('        defer_obj_release(pat);', '        (void)pat;'))):
                path = root / (name + '.c')
                path.write_text(code)
                subprocess.run(compiler + ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                          '-Wno-unused-function', str(path), '-o', str(root / name)], check=True)
                # Prevent a known-failing control from writing a core dump.
                import resource
                def no_core():
                    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                result = subprocess.run([str(root / name)], capture_output=True, timeout=5, preexec_fn=no_core)
                if name == 'production':
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('nq == 1', result.stderr.decode())


if __name__ == '__main__':
    unittest.main()
