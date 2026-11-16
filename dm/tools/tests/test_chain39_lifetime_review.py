"""Pinned proposal review gates, not native Metal validation or runtime patches.

Fetch the three reviewed branches before running in a shallow checkout. Missing
review objects cause explicit skips; no test downloads data or mutates a checkout.
"""
from pathlib import Path
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
HOST = 'dm/gfx/nvn/nvn_mtl.m'
PR5 = '6cfb79edb0127027323df9ec7e53fd5e57e4d9c6'
PR6 = '3c2198152292f64cbedf06701c84b6381d4e8285'
PR9 = '863e2ab1d2915b5ba36a47ebe237403b2c41cc22'


def source(case, revision, path=HOST):
    result = subprocess.run(['git', 'show', f'{revision}:{path}'], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode:
        case.skipTest(f'pinned review source unavailable; fetch revision {revision}')
    return result.stdout


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index('\n}', start) + 2]


def normalized(text):
    text = re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'\s+', '', text)


class UploadOwnershipReview(unittest.TestCase):
    def test_ci_fetch_pins_cover_all_review_inputs(self):
        workflow = (ROOT / '.github/workflows/tests.yml').read_text()
        baseline = '04811a634b7f9344e882129b0973dd493369dd62'
        for job in ('coverage', 'tool-tests'):
            with self.subTest(job=job):
                block = re.search(r'^  ' + job + r':\n(.*?)(?=^  [\w-]+:|\Z)', workflow, re.S | re.M)
                self.assertIsNotNone(block)
                assert block is not None
                self.assertIn('git fetch --no-tags --depth=1 origin', block.group(1))
                for revision in (baseline, PR5, PR6, PR9):
                    self.assertIn(revision, block.group(1))

    def test_pr5_diff_is_limited_to_release_after_identical_protocol(self):
        base, proposal = source(self, '04811a63'), source(self, PR5)
        for signature in ('static void up_begin(void) {', 'static void up_flush(void) {'):
            with self.subTest(function=signature):
                self.assertEqual(normalized(function(base, signature)), normalized(function(proposal, signature)))
        signature = 'static id<MTLBuffer> up_alloc(size_t n, size_t *off) {'
        old, new = normalized(function(base, signature)), normalized(function(proposal, signature))
        self.assertEqual(old.count('defer_obj_release(*sb);'), 1)
        self.assertEqual(old.replace('defer_obj_release(*sb);', 'res_remove(*sb);'), new)

    def test_slot_reuse_waits_after_publication_and_completion_cleanup(self):
        text = source(self, PR5)
        begin = function(text, 'static void up_begin(void) {')
        self.assertLess(begin.index('rec_publish();'), begin.index('up_wait_zero('))
        self.assertLess(begin.index('up_wait_zero('), begin.index('atomic_store(&g_up_alloc_busy[slot], 1)'))
        self.assertLess(begin.index('up_wait_zero('), begin.index('[g_up_alloc4[slot] reset]'))
        flush = function(text, 'static void up_flush(void) {')
        handler = flush[flush.index('[o addFeedbackHandler:'):]
        self.assertLess(handler.index('res_remove(obj)'), handler.index('atomic_store(&g_up_alloc_busy[slot], 0)'))
        self.assertLess(handler.index('[staging removeAllObjects]'), handler.index('atomic_store(&g_up_alloc_busy[slot], 0)'))
        self.assertIn('if (g_up_block && !up_retained(g_up_block, slot))', flush)
        alloc = function(text, 'static id<MTLBuffer> up_alloc(size_t n, size_t *off) {')
        self.assertIn('if (!g_up_block && need <= UP_BLOCK_SIZE)', alloc)


class PatternAndHeapReview(unittest.TestCase):
    @unittest.expectedFailure
    def test_pr6_previous_pattern_has_deferred_retirement(self):
        # Known failed acceptance gate: registering a replacement does not retire
        # the old resident allocation. Do not count this as a fixed lifetime bug.
        text = source(self, PR6)
        fill = function(text, 'void mtl_sub_fill(uint64_t dst, uint64_t n, uint32_t value) {')
        replace = fill[fill.index('    enum { PAT = '):fill.index('    for (uint64_t off = ')]
        self.assertIn('res_add(pat)', replace)
        self.assertRegex(replace, r'defer_obj_(?:release|at)\(pat\b')

    def test_chain39_image_heap_ownership_is_not_pr9_recycle_ownership(self):
        base, proposal = source(self, '04811a63'), source(self, PR9)
        start = base.index('@implementation NvImageHeap')
        old = base[start:base.index('@end', start)]
        start = proposal.index('@implementation NvImageHeap')
        new = proposal[start:proposal.index('@end', start)]
        self.assertIn('res_remove(heap)', old)
        self.assertNotIn('rh_wait(heap)', old)
        self.assertIn('rh_wait(heap)', new)

    def test_pr9_eviction_matches_reference_for_all_small_timestamp_orders(self):
        header = source(self, PR9, 'dm/gfx/nvn/nvn_heap_cache.h')
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "policy.h"
int main(void) {
    for (unsigned n = 0; n <= 6; n++) {
        unsigned orders = 1;
        for (unsigned i = 0; i < n; i++) orders *= 3;
        for (unsigned code = 0; code < orders; code++) {
            rh_ent initial[6] = {0}; uint64_t total = 0; unsigned digits = code;
            for (unsigned i = 0; i < n; i++) {
                initial[i] = (rh_ent){(void *)(uintptr_t)(i + 1), 1 + i % 3, digits % 3};
                digits /= 3; total += initial[i].size;
            }
            for (unsigned room = 0; room <= 2; room++) {
                uint64_t cap = total + room;
                for (uint64_t incoming = 0; incoming <= cap + 1; incoming++)
                for (unsigned limit = 0; limit <= n; limit++) {
                    uint64_t left = total; unsigned chosen = 0, mask = 0;
                    int expected = incoming <= cap;
                    if (expected) {
                        while (left > cap - incoming && chosen < limit) {
                            unsigned best = n;
                            for (unsigned i = 0; i < n; i++)
                                if (!(mask & (1u << i)) && (best == n || initial[i].t < initial[best].t)) best = i;
                            assert(best < n);
                            mask |= 1u << best; chosen++; left -= initial[best].size;
                        }
                        expected = left <= cap - incoming;
                    }
                    rh_ent entries[6], drop[6]; memcpy(entries, initial, sizeof entries);
                    unsigned count = n, nd = 99; uint64_t bytes = total;
                    int actual = rh_cache_room(entries, &count, &bytes, incoming, cap, drop, &nd, limit);
                    assert(actual == expected);
                    if (!actual) {
                        assert(nd == 0 && count == n && bytes == total);
                        assert(!memcmp(entries, initial, sizeof entries));
                    } else {
                        assert(nd == chosen && count + nd == n && bytes == left);
                        unsigned dropped = 0, retained = 0;
                        for (unsigned i = 0; i < nd; i++) {
                            unsigned bit = 1u << ((uintptr_t)drop[i].heap - 1);
                            assert(!(dropped & bit)); dropped |= bit;
                        }
                        for (unsigned i = 0; i < count; i++) {
                            unsigned bit = 1u << ((uintptr_t)entries[i].heap - 1);
                            assert(!(retained & bit)); retained |= bit;
                        }
                        assert(dropped == mask && !(retained & dropped));
                        assert((retained | dropped) == (1u << n) - 1);
                    }
                }
            }
        }
    }
    return 0;
}
'''
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('clang') or 'cc']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'policy.h').write_text(header)
            (root / 'test.c').write_text(code)
            subprocess.run(compiler + ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                                      str(root / 'test.c'), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
