"""Audit the complete current export and all referenced history without a hash loop.

The result stays outside Git. A source-baseline receipt cannot attest a later
evidence commit: this check scans the current publication candidate each time.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from scripts import evidence


def verify_publication(root: Path = evidence.ROOT) -> dict:
    scanner=shutil.which('gitleaks')
    if not scanner: raise ValueError('current complete publication audit requires gitleaks')
    out=root/'.local-runs/publication'/uuid.uuid4().hex[:12]
    out.mkdir(parents=True)
    env=dict(os.environ)
    for key in ('GITLEAKS_CONFIG','GITLEAKS_CONFIG_TOML'): env.pop(key,None)
    def execute(name: str, command: list[str]) -> None:
        result=subprocess.run(command,cwd=root,env=env,capture_output=True,timeout=900)
        (out/f'{name}.stdout.txt').write_bytes(result.stdout)
        (out/f'{name}.stderr.txt').write_bytes(result.stderr)
        (out/f'{name}.command.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest()),indent=2)+'\n')
        if result.returncode: raise ValueError(f'publication {name} failed with exit {result.returncode}; outputs retained')
    def git(*args: str) -> bytes:
        return subprocess.check_output(['git',*args],cwd=root)
    head=git('rev-parse','HEAD').decode().strip()
    tree=git('rev-parse','HEAD^{tree}').decode().strip()
    inventory=git('ls-files','--cached','--others','--exclude-standard','-z')
    export={}
    for name in inventory.decode('utf-8').split('\0'):
        if not name: continue
        path=evidence._inside(root,root/evidence._safe_relative(name))
        export[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    # Includes every published receipt/review/index and any additional export
    # file; no broad verification/published exclusion is used here.
    execute('allowlist',[sys.executable,'scripts/audit_public.py'])
    common=['--config',str(root/'.gitleaks.toml'),'--redact','--ignore-gitleaks-allow',
            '--no-banner','--no-color','--report-format','json']
    execute('history',[scanner,'git',str(root),'--log-opts=--all',*common,'--report-path',str(out/'history.json')])
    base=Path(os.environ.get('BQ_TEMP_BASE',tempfile.gettempdir())).resolve()
    owned=base/('bqp-'+uuid.uuid4().hex[:10]);owned.mkdir(parents=True)
    try:
        for name in export:
            target=owned/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(root/name,target)
        execute('export',[scanner,'dir',str(owned),*common,'--report-path',str(out/'export.json')])
    finally:
        if owned.parent!=base or not owned.name.startswith('bqp-'): raise ValueError('unsafe cleanup target')
        shutil.rmtree(owned)
    if json.loads((out/'history.json').read_text()) or json.loads((out/'export.json').read_text()):
        raise ValueError('unresolved findings in complete current publication scope')
    if git('rev-parse','HEAD').decode().strip()!=head:
        raise ValueError('HEAD changed during publication audit')
    if git('ls-files','--cached','--others','--exclude-standard','-z')!=inventory:
        raise ValueError('public file inventory changed during publication audit')
    if any(hashlib.sha256(evidence._inside(root,root/name).read_bytes()).hexdigest()!=digest for name,digest in export.items()):
        raise ValueError('public file bytes changed during publication audit')
    result=dict(status='PASS',git_commit=head,git_tree=tree,full_history=True,
                complete_export_sha256=evidence.identity(export),export_files=len(export),findings=[],
                scope='Current complete candidate export, including all evidence envelopes, plus all referenced history through current HEAD; result deliberately retained outside Git.')
    (out/'export-manifest.json').write_text(json.dumps(export,indent=2,sort_keys=True)+'\n')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(verify_publication(),indent=2))
