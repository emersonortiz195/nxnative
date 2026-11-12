#!/usr/bin/env python3
"""Read-only shader metadata preflight; never compiles, packs or rewrites libraries.

Pass b-<chain> or b-<chain>.img, not DM_MSL_DIR's parent directory.
Success checks metadata and file presence only, not Metal loadability, entry
points, reflection ABI validity or gameplay correctness. Map coverage is checked
only when --shader-map is supplied; optional uniform-table checks are warnings.
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


def map_keys(path):
    """Read control-section keys from the same TSV column the host uses."""
    keys = set()
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) >= 4 and fields[3] == 'dm_ctl_sha16':
            continue
        if len(fields) < 4 or not re.fullmatch('[0-9a-f]{16}', fields[3]):
            raise ValueError(f'{path}:{number}: invalid shader-map key row')
        keys.add(fields[3])
    if not keys:
        raise ValueError(f'{path}: shader map contains no keys')
    return keys


def audit(lib, chain, game, inputs=None, keys=(), tables_dir=None):
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
    keys = sorted(set(keys))
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
    warnings, tables = [], {}
    if tables_dir is not None:
        # Match shmap_read's literal prefix, including the space after inputs.
        # Missing/stale tables select conservative host fallbacks, not bad shaders.
        prefix = f'# chain b-{chain} inputs {stamp.get("inputs") or "-"} '
        for name in ('c1_full.tsv', 'cb_extent.tsv'):
            path = Path(tables_dir) / name
            try:
                with path.open() as stream:
                    head = stream.readline().rstrip('\r\n')
            except FileNotFoundError:
                tables[name] = 'missing'
            else:
                tables[name] = 'accepted' if stamp.get('inputs') and head.startswith(prefix) else 'stale'
            if tables[name] != 'accepted':
                warnings.append(f'{name}: {tables[name]}; host uses conservative uniform fallback')
    return {'chain': chain, 'game': game, 'inputs': stamp.get('inputs'),
            'shaders_checked': len(names), 'required_keys': len(keys), 'errors': errors,
            'tables': tables, 'warnings': warnings,
            'scope': 'metadata and base file presence only; Metal, side libraries and gameplay untested'}


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
    parser.add_argument('--shader-map', type=Path, help='require base reflection for every key in this TSV')
    parser.add_argument('--tables-dir', type=Path, help='report host acceptance of c1_full.tsv and cb_extent.tsv')
    args = parser.parse_args()
    try:
        chain = args.chain or header_chain(args.host_header)
        if not re.fullmatch('[0-9a-f]{12}', chain):
            raise ValueError('chain must be 12 lowercase hexadecimal digits')
        if any(not re.fullmatch('[0-9a-f]{16}', k) for k in args.key):
            raise ValueError('keys must be 16 lowercase hexadecimal digits')
        keys = set(args.key)
        if args.shader_map:
            keys.update(map_keys(args.shader_map))
        result = audit(args.library, chain, args.game, args.inputs, keys, args.tables_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'preflight could not inspect library: {exc}\n')
    print(json.dumps(result, indent=2))
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
