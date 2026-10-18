"""Run the real Clang static analyzer; unavailable tools are an error, not a skip."""
import shutil
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
compiler=shutil.which('clang++')
if not compiler: raise SystemExit('BLOCKED: clang++ static analyzer unavailable')
for source in sorted((root/'src').glob('*.cpp')):
    command=[compiler,'--analyze','-std=c++20','-Isrc','-Xanalyzer','-analyzer-output=text',str(source)]
    result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=60)
    print(source.name,result.returncode)
    print(result.stdout+result.stderr)
    if result.returncode or 'warning:' in result.stderr: raise SystemExit(1)
print('PASS Clang static analyzer for src/*.cpp; not a proof of correctness')
