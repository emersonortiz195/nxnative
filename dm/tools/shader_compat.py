#!/usr/bin/env python3
"""Read-only shader metadata preflight; never compiles, packs or rewrites libraries.

Pass b-<chain> or b-<chain>.img, not DM_MSL_DIR's parent directory.
Success checks metadata and file presence only, not Metal loadability, entry
points, reflection ABI validity, shader-map coverage or gameplay correctness.
"""
import argparse
import json
from pathlib import Path
import re

import romfs
import shader_lib

SHADER = re.compile(r'[0-9a-f]{16}_b\.json')


def header_chain(path):
    text = Path(path).read_text()
    matches = re.findall(r'^#define DMSH_CHAIN "([0-9a-f]{12})"$', text, re.M)
    if len(matches) != 1:
        raise ValueError('expected one DMSH_CHAIN definition')
    return matches[0]


def audit(lib, chain, game, inputs=None, keys=()):
    """Inspect the folder-first overlay the host reads, including partial builds.

    Only the image index and JSON/stamp bytes are read; metallibs are stat'ed.
    A stamped folder does not hide missing image files from the host.
    """
    folder = Path(shader_lib.folder_of(lib))
    image = Path(shader_lib.image_of(lib))
    files = {}
    if image.is_file():
        files.update((p.name, p) for p in romfs.Path(image).iterdir())
    if folder.is_dir():
        files.update((p.name, p) for p in folder.iterdir() if p.is_file())
    errors = []
    if folder.name != 'b-' + chain:
        errors.append(f'library name {folder.name} does not match host b-{chain}')
    stamp = {}
    if 'inputs.tsv' in files:
        stamp = dict(line.split('\t', 1) for line in files['inputs.tsv'].read_text().splitlines()
                     if '\t' in line and not line.startswith('#'))
    if stamp.get('game') != game:
        errors.append('missing or mismatched game stamp')
    if not stamp.get('inputs'):
        errors.append('missing inputs stamp: derived uniform tables cannot be accepted')
    elif inputs is not None and stamp['inputs'] != inputs:
        errors.append('profile inputs digest does not match archive stamp')
    names = sorted(n for n in files if SHADER.fullmatch(n))
    if not names:
        errors.append('no base shader reflection files found')
    for key in keys:
        if key + '_b.json' not in files:
            errors.append(f'{key}: requested shader reflection missing')
    for name in names:
        try:
            j = json.loads(files[name].read_text())
        except (ValueError, UnicodeError) as exc:
            errors.append(f'{name}: unreadable reflection ({exc})')
            continue
        if not isinstance(j, dict):
            errors.append(f'{name}: reflection must be an object')
            continue
        if j.get('chain') != chain:
            errors.append(f'{name}: chain {j.get("chain")!r}, expected {chain}')
        # The loader folds a gs_slice geometry shader without a Metal library.
        folded = j.get('stage') == 'gs' and isinstance(j.get('gs_slice'), dict)
        metal = name[:-5] + '.metallib'
        if not folded and (metal not in files or files[metal].stat().st_size == 0):
            errors.append(f'{metal}: missing or empty base library')
    return {'chain': chain, 'game': game, 'inputs': stamp.get('inputs'),
            'shaders_checked': len(names), 'errors': errors,
            'scope': 'metadata and base file presence only; Metal and gameplay untested'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--chain', help='chain recorded by the actual host build')
    source.add_argument('--host-header', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'gfx/nvn/dmsh_chain.h')
    parser.add_argument('--game', required=True)
    parser.add_argument('--inputs', help='expected profile inputs digest (optional)')
    parser.add_argument('--key', action='append', default=[], help='required base shader key; repeatable')
    args = parser.parse_args()
    try:
        chain = args.chain or header_chain(args.host_header)
        if not re.fullmatch('[0-9a-f]{12}', chain):
            raise ValueError('chain must be 12 lowercase hexadecimal digits')
        if any(not re.fullmatch('[0-9a-f]{16}', k) for k in args.key):
            raise ValueError('keys must be 16 lowercase hexadecimal digits')
        result = audit(args.library, chain, args.game, args.inputs, args.key)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'preflight could not inspect library: {exc}\n')
    print(json.dumps(result, indent=2))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
