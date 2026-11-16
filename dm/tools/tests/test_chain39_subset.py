"""Source-integrity gates for the archive-preserving compatibility subset.

Does not load or compile the user's archive; Mac loading and gameplay are separate.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'dm/gfx/tools'))
import dmsh_chain  # noqa: E402

BASE = '04811a63'
CHAIN = '39eb2f781d07'


class Chain39Subset(unittest.TestCase):
    def test_computed_default_chain_and_header_match_existing_contract(self):
        with mock.patch.dict(os.environ, XLATE_DEBUG='1', XLATE_REDUCED='1'):
            self.assertEqual(dmsh_chain.version(), CHAIN)
        self.assertIn(f'#define DMSH_CHAIN "{CHAIN}"', Path(dmsh_chain.HEADER).read_text())

    def test_every_chain_input_is_identical_to_baseline(self):
        gfx = ROOT / 'dm/gfx'
        for name in dmsh_chain.FILES:
            with self.subTest(input=name):
                file = (gfx / name).resolve()
                relative = file.relative_to(ROOT).as_posix()
                original = subprocess.run(['git', 'show', f'{BASE}:{relative}'], cwd=ROOT,
                                          capture_output=True, check=True).stdout
                self.assertEqual(file.read_bytes(), original)

    def test_coalescing_is_not_a_shader_chain_input(self):
        self.assertNotIn('tools/dmsh_mtlcache.py', dmsh_chain.FILES)


if __name__ == '__main__':
    unittest.main()
