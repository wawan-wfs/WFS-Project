"""Verify bundled source checksums (not user data or .env); standard library only."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MANIFEST=ROOT/'RELEASE_MANIFEST.json'


def main() -> int:
    if not MANIFEST.is_file():
        print('FAIL: release manifest missing')
        return 1
    try:
        data=json.loads(MANIFEST.read_text(encoding='utf-8'))
        files=data['files']
        if not isinstance(files,dict):
            raise ValueError('Invalid manifest file map')
    except (OSError,ValueError,KeyError) as exc:
        print('FAIL: bad release manifest:',exc)
        return 1
    failures=[]
    for name,expected in files.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            failures.append(f'Unsafe manifest path {name}')
            continue
        target=ROOT/path
        if target.is_symlink() or not target.is_file():
            failures.append(f'Missing or symbolic file {name}')
            continue
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        if digest!=expected:
            failures.append(f'Checksum mismatch {name}')
    print(f'Checked {len(files)} release files')
    if failures:
        for fail in failures:print('FAIL:',fail)
        return 1
    print('PASS: release files match SHA-256 manifest')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
