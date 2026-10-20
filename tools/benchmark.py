"""Paired command-level smoke benchmark, not a production serving benchmark."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path
from tools.fixture import generate
from scripts.evidence import identity, manifest


def run_smoke(out: Path, repetitions: int = 5) -> dict:
    if repetitions<5:
        raise ValueError('at least five repetitions are required')
    out.mkdir(parents=True,exist_ok=True)
    model=out/'tiny.bqw';metadata=generate(model)
    binary=str(Path(os.environ.get('BQ_BINARY','build/batchquay')).resolve())
    variants={'contiguous':[], 'paged':['--paged'], 'serial-recompute':['--recompute']}
    rows=[];tokens=[(i*7)%37 for i in range(64)];expected=None
    for repetition in range(-1,repetitions):
        names=list(variants)
        shift=max(repetition,0)%3;names=names[shift:]+names[:shift]
        for variant in names:
            command=[binary,'logits',*variants[variant],str(model),*map(str,tokens)]
            start=time.perf_counter_ns()
            result=subprocess.run(command,capture_output=True,check=True,timeout=30)
            elapsed=(time.perf_counter_ns()-start)/1e6
            values=json.loads(result.stdout)['logits']
            if expected is None:
                expected=values
            if values!=expected:
                raise RuntimeError('variant outputs differ')
            if repetition>=0:
                rows.append(dict(repetition=repetition,variant=variant,process_wall_ms=elapsed,
                    stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),positions=64))
    summary={name:dict(median_ms=statistics.median(v['process_wall_ms'] for v in rows if v['variant']==name),
                      minimum_ms=min(v['process_wall_ms'] for v in rows if v['variant']==name),
                      maximum_ms=max(v['process_wall_ms'] for v in rows if v['variant']==name)) for name in variants}
    info=dict(schema_version=1,scope='synthetic tiny model; fresh-process wall time including load and JSON output; not TTFT or production throughput',
        source_sha256=identity(manifest()),model=metadata,repetitions=repetitions,warmups_per_variant=1,
        environment=dict(platform=platform.platform(),python=platform.python_version(),
            cpu=(Path('/proc/cpuinfo').read_text().split('model name')[1].split('\n')[0].strip(' :\t') if Path('/proc/cpuinfo').exists() else 'unknown'),
            affinity_cores=(len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None)),
        rows=rows,summary=summary,memory_rss='NOT MEASURED',serving_latency='NOT MEASURED',
        limitations=['shared container; no CPU affinity pin','one tiny synthetic workload','not a dedicated reference-host study'])
    (out/'benchmark.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


from tools.benchmark_measurements import run


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('.local-runs/benchmark'))
    p.add_argument('--repetitions',type=int,default=5)
    p.add_argument('--model',type=Path);a=p.parse_args()
    result=run(a.output,a.repetitions,a.model)
    print(json.dumps({key:result[key] for key in ('status','source_sha256','repetitions','summary')},indent=2))
