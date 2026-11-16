"""Same-MSL build requests share a compile, without serializing other inputs.

The compiler writes synthetic bytes; no Xcode, game files or existing archive is
opened. A barrier makes all workers observe the initial cache miss, so this
reproduces the check/compile race without scheduler sleeps.
"""
import concurrent.futures as cf
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'dm/gfx/tools'))
import dmsh_mtlcache  # noqa: E402
import shader_cache  # noqa: E402


class ConcurrentMetalCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []
        self.call_lock = threading.Lock()

        def compile_source(msl, air, lib):
            with self.call_lock:
                self.calls.append(Path(msl).read_bytes())
            Path(lib).write_bytes(b'compiled:' + Path(msl).read_bytes())

        self.store = shader_cache.Store(self.root / 'cache.db')
        self.addCleanup(self.store.db.close)
        with mock.patch.object(dmsh_mtlcache, 'compiler_id', return_value='compiler/sdk'):
            self.cache = dmsh_mtlcache.Cache(
                self.store, {'mac': ('macosx', 'flags', compile_source)}, str(self.root))

    def source(self, name, contents):
        path = self.root / name
        path.write_bytes(contents)
        return str(path)

    def parallel_misses(self, method, request, workers=8):
        original = getattr(self.store, method)
        first = threading.local()
        missed = threading.Barrier(workers)

        def initial_miss(*args):
            result = original(*args)
            if not getattr(first, 'seen', False):
                first.seen = True
                self.assertFalse(result)
                missed.wait(timeout=10)
            return result

        with mock.patch.object(self.store, method, side_effect=initial_miss):
            with cf.ThreadPoolExecutor(workers) as pool:
                futures = [pool.submit(request, i) for i in range(workers)]
                return [future.result(timeout=15) for future in futures]

    def test_same_source_misses_compile_once(self):
        sources = [self.source(f'{i}.metal', b'same MSL') for i in range(8)]
        outputs = [self.root / f'{i}.metallib' for i in range(8)]
        self.parallel_misses('to_file', lambda i: self.cache.compile('mac', sources[i], str(outputs[i])))
        self.assertEqual(self.calls, [b'same MSL'])
        self.assertEqual([p.read_bytes() for p in outputs], [b'compiled:same MSL'] * 8)
        self.assertEqual(self.cache.stats['mac', 'compiled'], 1)
        self.assertEqual(self.cache.stats['mac', 'reused'], 7)
        self.assertFalse(self.cache.pending)

    def test_same_split_source_misses_compile_once_and_keep_all_pieces(self):
        source = self.source('unit.metal', b'same unit')
        outputs = [[str(self.root / f'{i}-{part}.metallib') for part in range(3)] for i in range(8)]
        split = lambda data: (data[:9], data[9:13], data[13:])
        self.parallel_misses('has', lambda i: self.cache.compile_split('mac', source, outputs[i], split))
        self.assertEqual(self.calls, [b'same unit'])
        for group in outputs:
            self.assertEqual(tuple(Path(p).read_bytes() for p in group), split(b'compiled:same unit'))
        self.assertEqual(self.cache.stats['mac', 'compiled'], 1)
        self.assertEqual(self.cache.stats['mac', 'reused'], 7)
        self.assertFalse(self.cache.pending)

    def test_distinct_sources_compile_in_parallel(self):
        simultaneous = threading.Barrier(2)
        original = self.cache.targets['mac'][2]

        def compile_source(msl, air, lib):
            simultaneous.wait(timeout=10)  # a global compile lock would deadlock
            original(msl, air, lib)

        self.cache.targets['mac'] = ('macosx', 'flags', compile_source)
        sources = [self.source(f'{i}.metal', f'MSL {i}'.encode()) for i in range(2)]
        with cf.ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.cache.compile, 'mac', p, str(self.root / f'{i}.metallib'))
                       for i, p in enumerate(sources)]
            for future in futures:
                future.result(timeout=15)
        self.assertCountEqual(self.calls, [b'MSL 0', b'MSL 1'])
        self.assertFalse(self.cache.pending)

    def test_failed_compile_releases_waiter_without_publishing_failure(self):
        original = self.cache.targets['mac'][2]
        attempts = []

        def compile_source(msl, air, lib):
            attempts.append(1)
            if len(attempts) == 1:
                raise subprocess.CalledProcessError(1, ['synthetic-metal'])
            original(msl, air, lib)

        self.cache.targets['mac'] = ('macosx', 'flags', compile_source)
        source = self.source('source.metal', b'MSL')

        def request(i):
            output = self.root / f'{i}.metallib'
            try:
                self.cache.compile('mac', source, str(output))
            except subprocess.CalledProcessError:
                self.assertFalse(output.exists())
                return 'failed'
            self.assertEqual(output.read_bytes(), b'compiled:MSL')
            return 'compiled'

        self.assertCountEqual(self.parallel_misses('to_file', request, workers=2), ['failed', 'compiled'])
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.cache.stats['mac', 'compiled'], 1)
        self.assertFalse(self.cache.pending)

    def test_targets_remain_independent_and_parallel(self):
        simultaneous = threading.Barrier(2)
        original = self.cache.targets['mac'][2]

        def compile_source(msl, air, lib):
            simultaneous.wait(timeout=10)
            original(msl, air, lib)

        self.cache.targets['mac'] = ('macosx', 'flags', compile_source)
        self.cache.targets['ios'] = ('iphoneos', 'other flags', compile_source)
        self.cache.ident['ios'] = b'different compiler/flags identity'
        source = self.source('shared.metal', b'MSL')
        with cf.ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.cache.compile, target, source, str(self.root / f'{target}.metallib'))
                       for target in ('mac', 'ios')]
            for future in futures:
                future.result(timeout=15)
        self.assertEqual(len(self.calls), 2)
        self.assertNotEqual(self.cache.path('mac', b'MSL'), self.cache.path('ios', b'MSL'))
        self.assertEqual(self.cache.stats['mac', 'compiled'], 1)
        self.assertEqual(self.cache.stats['ios', 'compiled'], 1)
        self.assertFalse(self.cache.pending)

    def test_unwritable_cache_still_produces_outputs_and_releases_locks(self):
        source = self.source('source.metal', b'MSL')
        outputs = [self.root / f'{i}.metallib' for i in range(8)]
        # Store.put_file deliberately allows the build to proceed without cache
        # persistence on a full drive. No waiter may assume publication worked.
        with mock.patch.object(self.store, 'put_file', return_value=None):
            self.parallel_misses('to_file', lambda i: self.cache.compile('mac', source, str(outputs[i])))
        self.assertEqual(len(self.calls), 8)
        self.assertEqual([p.read_bytes() for p in outputs], [b'compiled:MSL'] * 8)
        self.assertFalse(self.cache.pending)

    def test_split_error_releases_entry_and_does_not_cache_partial_result(self):
        source = self.source('unit.metal', b'MSL')
        outputs = [str(self.root / f'{i}.metallib') for i in range(2)]
        with self.assertRaises(ValueError):
            self.cache.compile_split('mac', source, outputs, lambda data: (data,))
        self.assertFalse(self.cache.pending)
        self.assertFalse(self.store.has(self.cache.path('mac', b'MSL')))
        self.cache.compile_split('mac', source, outputs, lambda data: (data[:3], data[3:]))
        self.assertEqual(b''.join(Path(p).read_bytes() for p in outputs), b'compiled:MSL')
        self.assertFalse(self.cache.pending)


if __name__ == '__main__':
    unittest.main()
