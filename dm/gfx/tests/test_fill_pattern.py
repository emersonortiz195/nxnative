"""Exercise production fill-pattern initialization without a Metal device.

Only the Metal allocation/property syntax is substituted. The actual pattern
cache condition and CPU initialization execute with separately owned buffers;
real GPU ordering/residency is covered by t_copy_alias on Apple Silicon.
"""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest


class FillPattern(unittest.TestCase):
    def test_no_temporary_copy_and_old_sources_remain_immutable(self):
        source = (Path(__file__).resolve().parents[1] / 'nvn/nvn_mtl.m').read_text()
        function = source[source.index('void mtl_sub_fill('):]
        body = function[function.index('    enum { PAT = '):function.index('    for (uint64_t off = ')]
        body = body.replace('__strong id<MTLBuffer>', 'struct pattern *')
        body = body.replace('[g_dev newBufferWithLength:PAT options:MTLResourceStorageModeShared]', 'new_pattern(PAT)')
        body = body.replace('[g_dev newBufferWithBytes:tmp length:PAT options:MTLResourceStorageModeShared]', 'copy_pattern(tmp, PAT)')
        body = body.replace('pat.contents', 'pat->contents')
        program = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
struct pattern { uint32_t *contents; };
static unsigned made, registered, temporary;
static int fail_allocation;
static struct pattern *new_pattern(size_t n) {
    if (fail_allocation) return NULL;
    struct pattern *p = calloc(1, sizeof *p); assert(p);
    p->contents = calloc(1, n); assert(p->contents); made++; return p;
}
static struct pattern *copy_pattern(const void *bytes, size_t n) {
    struct pattern *p = new_pattern(n); memcpy(p->contents, bytes, n); return p;
}
static void *temporary_alloc(size_t n) { temporary++; return malloc(n); }
static void res_add(struct pattern *p) { assert(p); registered++; }
#define MDIE(...) exit(89)
#define malloc temporary_alloc
static struct pattern *initialize(uint32_t value) {
''' + body + r'''
    return pat;
}
int main(int argc, char **argv) {
    (void)argv;
    if (argc > 1) { fail_allocation = 1; initialize(0x78563412u); return 1; }
    const uint32_t values[] = {0x78563412u, 0x01234567u, 0x01234567u, 0xdeadbeefu};
    struct pattern *buffers[4];
    for (unsigned i = 0; i < 4; i++) buffers[i] = initialize(values[i]);
    assert(made == 3 && registered == 3); // repeated value keeps the pattern
    assert(temporary == 0); // old implementation allocated a second 64 KiB
    assert(buffers[0] != buffers[1] && buffers[1] == buffers[2] && buffers[2] != buffers[3]);
    for (unsigned i = 0; i < 4; i++)
        for (unsigned k = 0; k < 0x10000 / 4; k++) assert(buffers[i]->contents[k] == values[i]);
    for (unsigned i = 0; i < 4; i++) if (i != 2) { free(buffers[i]->contents); free(buffers[i]); }
    return 0;
}
'''
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('clang') or 'cc']
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'pattern.c').write_text(program)
            subprocess.run(compiler + ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                      '-Wno-unused-function', str(root / 'pattern.c'),
                                      '-o', str(root / 'pattern')], check=True)
            subprocess.run([str(root / 'pattern')], check=True, timeout=5)
            # Distinguish the explicit allocation-failure guard from a null
            # contents access (which would fault rather than exit with 89).
            result = subprocess.run([str(root / 'pattern'), '--fail-allocation'], timeout=5)
            self.assertEqual(result.returncode, 89)


if __name__ == '__main__':
    unittest.main()
