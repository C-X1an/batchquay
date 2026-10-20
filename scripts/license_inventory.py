"""Check exact installed reference versions and notice bytes against reviewed policy."""
from __future__ import annotations
import hashlib
import importlib.metadata as metadata
import json
import sys
import argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def collect(policy_name: str = 'verification/dependency_license_policy.json',
            lock_name: str = 'requirements-reference-windows-cp312.lock') -> dict:
    policy_path=(ROOT/policy_name).resolve();lock=(ROOT/lock_name).resolve()
    if not policy_path.is_relative_to(ROOT) or not lock.is_relative_to(ROOT):
        raise RuntimeError('license policy/lock must be public repository files')
    policy=json.loads(policy_path.read_text(encoding='utf-8'))
    if hashlib.sha256(lock.read_bytes()).hexdigest()!=policy['lock_sha256']:
        raise RuntimeError('license policy does not match resolved dependency lock')
    prefix=Path(sys.prefix).resolve()
    packages=[];unresolved=[]
    for row in policy['packages']:
        item=dict(name=row['name'],version=row['version'],license=row['license'],approved=False,notices=[])
        try:
            if metadata.version(row['name'])!=row['version']: raise RuntimeError('installed version mismatch')
            for notice in row['notices']:
                path=(prefix/notice['path']).resolve()
                if not path.is_relative_to(prefix): raise RuntimeError('notice escapes environment')
                payload=path.read_bytes()
                digest=hashlib.sha256(payload).hexdigest()
                if digest!=notice['sha256'] or len(payload)!=notice['bytes']: raise RuntimeError('notice bytes mismatch')
                item['notices'].append(dict(path=notice['path'],sha256=digest))
            if not row['notices']:
                notice=row['upstream_notice']
                path=(ROOT/notice['path']).resolve()
                if not path.is_relative_to(ROOT): raise RuntimeError('notice escapes repository')
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                if digest!=notice['sha256']: raise RuntimeError('upstream notice mismatch')
                item['notices'].append(dict(path=notice['path'],sha256=digest,source=notice['source'],
                                             source_archive_sha256=notice['source_archive_sha256']))
            item['approved']=row['approved'] is True
            if not item['approved']: raise RuntimeError('dependency not approved for verification use')
        except (OSError,KeyError,RuntimeError,metadata.PackageNotFoundError) as error:
            unresolved.append(dict(name=row['name'],reason=str(error)))
        packages.append(item)
    return dict(status='FAIL' if unresolved else 'PASS',packages=packages,unresolved=unresolved,
                scope=policy['scope'],lock_sha256=policy['lock_sha256'])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--policy',default='verification/dependency_license_policy.json')
    parser.add_argument('--lock',default='requirements-reference-windows-cp312.lock')
    args=parser.parse_args();result=collect(args.policy,args.lock)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)
