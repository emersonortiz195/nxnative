"""Exercise t_pollwait's sleep adapter with production sleep_precise, without Mach.

The fixture's frozen policy clock must not turn short guest sleeps into repeated
wall-clock sleeps. Actual condition-variable wait/signal coverage stays in the
Mac t_pollwait executable.
"""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class PollwaitFixture(unittest.TestCase):
    def test_frozen_clock_records_sleeps_without_blocking_or_advancing(self):
        fixture = (ROOT / 'dm/host/tests/t_pollwait.c').read_text()
        adapter = fixture[fixture.index('static _Atomic uint64_t poll_clock;'):
                          fixture.index('static _Thread_local struct timespec wait_start;')]
        source = (ROOT / 'dm/host/hle_thread.c').read_text()
        start = source.index('static void sleep_precise(uint64_t dl) {')
        precise = source[start:source.index('\n}', start) + 2]
        # A regression to real nanosleep in the adapter must fail immediately,
        # without making this test depend on CI scheduler timing.
        code = '''#include <assert.h>
#include <stdint.h>
#include <stdatomic.h>
#include <time.h>
static int forbidden_wall_sleep(const struct timespec *ts, struct timespec *rem) {
    (void)ts; (void)rem; assert(!"fixture must not sleep on the wall clock"); return -1;
}
#define nanosleep forbidden_wall_sleep
''' + adapter + '''
#undef nanosleep
#define nanosleep test_nanosleep
#define now_ns test_now_ns
''' + precise + '''
int main(void) {
    atomic_store(&poll_clock, 1000000);
    sleep_precise(1300000);
    // A frozen clock takes all 16 production attempts: the original fixture
    // paid this amplification in real sleeps for every 300 us guest sleep.
    assert(atomic_load(&sleep_calls) == 16);
    assert(atomic_load(&sleep_requested) == 16 * 225000);
    assert(test_now_ns() == 1000000);
    uint64_t before = atomic_load(&sleep_calls);
    sleep_precise(1020000); // already within the 20 us margin
    assert(atomic_load(&sleep_calls) == before);
    assert(test_nanosleep(&(struct timespec){0, 500000}, 0) == 0);
    assert(atomic_load(&sleep_requested) == 16 * 225000 + 500000);
    return 0;
}
'''
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('clang') or 'cc']
        with tempfile.TemporaryDirectory() as work:
            path = Path(work)
            (path / 'test.c').write_text(code)
            subprocess.run(compiler + ['-std=c11', '-Wall', '-Wextra', '-Werror',
                                      '-Wno-unused-function', str(path / 'test.c'),
                                      '-o', str(path / 'test')], check=True)
            subprocess.run([str(path / 'test')], check=True, timeout=5)
        self.assertIn('#define nanosleep test_nanosleep', fixture)
        self.assertIn('#undef nanosleep', fixture)
        self.assertIn('return pthread_cond_wait(cv, mutex);', fixture)


if __name__ == '__main__':
    unittest.main()
