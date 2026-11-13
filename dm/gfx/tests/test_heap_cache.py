"""Run the production idle-cache metadata and process-level timeout checks portably."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from dm.gfx.tests.check_gpu_timeout import check_timeout

HERE = Path(__file__).resolve().parent
CC = shutil.which('cc') or shutil.which('clang') or 'cc'


@unittest.skipUnless(shutil.which(CC), 'C compiler required')
class HeapCache(unittest.TestCase):
    def test_production_policy_and_concurrent_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = str(Path(tmp) / 'heap_cache')
            subprocess.run([CC, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread',
                            str(HERE / 't_heap_cache.c'), '-o', binary], check=True, capture_output=True)
            result = subprocess.run([binary], check=True, capture_output=True, text=True, timeout=15)
            self.assertIn('0 failed', result.stdout)

    def test_rejection_only_negative_control_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'nvn').mkdir()
            (root / 'tests').mkdir()
            header = (HERE.parent / 'nvn/nvn_heap_cache.h').read_text()
            signature = header[header.index('static inline int rh_cache_room'):header.index('    *ndrop = 0;')]
            old = header[:header.index('static inline int rh_cache_room')] + signature
            old += ('    (void)entries; (void)count; (void)drop; (void)limit;\n'
                    '    *ndrop = 0; return size <= cap && *bytes <= cap - size;\n}\n#endif\n')
            (root / 'nvn/nvn_heap_cache.h').write_text(old)
            source = root / 'tests/t_heap_cache.c'
            source.write_text((HERE / 't_heap_cache.c').read_text())
            binary = str(root / 'negative')
            subprocess.run([CC, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread',
                            str(source), '-o', binary], check=True, capture_output=True)
            result = subprocess.run([binary], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertIn('allocated == 1 && taken == 59', result.stderr)

    def test_timeout_exit_skips_unbounded_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'timeout.c'
            source.write_text('#include "gpu_test_timeout.h"\n'
                              'static void cleanup(void) { for (;;) {} }\n'
                              'int main(void) { atexit(cleanup); gpu_test_timeout(); }\n')
            binary = str(Path(tmp) / 'timeout')
            subprocess.run([CC, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(HERE),
                            str(source), '-o', binary], check=True, capture_output=True)
            check_timeout(binary)
