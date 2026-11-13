"""Require the isolated GPU test's injected timeout to fail promptly, without cleanup."""
import os
import subprocess
import sys


def check_timeout(executable):
    result = subprocess.run([executable], env={**os.environ, 'DM_TEST_RH_TIMEOUT': '1'},
                            capture_output=True, timeout=15)
    if result.returncode != 1 or b'bounded GPU wait timed out' not in result.stderr:
        raise RuntimeError(f'timeout child did not take the bounded failure path (exit {result.returncode})')


if __name__ == '__main__':
    check_timeout(sys.argv[1])
