"""Paired CPU measurements using original kernels and the production paged actor."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import statistics
import struct
import subprocess
import time
from pathlib import Path
from tools.fixture import DEFAULT, generate
from scripts.evidence import identity, manifest, _write_json

VARIANTS = ('serial-recompute', 'contiguous', 'paged')
WORKLOADS = (
    ('short-single', [4], [8]),
    ('long-single', [96], [24]),
    ('mixed-four', [8, 24, 64, 96], [16, 8, 24, 4]),
    ('mixed-eight', [4, 12, 32, 96, 4, 12, 32, 96], [4, 12, 8, 24, 24, 8, 12, 4]),
    ('mixed-two', [16, 128], [32, 16]),
    ('mixed-sixteen', [4, 16, 64, 128]*4, [16, 32, 16, 32]*4),
)


def shape(model: Path) -> dict:
    with model.open('rb') as stream:
        values = struct.unpack('<4s8I2f', stream.read(44))
    if values[0] != b'BQW1' or values[1] != 1:
        raise ValueError('benchmark requires BQW1 version 1')
    return dict(zip(('vocab', 'dim', 'hidden', 'layers', 'heads', 'kv_heads',
                     'max_positions', 'epsilon', 'rope_theta'), values[2:]))


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_run(value: dict, outputs: list[int]) -> list[list[int]]:
    requests = value['requests']
    if len(requests) != len(outputs):
        raise RuntimeError('missing measured request')
    for row, expected in zip(requests, outputs):
        observed = row['token_observed_ms']
        if len(row['output']) != expected or len(observed) != expected:
            raise RuntimeError('incomplete output/timing distribution')
        if observed != sorted(observed) or row['ttft_ms'] != observed[0]:
            raise RuntimeError('invalid observed token timestamps')
    if value['peak_rss_bytes'] <= 0 or value['elapsed_ms'] <= 0:
        raise RuntimeError('missing native resource/timing measurements')
    return [row['output'] for row in requests]


def run(out: Path, repetitions: int = 5, model_path: Path | None = None) -> dict:
    if repetitions < 5:
        raise ValueError('at least five repetitions are required')
    out.mkdir(parents=True, exist_ok=True)
    if model_path is None:
        model = out/'measurement.bqw'
        cfg = dict(DEFAULT, vocab=257, dim=64, hidden=128, layers=4, heads=4, kv_heads=2)
        metadata = generate(model, config=cfg)
    else:
        model = model_path.resolve()
        metadata = dict(kind='USER_SUPPLIED_BQW1', config=shape(model),
                        sha256=digest(model), bytes=model.stat().st_size)
    model = model.resolve()
    native = Path(os.environ.get('BQ_BINARY', 'build/batchquay')).resolve()
    if os.name == 'nt' and not native.is_file():
        native = native.with_suffix('.exe')
    driver = Path(os.environ.get('BQ_BENCHMARK_BINARY', str(native.with_name('bq_benchmark'+native.suffix)))).resolve()
    cfg = metadata['config']
    workloads = []
    rows = []
    warmups = []
    for workload_id, lengths, outputs in WORKLOADS:
        prompts = [[(position*7 + index*19 + 3) % cfg['vocab'] for position in range(length)]
                   for index, length in enumerate(lengths)]
        if max(a+b for a, b in zip(lengths, outputs)) > cfg['max_positions']:
            raise ValueError('model context cannot hold the fixed benchmark workloads')
        workloads.append(dict(id=workload_id, prompt_tokens=max(lengths), output_tokens=max(outputs),
                              concurrency=len(lengths), prompt_lengths=lengths, output_lengths=outputs,
                              prompts=prompts, arrival='all at native time zero'))
        payload = str(len(lengths))+'\n'+''.join(
            f'{len(prompt)} {output} '+' '.join(map(str, prompt))+'\n'
            for prompt, output in zip(prompts, outputs))
        expected = None
        for repetition in range(-1, repetitions):
            shift = max(repetition, 0) % len(VARIANTS)
            order = VARIANTS[shift:]+VARIANTS[:shift]
            for order_index, variant in enumerate(order):
                command = [os.path.relpath(driver, Path.cwd()).replace(os.sep,'/'), variant,
                           os.path.relpath(model, Path.cwd()).replace(os.sep,'/')]
                started = time.perf_counter_ns()
                completed = subprocess.run(command, input=payload.encode(), capture_output=True, timeout=900)
                process_wall_ms = (time.perf_counter_ns()-started)/1e6
                stem = f'{workload_id}-{repetition}-{variant}'
                (out/f'{stem}.stdout.json').write_bytes(completed.stdout)
                (out/f'{stem}.stderr.txt').write_bytes(completed.stderr)
                _write_json(out/f'{stem}.command.json',dict(
                    command=command, input=payload, exit_code=completed.returncode,
                    process_wall_ms=process_wall_ms))
                completed.check_returncode()
                measured = json.loads(completed.stdout)
                actual = validate_run(measured, outputs)
                if expected is None:
                    expected = actual
                if actual != expected:
                    raise RuntimeError(f'greedy outputs differ: {workload_id}/{variant}/{repetition}')
                intervals = [b-a for request in measured['requests']
                             for a, b in zip(request['token_observed_ms'], request['token_observed_ms'][1:])]
                row = dict(workload=workload_id, variant=variant, repetition=repetition,
                           order=order_index, process_wall_ms=process_wall_ms,
                           ttft_ms=statistics.median(request['ttft_ms'] for request in measured['requests']),
                           ttft_per_request_ms=[request['ttft_ms'] for request in measured['requests']],
                           inter_token_ms=intervals, **{k: v for k, v in measured.items() if k != 'variant'},
                           raw_stdout_file=f'{stem}.stdout.json',raw_stderr_file=f'{stem}.stderr.txt',
                           raw_command_file=f'{stem}.command.json',
                           stdout_sha256=hashlib.sha256(completed.stdout).hexdigest(),
                           stderr_sha256=hashlib.sha256(completed.stderr).hexdigest(),
                           command_sha256=digest(out/f'{stem}.command.json'),output_parity=True)
                (warmups if repetition < 0 else rows).append(row)
    summary = []
    for workload in workloads:
        for variant in VARIANTS:
            selected = [r for r in rows if r['workload'] == workload['id'] and r['variant'] == variant]
            summary.append(dict(workload=workload['id'], variant=variant,
                                elapsed_median_ms=statistics.median(r['elapsed_ms'] for r in selected),
                                elapsed_minimum_ms=min(r['elapsed_ms'] for r in selected),
                                elapsed_maximum_ms=max(r['elapsed_ms'] for r in selected),
                                peak_rss_maximum_bytes=max(r['peak_rss_bytes'] for r in selected)))
    info = dict(schema_version=2, status='PASS', source_sha256=identity(manifest()),
                model=metadata, binary_sha256=digest(driver), repetitions=repetitions,
                warmups_per_variant=1, workloads=workloads, warmup_rows=warmups, rows=rows, summary=summary,
                environment=dict(platform=platform.platform(), python=platform.python_version(),
                                 cpu=platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER', 'unavailable'),
                                 logical_cpus=os.cpu_count(), threads=1,
                                 affinity_cores=len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None),
                claims=dict(fused_batching=False, performance_win_required=False),
                methodology=dict(
                    variants={'serial-recompute':'single-thread round grants; every prefix recomputed without persistent KV',
                              'contiguous':'single-thread round grants; one contiguous cache per request',
                              'paged':'production bounded paged Scheduler::step with owned arena'},
                    latency='Native steady clock from simultaneous arrival before cache allocation. Tokens visible at completed grant-round boundaries for every variant. Excludes model loading, pipe/JSON/controller costs.',
                    rss='Native process high-water working set on Windows; getrusage peak RSS on Linux. Includes model, allocator and harness; not attributable solely to KV.',
                    logical_cache='High-water complete-token KV payload measured at each forward before reclamation. Recompute has one temporary prefix. Allocated KV is retained vector payload capacity, including released paged buffers; excludes container overhead.',
                    pairing='Fixed prompts/output budgets; exact greedy output equality across all variants, warmups and repetitions. Fresh child each run, rotated variant order. All raw results retained.'),
                limitations=['Synthetic random weights unless --model is supplied; no language quality claim.',
                             'Shared desktop host, no CPU affinity or frequency control.',
                             'Round-visible TTFT/inter-token latency is not HTTP or per-token streaming latency.',
                             'Single-thread token scheduling; no fused GEMM, GPU, or production throughput claim.'])
    _write_json(out/'benchmark.json',info)
    return info
