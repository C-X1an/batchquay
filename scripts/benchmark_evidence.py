"""Validate retained native measurements; recompute parity and latency summaries."""
from __future__ import annotations
import hashlib
import json
import math
import statistics
from pathlib import Path
from scripts import evidence


def number(value, positive: bool = False) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and (value>0 if positive else value>=0)


def validate(value: dict, directory: Path, root: Path, source: str) -> None:
    if value.get('schema_version')!=2 or value.get('status')!='PASS' or value.get('source_sha256')!=source:
        raise ValueError('expanded benchmark schema/status/source mismatch')
    model=value.get('model',{});config=model.get('config',{})
    for digest in (model.get('sha256',''),value.get('binary_sha256','')):
        if not evidence._is_hex64(digest): raise ValueError('model/binary digest missing')
    for key in ('vocab','dim','layers','kv_heads','heads','max_positions'):
        if not isinstance(config.get(key),int) or isinstance(config[key],bool) or config[key]<1: raise ValueError('model dimensions missing')
    environment=value.get('environment',{})
    if environment.get('threads')!=1 or not environment.get('platform') or not environment.get('python') or not environment.get('cpu'):
        raise ValueError('benchmark environment missing')
    repetitions=value.get('repetitions')
    if not isinstance(repetitions,int) or isinstance(repetitions,bool) or repetitions<5:
        raise ValueError('at least five repetitions required')
    if value.get('warmups_per_variant')!=1: raise ValueError('one retained warmup per pair required')
    definitions=value.get('workloads')
    if not isinstance(definitions,list) or len(definitions)<2: raise ValueError('mixed workloads missing')
    workloads={}
    for row in definitions:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or row['id'] in workloads:
            raise ValueError('invalid/duplicate workload identity')
        prompts=row.get('prompts');lengths=row.get('prompt_lengths');outputs=row.get('output_lengths')
        if not isinstance(prompts,list) or not prompts or not isinstance(lengths,list) or not isinstance(outputs,list):
            raise ValueError('workload token definitions missing')
        if len(prompts)!=len(lengths) or len(outputs)!=len(prompts) or row.get('concurrency')!=len(prompts):
            raise ValueError('workload request count mismatch')
        for prompt,length,output in zip(prompts,lengths,outputs):
            if not isinstance(length,int) or not isinstance(output,int) or length<1 or output<2:
                raise ValueError('invalid prompt/output budget')
            if not isinstance(prompt,list) or len(prompt)!=length or length+output>config['max_positions']:
                raise ValueError('workload length mismatch')
            if any(not isinstance(token,int) or isinstance(token,bool) or not 0<=token<config['vocab'] for token in prompt):
                raise ValueError('invalid workload token')
        if row.get('prompt_tokens')!=max(lengths) or row.get('output_tokens')!=max(outputs):
            raise ValueError('aggregate workload dimensions differ')
        workloads[row['id']]=row
    if max(row['concurrency'] for row in workloads.values())<2:
        raise ValueError('concurrent workload missing')
    variants=('serial-recompute','contiguous','paged')
    expected={(key,variant,repetition) for key in workloads for variant in variants for repetition in range(-1,repetitions)}
    seen=set();parity={};selected={}
    rows=value.get('rows');warmups=value.get('warmup_rows')
    if not isinstance(rows,list) or not isinstance(warmups,list): raise ValueError('retained measurement/warmup rows missing')
    for row in warmups+rows:
        if not isinstance(row,dict): raise ValueError('invalid measurement row')
        key=(row.get('workload'),row.get('variant'),row.get('repetition'))
        if not isinstance(key[2],int) or isinstance(key[2],bool): raise ValueError('invalid repetition type')
        if key not in expected or key in seen: raise ValueError('missing/duplicate/unexpected repetition')
        seen.add(key)
        if (row in warmups)!=(key[2]==-1): raise ValueError('warmup repetition mislabelled')
        workload=workloads[key[0]]
        if row.get('output_parity') is not True: raise ValueError('output parity not established')
        if not number(row.get('elapsed_ms'),True) or not number(row.get('process_wall_ms'),True):
            raise ValueError('elapsed/process time missing')
        if not number(row.get('peak_rss_bytes'),True) or not number(row.get('logical_cache_bytes')) or not number(row.get('allocated_kv_bytes')):
            raise ValueError('resource measurements missing')
        for prefix in ('stdout','stderr','command'):
            name=row.get(f'raw_{prefix}_file')
            if not isinstance(name,str) or Path(name).name!=name:
                raise ValueError('unsafe/missing native artifact filename')
            path=evidence._inside(root,directory/evidence._safe_relative(name))
            payload=path.read_bytes()
            if hashlib.sha256(payload).hexdigest()!=row.get(f'{prefix}_sha256'):
                raise ValueError('native child artifact hash mismatch')
            if prefix=='stdout': raw=json.loads(payload)
            if prefix=='command': command=json.loads(payload)
        if not isinstance(raw,dict) or not isinstance(command,dict): raise ValueError('invalid native artifact object')
        if command.get('exit_code')!=0 or command.get('process_wall_ms')!=row['process_wall_ms']:
            raise ValueError('native command did not succeed/measurement differs')
        args=command.get('command',[])
        if len(args)!=3 or Path(args[0]).name not in {'bq_benchmark','bq_benchmark.exe'} or args[1]!=key[1]:
            raise ValueError('unexpected measured child command')
        expected_input=str(workload['concurrency'])+'\n'+''.join(
            f'{len(prompt)} {output} '+' '.join(map(str,prompt))+'\n'
            for prompt,output in zip(workload['prompts'],workload['output_lengths']))
        if command.get('input')!=expected_input: raise ValueError('measured child used a different workload')
        if raw.get('variant')!=key[1] or any(row.get(k)!=v for k,v in raw.items()):
            raise ValueError('row differs from retained native output')
        requests=raw.get('requests')
        if not isinstance(requests,list) or len(requests)!=workload['concurrency']:
            raise ValueError('measured request count mismatch')
        outputs=[];first=[];intervals=[]
        for request,budget in zip(requests,workload['output_lengths']):
            if not isinstance(request,dict): raise ValueError('invalid native request object')
            tokens=request.get('output');times=request.get('token_observed_ms')
            if not isinstance(tokens,list) or len(tokens)!=budget or not isinstance(times,list) or len(times)!=budget:
                raise ValueError('native output/timing counts differ')
            if any(not isinstance(token,int) or isinstance(token,bool) or not 0<=token<config['vocab'] for token in tokens):
                raise ValueError('invalid measured output token')
            if any(not number(t) or t>raw['elapsed_ms']+1e-6 for t in times) or times!=sorted(times):
                raise ValueError('native timestamp outside elapsed interval')
            if request.get('ttft_ms')!=times[0]: raise ValueError('native TTFT differs from first token')
            outputs.append(tokens);first.append(times[0]);intervals.extend(b-a for a,b in zip(times,times[1:]))
        if row.get('ttft_ms')!=statistics.median(first) or row.get('ttft_per_request_ms')!=first or row.get('inter_token_ms')!=intervals:
            raise ValueError('derived token timing summary differs')
        if key[0] in parity and parity[key[0]]!=outputs: raise ValueError('cross-variant/repetition output parity failed')
        parity[key[0]]=outputs
        if key[2]>=0: selected.setdefault(key[:2],[]).append(row)
    if seen!=expected: raise ValueError('incomplete retained repetitions/warmups')
    summary=value.get('summary')
    if not isinstance(summary,list) or len(summary)!=len(workloads)*3: raise ValueError('comparison summary missing')
    summary_seen=set()
    for row in summary:
        key=(row.get('workload'),row.get('variant'))
        if key not in selected or key in summary_seen: raise ValueError('invalid comparison summary identity')
        summary_seen.add(key);items=selected[key]
        computed={'elapsed_median_ms':statistics.median(x['elapsed_ms'] for x in items),
                  'elapsed_minimum_ms':min(x['elapsed_ms'] for x in items),
                  'elapsed_maximum_ms':max(x['elapsed_ms'] for x in items),
                  'peak_rss_maximum_bytes':max(x['peak_rss_bytes'] for x in items)}
        if any(row.get(k)!=v for k,v in computed.items()): raise ValueError('comparison summary differs from retained distribution')
    if value.get('claims',{}).get('fused_batching') is not False:
        raise ValueError('fused-batching scope is not explicit')
