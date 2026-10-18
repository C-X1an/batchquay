"""Conservative local export check. Not a substitute for an independent secret scan."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
allowed_dirs={'src','tests','tools','scripts','models','verification','docs','.github'}
ignored={'.git','.local-runs','.agent-local','__pycache__'}
patterns=[re.compile(rb'ghp_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{35,}'),
          re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
problems=[];count=0
try:
    tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0'))
except subprocess.CalledProcessError:
    tracked=set()
except FileNotFoundError:
    tracked=set()
for path in root.rglob('*'):
    relative=path.relative_to(root)
    excluded=any(x in ignored or x.startswith('build') or x.startswith('.venv') for x in relative.parts)
    if excluded:
        if relative.as_posix() in tracked: problems.append(str(relative)+': forbidden generated/private file is tracked')
        continue
    if path.is_symlink(): problems.append(str(relative)+': symlink requires explicit review');continue
    if not path.is_file(): continue
    if len(relative.parts)>1 and relative.parts[0] not in allowed_dirs:
        problems.append(str(relative)+': outside public allowlist')
    if path.suffix in {'.docx','.pem','.key','.token','.safetensors','.bqw','.zip','.partial'} or path.name.startswith('.env'):
        problems.append(str(relative)+': private/generated artifact')
    data=path.read_bytes();count+=1
    if any(p.search(data) for p in patterns): problems.append(str(relative)+': secret-like material')
if problems: raise SystemExit('\n'.join(problems))
print(f'PASS local path/content export checks for {count} files. Independent full-history scanner remains separate.')
