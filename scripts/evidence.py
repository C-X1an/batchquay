"""Capture real command results and bind them to explicit source and output hashes.

Hashes detect changed bytes; they are not an external attestation against an owner
who can rewrite both payload and manifest. No shell-string execution is used.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('src','tests','tools','scripts')
SOURCE_FILES = ('CMakeLists.txt','Makefile','requirements.txt','requirements-reference.txt',
    'API_SPEC.md','ACCEPTANCE_SPEC.md','PRD.md','ARCHITECTURE.md','THREAT_MODEL.md',
    'verification/acceptance.json','verification/acceptance.lock.json',
    'verification/phase_plan.json','verification/phase_plan.sha256','models/manifest.json')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(root: Path = ROOT) -> dict[str,str]:
    files = [root/x for x in SOURCE_FILES if (root/x).is_file()]
    for directory in SOURCE_DIRS:
        files.extend(p for p in (root/directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.plist'))
    return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in sorted(set(files))}


def identity(data: dict[str,str]) -> str:
    return sha(json.dumps(data,sort_keys=True,separators=(',',':')).encode())


def command_info(command: list[str]) -> str:
    try:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=5)
        return result.stdout.strip() if result.returncode==0 else 'UNAVAILABLE'
    except (OSError,subprocess.TimeoutExpired):
        return 'UNAVAILABLE'


def run(name: str, command: list[str], timeout: int = 180) -> Path:
    if not name.replace('-','').replace('_','').isalnum() or not command:
        raise ValueError('invalid evidence request')
    out=ROOT/'.local-runs'/'evidence'/f'{name}-{uuid.uuid4().hex[:12]}'
    out.mkdir(parents=True,exist_ok=False)
    sources=manifest()
    commit=command_info(['git','rev-parse','HEAD'])
    dirty=command_info(['git','status','--porcelain','--untracked-files=normal'])
    versions={tool:command_info([tool,'--version']).split('\n')[0] for tool in ('c++','clang++','cmake','git')}
    (out/'source_manifest.json').write_text(json.dumps(sources,indent=2)+'\n')
    start=dt.datetime.now(dt.timezone.utc).isoformat(); clock=time.perf_counter_ns()
    timed_out=False
    try:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        code,stdout,stderr=result.returncode,result.stdout,result.stderr
    except subprocess.TimeoutExpired as exc:
        code,stdout,stderr=124,exc.stdout or b'',exc.stderr or b'';timed_out=True
    except OSError as exc:
        code,stdout,stderr=127,b'',str(exc).encode()
    elapsed=(time.perf_counter_ns()-clock)/1e9
    (out/'stdout.txt').write_bytes(stdout);(out/'stderr.txt').write_bytes(stderr)
    info=dict(schema_version=1,name=name,command=command,cwd='public repository root',
        started_utc=start,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),duration_seconds=elapsed,exit_code=code,timed_out=timed_out,
        git_commit=commit,git_dirty=None if dirty=='UNAVAILABLE' else bool(dirty),runtime_versions=versions,
        category=name,stdout_file='stdout.txt',stderr_file='stderr.txt',
        status='PASS' if code==0 else 'FAIL',
        source_sha256=identity(sources),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),
        environment=dict(os=platform.platform(),python=platform.python_version(),machine=platform.machine()),
        scope='local execution; no independent-agent or hosted-CI attestation')
    (out/'record.json').write_text(json.dumps(info,indent=2)+'\n')
    return out


def verify(path: Path, current: bool = True) -> dict:
    info=json.loads((path/'record.json').read_text())
    sources=json.loads((path/'source_manifest.json').read_text())
    if identity(sources)!=info['source_sha256']:
        raise ValueError('source manifest changed')
    for stream in ('stdout','stderr'):
        if sha((path/f'{stream}.txt').read_bytes())!=info[f'{stream}_sha256']:
            raise ValueError(f'{stream} payload changed')
    if current and identity(manifest())!=info['source_sha256']:
        raise ValueError('receipt belongs to a different source state')
    return info


def main() -> None:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='operation',required=True)
    r=sub.add_parser('run');r.add_argument('name');r.add_argument('--timeout',type=int,default=180)
    r.add_argument('command',nargs=argparse.REMAINDER)
    v=sub.add_parser('verify');v.add_argument('path',type=Path);v.add_argument('--historical',action='store_true')
    args=p.parse_args()
    if args.operation=='run':
        command=args.command[1:] if args.command[:1]==['--'] else args.command
        path=run(args.name,command,args.timeout);info=verify(path)
        print(json.dumps(dict(path=str(path.relative_to(ROOT)),**info),indent=2))
        raise SystemExit(info['exit_code'])
    print(json.dumps(verify(args.path,not args.historical),indent=2))


if __name__=='__main__':
    main()
