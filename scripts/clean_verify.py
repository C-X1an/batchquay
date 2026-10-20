"""Reproduce committed source with freshly provisioned hash-locked dependencies."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import sys
import hashlib
import time
import uuid
import venv
from scripts.evidence import identity, manifest, release_manifest, _write_json
from pathlib import Path
root=Path(__file__).resolve().parents[1]

def main() -> None:
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=root,text=True)
    if dirty.strip(): raise SystemExit('Commit all intended public files before clean reproduction; author tree is dirty')
    base=Path(os.environ.get('BQ_TEMP_BASE',tempfile.gettempdir())).resolve()
    base.mkdir(parents=True,exist_ok=True)
    owned=base/('bqc-'+uuid.uuid4().hex[:10]);owned.mkdir()
    checkout=owned/'source';environment=owned/'venv'
    out=root/'.local-runs'/'clean';out.mkdir(parents=True,exist_ok=True)
    steps=[]
    def execute(name: str, command: list[str], cwd: Path, env: dict | None = None) -> None:
        started=time.perf_counter()
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,timeout=1800)
        (out/f'{name}.stdout.txt').write_bytes(result.stdout)
        (out/f'{name}.stderr.txt').write_bytes(result.stderr)
        step=dict(name=name,command=command,exit_code=result.returncode,
                  duration_seconds=time.perf_counter()-started,
                  stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                  stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
        steps.append(step)
        _write_json(out/'steps.json',steps)
        if result.returncode: raise RuntimeError(f'{name} failed with exit {result.returncode}; retained in {out}')
    execute('clone',['git','-c','core.autocrlf=false','clone','--no-hardlinks',str(root),str(checkout)],root)
    execute('checkout',['git','-c','core.autocrlf=false','checkout','--detach',commit],checkout)
    # venv is a new directory, with no system site packages or author environment.
    venv.EnvBuilder(with_pip=True,system_site_packages=False).create(environment)
    python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    env=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):
        env.pop(name,None)
    env['PATH']=str(python.parent)+os.pathsep+env['PATH']
    env['VIRTUAL_ENV']=str(environment)
    lock_name='requirements-reference-windows-cp312.lock' if os.name=='nt' else 'requirements-core.lock'
    lock=checkout/lock_name
    if not lock.is_file(): raise RuntimeError(f'No verified dependency lock for this platform: {lock_name}')
    execute('dependency-install',[str(python),'-m','pip','install','--require-hashes','--only-binary=:all:',
            '--index-url','https://pypi.org/simple','--report',str(out/'install-report.json'),'-r',str(lock)],checkout,env)
    execute('dependency-check',[str(python),'-m','pip','check'],checkout,env)
    make=['make',f'PYTHON={python.as_posix()}']
    execute('build',make+['build'],checkout,env)
    execute('tests',make+['verify'],checkout,env)
    execute('demo',make+['demo'],checkout,env)
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=checkout,text=True).strip()
    record=dict(status='PASS',git_commit=commit,git_tree=tree,
                source_sha256=identity(manifest(checkout)),release_sha256=identity(release_manifest(checkout)),
                fresh_checkout=True,fresh_dependency_environment=True,hash_locked_dependencies=True,
                dependency_lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),
                steps=[{k:v for k,v in step.items() if k!='command'} for step in steps],
                scope='Fresh committed clone and fresh isolated dependency environment; same operating system and toolchain. Not a clean machine image.',
                retained_environment_id=owned.name,
                command_records='Exact command arrays and raw child streams retained locally in .local-runs/clean/steps.json and step files.')
    _write_json(out/'result.json',record)
    print(json.dumps(record,indent=2))

if __name__=='__main__': main()
