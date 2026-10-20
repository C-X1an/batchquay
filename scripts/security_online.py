"""Actual full-history/export scanners, a detection canary, advisories and notices."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import hashlib
import tempfile
import uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]


def main() -> None:
    gitleaks=shutil.which('gitleaks')
    audit_python=os.environ.get('BQ_PIP_AUDIT_PYTHON',sys.executable)
    reference_python=os.environ.get('BQ_REFERENCE_PYTHON',sys.executable)
    browser_python=os.environ.get('BQ_BROWSER_PYTHON',sys.executable)
    if not gitleaks: raise SystemExit('gitleaks unavailable; no scan claimed')
    out=root/'.local-runs/security-online';out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    for key in ('GITLEAKS_CONFIG','GITLEAKS_CONFIG_TOML'): env.pop(key,None)
    def run(name: str, command: list[str], expected: int = 0) -> subprocess.CompletedProcess:
        result=subprocess.run(command,cwd=root,env=env,capture_output=True,timeout=900)
        (out/f'{name}.stdout.txt').write_bytes(result.stdout)
        (out/f'{name}.stderr.txt').write_bytes(result.stderr)
        (out/f'{name}.command.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest()),indent=2)+'\n')
        if result.returncode!=expected: raise RuntimeError(f'{name} exit {result.returncode}; expected {expected}; raw outputs retained')
        return result
    common=['--config',str(root/'.gitleaks.toml'),'--redact','--ignore-gitleaks-allow',
            '--no-banner','--no-color','--report-format','json']
    base=Path(os.environ.get('BQ_TEMP_BASE',tempfile.gettempdir())).resolve()
    owned=base/('bqs-'+uuid.uuid4().hex[:10]);owned.mkdir(parents=True)
    try:
        canary=owned/'canary/verification/published/canary/source_manifest.json'
        canary.parent.mkdir(parents=True)
        # Intentionally fake high-entropy key at exactly the excluded path/field.
        # Its different value must remain detectable by the inherited generic rule.
        fake=hashlib.sha256(b'BatchQuay deliberate scanner detection control').hexdigest()
        canary.write_text(json.dumps({'API_SPEC.md':fake},indent=2)+'\n')
        run('canary',[gitleaks,'dir',str(owned/'canary'),*common,'--report-path',str(out/'canary.json')],1)
        canary_rows=json.loads((out/'canary.json').read_text())
        if not any(row.get('RuleID')=='generic-api-key' for row in canary_rows):
            raise RuntimeError('canary failed to exercise the original generic rule')
        run('history',[gitleaks,'git',str(root),'--log-opts=--all',*common,'--report-path',str(out/'gitleaks-history.json')])
        exported=owned/'export';exported.mkdir()
        inventory=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root)
        for name in inventory.decode('utf-8').split('\0'):
            if not name: continue
            source=root/name
            if source.is_symlink() or not source.resolve().is_relative_to(root): raise RuntimeError('unsafe export path')
            target=exported/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        run('export',[gitleaks,'dir',str(exported),*common,'--report-path',str(out/'gitleaks-export.json')])
        findings=json.loads((out/'gitleaks-history.json').read_text())+json.loads((out/'gitleaks-export.json').read_text())
        if findings: raise RuntimeError('scanner reported unresolved findings')
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        (out/'history-scan.json').write_bytes((json.dumps(dict(status='PASS',git_commit=commit,full_history=True,
            findings=[],canary_detected=True,configuration_sha256=hashlib.sha256((root/'.gitleaks.toml').read_bytes()).hexdigest(),
            scope='All referenced Git history and current public export; initial checksum findings retained separately.'),indent=2)+'\n').encode('utf-8'))
        (out/'gitleaks-report.json').write_bytes((json.dumps(dict(status='PASS',findings=[],canary_detected=True),indent=2)+'\n').encode('utf-8'))
        lock=root/'requirements-reference-windows-cp312.lock'
        run('advisories',[audit_python,'-m','pip_audit','--strict','--no-deps','--disable-pip',
            '--require-hashes','-r',str(lock),'--progress-spinner','off','-f','json','-o',str(out/'advisory-raw.json')])
        advisory=json.loads((out/'advisory-raw.json').read_text())
        if len(advisory['dependencies'])!=35 or any(row.get('vulns') or row.get('skip_reason') for row in advisory['dependencies']):
            raise RuntimeError('advisory coverage/findings require resolution')
        advisory['status']='PASS'
        (out/'advisory-report.json').write_bytes((json.dumps(advisory,indent=2)+'\n').encode('utf-8'))
        notices=run('licenses',[reference_python,'-m','scripts.license_inventory'])
        license_inventory=json.loads(notices.stdout)
        if license_inventory['status']!='PASS': raise RuntimeError('unresolved license inventory')
        run('browser-advisories',[audit_python,'-m','pip_audit','--strict','--no-deps','--disable-pip',
            '--require-hashes','-r',str(root/'requirements-browser.lock'),'--progress-spinner','off',
            '-f','json','-o',str(out/'browser-advisory-raw.json')])
        browser_advisory=json.loads((out/'browser-advisory-raw.json').read_text(encoding='utf-8'))
        if len(browser_advisory['dependencies'])!=4 or any(row.get('vulns') or row.get('skip_reason') for row in browser_advisory['dependencies']):
            raise RuntimeError('browser advisory coverage/findings require resolution')
        browser_notices=run('browser-licenses',[browser_python,'-m','scripts.license_inventory',
            '--policy','verification/browser_license_policy.json','--lock','requirements-browser.lock'])
        browser_inventory=json.loads(browser_notices.stdout)
        if browser_inventory['status']!='PASS': raise RuntimeError('unresolved browser license inventory')
        advisory['browser_dependencies']=browser_advisory['dependencies']
        (out/'advisory-report.json').write_bytes((json.dumps(advisory,indent=2)+'\n').encode('utf-8'))
        license_inventory['packages'].extend(browser_inventory['packages'])
        license_inventory['browser_lock_sha256']=browser_inventory['lock_sha256']
        (out/'license-inventory.json').write_bytes((json.dumps(license_inventory,indent=2)+'\n').encode('utf-8'))
        print('PASS actual full-history/export scans, detection control, 35 reference and 4 browser distribution advisory/notice checks (one shared package)')
    finally:
        if owned.parent!=base or not owned.name.startswith('bqs-'): raise RuntimeError('unsafe cleanup target')
        shutil.rmtree(owned)


if __name__=='__main__': main()
