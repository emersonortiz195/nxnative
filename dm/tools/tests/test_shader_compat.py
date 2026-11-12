"""Synthetic archives exercise the read-only preflight without Metal or games."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import shader_compat
import shader_lib

OLD, NEW = '39eb2f781d07', '3ae08e02ec6a'
GAME, KEY = '0400486024DEC000', '0123456789abcdef'


class Compatibility(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lib = self.root / ('b-' + OLD)
        self.files = {'inputs.tsv': f'game\t{GAME}\ninputs\tstamp\n'.encode(),
                      KEY + '_b.json': json.dumps({'chain': OLD, 'stage': 'fs'}).encode(),
                      KEY + '_b.metallib': b'synthetic library, not real Metal'}

    def image(self):
        shader_lib.write(self.files, str(self.lib) + '.img')

    def audit(self, **kwargs):
        return shader_compat.audit(self.lib, OLD, GAME, **kwargs)

    def test_matching_image_is_read_only(self):
        self.image()
        image = Path(str(self.lib) + '.img')
        before = hashlib.sha256(image.read_bytes()).digest()
        self.assertEqual(self.audit(inputs='stamp', keys=[KEY])['errors'], [])
        self.assertEqual(hashlib.sha256(image.read_bytes()).digest(), before)
        self.assertEqual(list(self.root.iterdir()), [image])

    def test_matching_folder(self):
        self.lib.mkdir()
        for n, data in self.files.items():
            (self.lib / n).write_bytes(data)
        self.assertEqual(self.audit()['errors'], [])

    def test_new_host_rejects_old_archive(self):
        self.image()
        errors = shader_compat.audit(self.lib, NEW, GAME)['errors']
        self.assertTrue(any('library name' in e for e in errors))
        self.assertTrue(any('expected ' + NEW in e for e in errors))

    def test_renaming_image_does_not_make_it_compatible(self):
        self.image()
        renamed = self.root / ('b-' + NEW + '.img')
        Path(str(self.lib) + '.img').rename(renamed)
        self.assertTrue(any('expected ' + NEW in e for e in
                            shader_compat.audit(renamed, NEW, GAME)['errors']))

    def test_folder_overlay_wins_even_with_stamp(self):
        self.image()
        self.lib.mkdir()
        (self.lib / 'inputs.tsv').write_bytes(self.files['inputs.tsv'])
        (self.lib / (KEY + '_b.json')).write_text(json.dumps({'chain': NEW}))
        self.assertTrue(any('expected ' + OLD in e for e in self.audit()['errors']))
        (self.lib / (KEY + '_b.json')).unlink()
        self.assertEqual(self.audit()['errors'], [])  # per-file image fallback

    def test_missing_game_inputs_library_and_requested_shader(self):
        for missing in ('inputs.tsv', KEY + '_b.metallib'):
            with self.subTest(missing=missing):
                saved = self.files.pop(missing)
                self.image()
                self.assertTrue(self.audit()['errors'])
                self.files[missing] = saved
        self.image()
        self.assertTrue(shader_compat.audit(self.lib, OLD, 'wrong')['errors'])
        self.assertTrue(self.audit(inputs='wrong')['errors'])
        self.assertTrue(self.audit(keys=['ffffffffffffffff'])['errors'])

    def test_bad_reflection_and_empty_library(self):
        for data in (b'not json', b'[]', b'{}'):
            self.files[KEY + '_b.json'] = data
            self.image()
            self.assertTrue(self.audit()['errors'])
        self.files[KEY + '_b.json'] = json.dumps({'chain': OLD}).encode()
        self.files[KEY + '_b.metallib'] = b''
        self.image()
        self.assertTrue(self.audit()['errors'])

    def test_folded_geometry_needs_no_library(self):
        self.files[KEY + '_b.json'] = json.dumps({'chain': OLD, 'stage': 'gs', 'gs_slice': {}}).encode()
        del self.files[KEY + '_b.metallib']
        self.image()
        self.assertEqual(self.audit()['errors'], [])

    def test_empty_archive_fails(self):
        self.files = {}
        self.image()
        self.assertTrue(self.audit()['errors'])

    def test_cli_status_and_header(self):
        self.image()
        header = self.root / 'chain.h'
        header.write_text(f'#define DMSH_CHAIN "{OLD}"\n')
        self.assertEqual(shader_compat.header_chain(header), OLD)
        command = [sys.executable, str(TOOLS / 'shader_compat.py'), str(self.lib),
                   '--game', GAME, '--host-header', str(header)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['shaders_checked'], 1)
        header.write_text(f'#define DMSH_CHAIN "{NEW}"\n')
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        header.write_text('invalid')
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == '__main__':
    unittest.main()
