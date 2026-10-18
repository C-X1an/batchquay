from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def check() -> None:
    lock=json.loads((ROOT/'verification/acceptance.lock.json').read_text())
    print('Acceptance lock fields:',sorted(lock))
    # Lock format is authored before source implementation and never regenerated here.
    if lock.get('algorithm')!='sha256' or set(lock.get('files',{}))!={'ACCEPTANCE_SPEC.md','verification/acceptance.json'}:
        raise ValueError('invalid acceptance lock structure')
    entries=lock['files']
    for name,digest in entries.items():
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('invalid acceptance digest')
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'locked acceptance changed: {name}')
    phases=json.loads((ROOT/'verification/phase_plan.json').read_text())
    actual=hashlib.sha256(json.dumps(phases,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if actual!=(ROOT/'verification/phase_plan.sha256').read_text().strip():
        raise ValueError('canonical phase definitions changed')
    if len({p['id'] for p in phases})!=len(phases):
        raise ValueError('duplicate phase identity')
    known=set()
    for p in phases:
        if not set(p['dependencies'])<=known:
            raise ValueError('phase dependency order invalid')
        known.add(p['id'])
    print('PASS locked acceptance and phase plan')


if __name__=='__main__':
    check()
