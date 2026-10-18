"""Reproduce committed source in a temporary checkout, retaining execution outputs."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]

def main() -> None:
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=root,text=True)
    if dirty.strip(): raise SystemExit('Commit all intended public files before clean reproduction; author tree is dirty')
    with tempfile.TemporaryDirectory(prefix='batchquay-clean-') as tmp:
        subprocess.run(['git','clone','--no-hardlinks',str(root),tmp],check=True,capture_output=True)
        subprocess.run(['git','checkout','--detach',commit],cwd=tmp,check=True,capture_output=True)
        result=subprocess.run(['make','verify'],cwd=tmp,capture_output=True,text=True,timeout=180)
        out=root/'.local-runs'/'clean';out.mkdir(parents=True,exist_ok=True)
        (out/'stdout.txt').write_text(result.stdout);(out/'stderr.txt').write_text(result.stderr)
        record=dict(commit=commit,exit_code=result.returncode,
            scope='fresh committed source checkout on same host and installed dependencies; NOT fresh dependency provisioning')
        (out/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
        raise SystemExit(result.returncode)

if __name__=='__main__': main()
