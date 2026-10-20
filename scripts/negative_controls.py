"""Build isolated deliberate defects; require baseline PASS, mutation FAIL, baseline PASS."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]


def execute(command: list[str], cwd: Path, out: Path, env: dict | None = None) -> int:
    started=time.perf_counter()
    result=subprocess.run(command,cwd=cwd,capture_output=True,timeout=600,env=env)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.stdout.txt').write_bytes(result.stdout)
    out.with_suffix('.stderr.txt').write_bytes(result.stderr)
    out.with_suffix('.command.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,
        duration_seconds=time.perf_counter()-started,stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(result.stderr).hexdigest()),indent=2))
    return result.returncode


def main() -> None:
    out=root/'.local-runs'/'mutation';out.mkdir(parents=True,exist_ok=True)
    build=Path(os.environ.get('BQ_BUILD','build')).resolve()
    suffix='.exe' if os.name=='nt' else ''
    baseline=[str(build/('native_tests'+suffix))]
    if execute(baseline,root,out/'baseline-before')!=0: raise SystemExit('baseline native failure')
    numerical=[sys.executable,'-m','unittest','discover','-s','tests','-p','test_numerics.py','-v']
    baseline_env=dict(os.environ,BQ_BINARY=str(build/('batchquay'+suffix)))
    if execute(numerical,root,out/'numerics-before',baseline_env)!=0: raise SystemExit('baseline numerical failure')
    cases=[('owner','src/cache.cpp','if (*p.owner!=owner) throw Error("E_OWNER"); // MUTATION_GUARD_OWNER',
            '(void)owner; // intentional removed ownership check','native'),
           ('attention-scale','src/model.cpp','scores[t]=sum/std::sqrt(static_cast<double>(hd));',
            'scores[t]=sum; // intentional wrong attention scale','numerical')]
    records=[]
    for name,file,old,new,kind in cases:
        base=Path(os.environ.get('BQ_TEMP_BASE',tempfile.gettempdir())).resolve()
        base.mkdir(parents=True,exist_ok=True)
        tmp=base/('bqm-'+uuid.uuid4().hex[:10]);tmp.mkdir()
        try:
            target=Path(tmp)/'source'
            # Copy only the public Git export, including intended untracked source;
            # never recurse into ignored weights, environments or build products.
            inventory=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root)
            for raw in inventory.decode('utf-8').split('\0'):
                if not raw: continue
                source=root/raw
                if source.is_symlink() or not source.resolve().is_relative_to(root):
                    raise RuntimeError('unsafe snapshot member')
                destination=target/raw;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,destination)
            path=target/file;text=path.read_text()
            if text.count(old)!=1: raise RuntimeError('mutation no longer targets exactly one statement')
            path.write_text(text.replace(old,new))
            for i,command in enumerate([['cmake','-S','.','-B','build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release'],['cmake','--build','build','--target','native_tests','batchquay','-j','2']]):
                if execute(command,target,out/f'{name}-build-{i}')!=0: raise RuntimeError('mutant did not compile')
            env=dict(os.environ,BQ_BINARY=str(target/'build'/('batchquay'+suffix)))
            command=[str(target/'build'/('native_tests'+suffix))] if kind=='native' else numerical
            code=execute(command,target,out/f'{name}-test',env)
            if code==0: raise RuntimeError(f'mutation survived: {name}')
            # Expected semantic failure, not a timeout, missing dependency, or build error.
            output=(out/f'{name}-test.stderr.txt').read_text()
            if kind=='native' and 'operation unexpectedly accepted' not in output: raise RuntimeError('wrong native failure')
            if kind=='numerical' and 'AssertionError' not in output: raise RuntimeError('wrong numerical failure')
            records.append(dict(name=name,exit_code=code,verdict='KILLED_BY_EXPECTED_TEST_FAILURE'))
        finally:
            if tmp.parent!=base or not tmp.name.startswith('bqm-'): raise RuntimeError('unsafe cleanup target')
            shutil.rmtree(tmp)
    if execute(baseline,root,out/'baseline-after')!=0 or execute(numerical,root,out/'numerics-after',baseline_env)!=0:
        raise RuntimeError('restored source no longer passes')
    result=dict(sequence='PASS -> expected FAIL -> PASS',selected_mutations=records,
                scope='two selected critical invariants; not a global mutation score')
    (out/'result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,indent=2))

if __name__=='__main__': main()
