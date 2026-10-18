"""Build isolated deliberate defects; require baseline PASS, mutation FAIL, baseline PASS."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]


def execute(command: list[str], cwd: Path, out: Path, env: dict | None = None) -> int:
    result=subprocess.run(command,cwd=cwd,capture_output=True,timeout=120,env=env)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.stdout.txt').write_bytes(result.stdout)
    out.with_suffix('.stderr.txt').write_bytes(result.stderr)
    out.with_suffix('.command.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode),indent=2))
    return result.returncode


def main() -> None:
    out=root/'.local-runs'/'mutation';out.mkdir(parents=True,exist_ok=True)
    baseline=[str(root/'build/native_tests')]
    if execute(baseline,root,out/'baseline-before')!=0: raise SystemExit('baseline native failure')
    numerical=['python3','-m','unittest','discover','-s','tests','-p','test_numerics.py','-v']
    if execute(numerical,root,out/'numerics-before')!=0: raise SystemExit('baseline numerical failure')
    cases=[('owner','src/cache.cpp','if (*p.owner!=owner) throw Error("E_OWNER"); // MUTATION_GUARD_OWNER',
            '(void)owner; // intentional removed ownership check','native'),
           ('attention-scale','src/model.cpp','scores[t]=sum/std::sqrt(static_cast<double>(hd));',
            'scores[t]=sum; // intentional wrong attention scale','numerical')]
    records=[]
    for name,file,old,new,kind in cases:
        with tempfile.TemporaryDirectory(prefix='batchquay-mutation-') as tmp:
            target=Path(tmp)/'source'
            shutil.copytree(root,target,ignore=shutil.ignore_patterns('.git','build*','.local-runs','__pycache__','*.pyc'))
            path=target/file;text=path.read_text()
            if text.count(old)!=1: raise RuntimeError('mutation no longer targets exactly one statement')
            path.write_text(text.replace(old,new))
            for i,command in enumerate([['cmake','-S','.','-B','build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release'],['cmake','--build','build','-j','2']]):
                if execute(command,target,out/f'{name}-build-{i}')!=0: raise RuntimeError('mutant did not compile')
            env=dict(os.environ,BQ_BINARY=str(target/'build/batchquay'))
            command=[str(target/'build/native_tests')] if kind=='native' else numerical
            code=execute(command,target,out/f'{name}-test',env)
            if code==0: raise RuntimeError(f'mutation survived: {name}')
            # Expected semantic failure, not a timeout, missing dependency, or build error.
            output=(out/f'{name}-test.stderr.txt').read_text()
            if kind=='native' and 'operation unexpectedly accepted' not in output: raise RuntimeError('wrong native failure')
            if kind=='numerical' and 'AssertionError' not in output: raise RuntimeError('wrong numerical failure')
            records.append(dict(name=name,exit_code=code,verdict='KILLED_BY_EXPECTED_TEST_FAILURE'))
    if execute(baseline,root,out/'baseline-after')!=0 or execute(numerical,root,out/'numerics-after')!=0:
        raise RuntimeError('restored source no longer passes')
    result=dict(sequence='PASS -> expected FAIL -> PASS',selected_mutations=records,
                scope='two selected critical invariants; not a global mutation score')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__': main()
