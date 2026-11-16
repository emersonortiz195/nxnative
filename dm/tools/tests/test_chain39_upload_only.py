"""Execute the production first-block branch with synthetic buffer ownership.

No ARC/driver/GPU simulation is claimed. Native delayed completion is exercised
by t_upload_slots on Mac; source gates pin the unmodified completion protocol.
"""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

from dm.tools.tests.test_chain39_lifetime_review import HOST, PR5, function, normalized, source

ROOT = Path(__file__).resolve().parents[3]


class UploadOnly(unittest.TestCase):
    def body(self):
        text = (ROOT / HOST).read_text()
        alloc = function(text, 'static id<MTLBuffer> up_alloc(size_t n, size_t *off) {')
        body = alloc[alloc.index('    if (!g_up_block && need <= UP_BLOCK_SIZE)'):
                     alloc.index('    if (!g_up_block || g_up_block_off + need > g_up_block_size)')]
        return (body.replace('__strong id<MTLBuffer> *', 'struct buffer **')
                .replace('(*sb).length', '(*sb)->length')
                .replace('[g_dev newBufferWithLength:want options:MTLResourceStorageModePrivate]', 'new_buffer(want)'))

    def run_model(self, body, failure=False):
        program = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
struct buffer { size_t length; int resident, completed; };
static int failures, made, removed, deferred, fail_new;
static struct buffer objects[32], *expected_old;
#define CHECK(c) do { if (!(c)) { failures++; fprintf(stderr, "FAIL %s\n", #c); } } while (0)
#define MAX(a,b) ((a) > (b) ? (a) : (b))
#define UP_BLOCK_SIZE (32u << 20)
#define UP_SLOT_BLOCK (4u << 20)
#define nil NULL
#define MDIE(...) exit(89)
static struct buffer *g_up_slot_blk[3], *g_up_block;
static unsigned g_up_cur_slot;
static size_t g_up_slot_want[3], g_up_block_size, g_up_block_off, g_up_staging_bytes;
static uint64_t g_up_blocks_new;
static int reuse = 1;
static int up_reuse(void) { return reuse; }
static struct buffer *new_buffer(size_t n) {
    CHECK(!expected_old || !expected_old->resident);
    if (fail_new) return NULL;
    CHECK(made < 32);
    struct buffer *b = &objects[made++]; b->length = n; return b;
}
static void res_add(struct buffer *b) { CHECK(b && !b->resident); b->resident = 1; }
static void res_remove(struct buffer *b) { CHECK(b->completed && b->resident); b->resident = 0; removed++; }
static void defer_obj_release(struct buffer *b) { (void)b; deferred++; }
static void first_block(size_t need) {
''' + body + r'''
}
static void next_batch(void) { g_up_block = NULL; g_up_staging_bytes = 0; expected_old = NULL; }
int main(int argc, char **argv) {
    (void)argv;
    static struct buffer old0 = {UP_SLOT_BLOCK, 1, 1}; g_up_slot_blk[0] = &old0;
    expected_old = &old0;
    if (argc > 1) { fail_new = 1; first_block(8u << 20); return 7; }
    first_block(8u << 20);
    CHECK(removed == 1 && deferred == 0 && !old0.resident);
    CHECK(made == 1 && g_up_blocks_new == 1 && g_up_block == g_up_slot_blk[0]);
    CHECK(g_up_block_size == (8u << 20) && g_up_block_off == 0 && g_up_staging_bytes == (8u << 20));
    next_batch(); first_block(4u << 20); // no growth: keep the primary
    CHECK(made == 1 && removed == 1 && g_up_slot_blk[0]->resident);
    first_block(16u << 20); // a current block excludes this release branch
    CHECK(made == 1 && removed == 1);
    next_batch(); first_block(UP_BLOCK_SIZE + 256); // oversized uploads bypass primary growth
    CHECK(made == 1 && removed == 1 && !g_up_block);
    static struct buffer old1 = {UP_SLOT_BLOCK, 1, 1}; g_up_cur_slot = 1; g_up_slot_blk[1] = &old1;
    expected_old = &old1; first_block(8u << 20);
    CHECK(removed == 2 && g_up_slot_blk[0]->resident); // another in-flight slot is untouched
    next_batch(); reuse = 0; g_up_slot_want[1] = UP_BLOCK_SIZE;
    first_block(1u << 20); // non-reuse mode ignores earlier demand, no unnecessary growth
    CHECK(made == 2 && removed == 2);
    next_batch(); reuse = 1; g_up_slot_blk[1]->completed = 1; expected_old = g_up_slot_blk[1];
    first_block(1u << 20);
    CHECK(made == 3 && removed == 3 && g_up_slot_blk[1]->length == UP_BLOCK_SIZE);
    CHECK(g_up_slot_blk[0]->resident && deferred == 0);
    return failures ? 1 : 0;
}
'''
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('clang') or 'cc']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'test.c').write_text(program)
            subprocess.run(compiler + ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                      '-Wno-unused-function', str(root / 'test.c'),
                                      '-o', str(root / 'test')], check=True)
            return subprocess.run([str(root / 'test')] + (['--fail'] if failure else []),
                                  capture_output=True, text=True, timeout=5)

    def test_growth_release_precedes_replacement_and_preserves_other_paths(self):
        result = self.run_model(self.body())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_deferred_release_is_a_failing_negative_control(self):
        body = self.body()
        self.assertEqual(body.count('res_remove(*sb);'), 1)
        result = self.run_model(body.replace('res_remove(*sb);', 'defer_obj_release(*sb);'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('!expected_old || !expected_old->resident', result.stderr)

    def test_allocation_failure_uses_existing_fatal_guard(self):
        self.assertEqual(self.run_model(self.body(), failure=True).returncode, 89)

    def test_current_upload_protocol_matches_reviewed_proposal(self):
        current, reviewed = (ROOT / HOST).read_text(), source(self, PR5)
        for signature in ('static void up_begin(void) {', 'static void up_flush(void) {',
                          'static id<MTLBuffer> up_alloc(size_t n, size_t *off) {'):
            with self.subTest(function=signature):
                self.assertEqual(normalized(function(current, signature)), normalized(function(reviewed, signature)))


if __name__ == '__main__':
    unittest.main()
