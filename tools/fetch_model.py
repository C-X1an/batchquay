"""Fetch only the pinned public checkpoint. No credentials or arbitrary model URL."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def fetch(destination: Path, profile: dict | None = None) -> dict:
    manifest=profile if profile is not None else json.loads((ROOT/'models/manifest.json').read_text())
    destination.mkdir(parents=True,exist_ok=True)
    result=dict(repository=manifest['repository'],revision=manifest['revision'],files={},
                expected_weight_sha256=manifest['expected_weight_sha256'])
    receipt_path=destination/'download-receipt.json'
    if receipt_path.exists():
        result=json.loads(receipt_path.read_text())
        if result['repository']!=manifest['repository'] or result['revision']!=manifest['revision']:
            raise ValueError('existing download belongs to another model revision')
    for name in manifest['files']:
        target=destination/name
        url=f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{name}"
        limit=1<<20 if name=='config.json' else 1<<30
        if target.exists():
            recorded=result['files'].get(name)
            if not recorded or target.is_symlink() or target.stat().st_size>limit:
                raise ValueError(f'{name}: existing artifact lacks valid provenance')
            digest=hashlib.sha256()
            with target.open('rb') as source:
                while block:=source.read(1<<20): digest.update(block)
            if digest.hexdigest()!=recorded['sha256'] or target.stat().st_size!=recorded['bytes']:
                raise ValueError(f'{name}: existing artifact changed')
            if name=='model.safetensors' and manifest['expected_weight_sha256'] is not None:
                if digest.hexdigest()!=manifest['expected_weight_sha256']:
                    raise ValueError('checkpoint digest mismatch')
                if target.stat().st_size!=manifest['expected_weight_bytes']:
                    raise ValueError('checkpoint length mismatch')
            continue
        temporary=target.with_suffix(target.suffix+'.partial')
        try:
            with urllib.request.urlopen(url,timeout=30) as response, temporary.open('xb') as out:
                digest=hashlib.sha256();total=0
                while block:=response.read(1<<20):
                    total+=len(block)
                    if total>limit:
                        raise ValueError('upstream artifact exceeds declared bound')
                    digest.update(block);out.write(block)
            if name=='model.safetensors' and manifest['expected_weight_sha256'] is not None:
                if digest.hexdigest()!=manifest['expected_weight_sha256']:
                    raise ValueError('checkpoint digest mismatch')
                if total!=manifest['expected_weight_bytes']:
                    raise ValueError('checkpoint length mismatch')
            result['files'][name]=dict(sha256=digest.hexdigest(),bytes=total,url=url)
            os.replace(temporary,target)
            # Persist completed files so a later network failure is restartable.
            staged=destination/'download-receipt.pending'
            staged.write_text(json.dumps(result,indent=2)+'\n')
            os.replace(staged,receipt_path)
        finally:
            temporary.unlink(missing_ok=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('.local-runs/model-source'))
    print(json.dumps(fetch(p.parse_args().output),indent=2))
