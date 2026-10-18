"""Portable text hygiene, not a claim of clang-format or Python static typing."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
errors=[]
for base in ['src','tests','tools','scripts']:
    for path in (root/base).rglob('*'):
        if path.suffix not in ('.py','.cpp','.hpp') or '__pycache__' in path.parts: continue
        text=path.read_text()
        if not text.endswith('\n'): errors.append(str(path)+': missing final newline')
        for i,line in enumerate(text.splitlines(),1):
            if line.rstrip()!=line: errors.append(f'{path}:{i}: trailing whitespace')
if errors: raise SystemExit('\n'.join(errors))
print('PASS text hygiene; clang-format is a separate optional command')
