"""Refuse release while required criteria lack current receipts or independent review."""
import json
from pathlib import Path
from scripts.evidence import identity, manifest, verify
root=Path(__file__).resolve().parents[1]
status_path=root/'verification/criterion_status.json'
if not status_path.exists(): raise SystemExit('NOT RELEASE READY: criterion evidence index not established')
status=json.loads(status_path.read_text());errors=[]
for i in range(1,25):
    ac=f'AC-{i:03d}';entry=status['criteria'].get(ac,{})
    if entry.get('status')!='PASS': errors.append(f'{ac}: {entry.get("status","NOT RUN")}')
    elif not entry.get('receipts'): errors.append(ac+': missing receipt paths')
    else:
        for name in entry['receipts']:
            try:
                record=verify(root/name)
                if record['exit_code']!=0: errors.append(ac+': nonzero verification receipt')
            except (OSError,ValueError,KeyError) as exc: errors.append(ac+': '+str(exc))
if not status.get('independent_verifier_completed'): errors.append('independent verifier NOT RUN')
if status.get('source_sha256')!=identity(manifest()): errors.append('criterion index belongs to different source')
if errors: raise SystemExit('NOT RELEASE READY\n'+'\n'.join(errors))
print('Release evidence gate passed; human review of semantic evidence and publication scope remains necessary.')
