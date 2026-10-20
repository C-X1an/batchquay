"""Mandatory full-product pretrained gate. Missing dependencies are not a PASS."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import subprocess
import uuid
from pathlib import Path
from scripts.evidence import _write_json


def verify(source: Path, native: Path, output: Path) -> dict:
    import numpy as np
    import torch
    import transformers
    from transformers import AutoModelForCausalLM
    from tools.convert_model import convert
    manifest=json.loads((Path(__file__).resolve().parents[1]/'models/manifest.json').read_text())
    receipt=json.loads((source/'download-receipt.json').read_text())
    if receipt['revision']!=manifest['revision'] or receipt['repository']!=manifest['repository']:
        raise ValueError('checkpoint provenance does not match pinned profile')
    for name in manifest['files']:
        h=hashlib.sha256()
        with (source/name).open('rb') as stream:
            while block:=stream.read(1<<20): h.update(block)
        if h.hexdigest()!=receipt['files'][name]['sha256']:
            raise ValueError('source artifact changed after download')
    output.mkdir(parents=True,exist_ok=True)
    one=convert(source,output/'model-1.bqw');two=convert(source,output/'model-2.bqw')
    if one['output_sha256']!=two['output_sha256']:
        raise ValueError('non-deterministic conversion')
    torch.set_num_threads(1)
    model=AutoModelForCausalLM.from_pretrained(str(source),dtype=torch.float32,
        attn_implementation='eager',trust_remote_code=False,local_files_only=True,
        use_safetensors=True).eval()
    rng=random.Random(20261019);rows=[]
    for case in range(20):
        tokens=[rng.randrange(49152) for _ in range(1+(case*7)%32)]
        with torch.inference_mode():
            ref=model(torch.tensor([tokens]),use_cache=False).logits[0].float().cpu().numpy()
        result=subprocess.run([str(native.resolve()),'logits',str(output/'model-1.bqw'),*map(str,tokens)],
            check=True,capture_output=True,text=True,timeout=180)
        actual=np.asarray(json.loads(result.stdout)['logits'],dtype=np.float64)
        if actual.shape!=ref.shape or not np.isfinite(actual).all():
            raise ValueError('invalid native logits')
        err=np.abs(actual-ref);ordered=np.sort(ref,axis=-1)
        confident=ordered[:,-1]-ordered[:,-2]>=0.02
        matches=bool(np.all(np.argmax(actual,axis=-1)[confident]==np.argmax(ref,axis=-1)[confident]))
        row=dict(case=case,tokens=tokens,max_abs=float(err.max()),mean_abs=float(err.mean()),
                 confident_top1_matches=matches,confident_positions=int(confident.sum()))
        rows.append(row)
        # Persist every attempted case, including a failing case.
        _write_json(output/'pretrained-progress.json',rows)
        if row['max_abs']>0.01 or row['mean_abs']>0.001 or not matches:
            raise ValueError(f'locked pretrained tolerance failed at case {case}')
    result=dict(status='PASS',revision=manifest['revision'],conversion=one,conversions=[one,two],
                conversion_hashes=[one['output_sha256'],two['output_sha256']],rows=rows,
                torch=torch.__version__,transformers=transformers.__version__)
    _write_json(output/'pretrained.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('.local-runs/model-source'))
    p.add_argument('--binary',type=Path,default=Path(os.environ.get('BQ_BINARY','build/batchquay')))
    p.add_argument('--output',type=Path,default=Path('.local-runs/real-model'))
    a=p.parse_args();print(json.dumps(verify(a.source,a.binary,a.output/uuid.uuid4().hex[:12]),indent=2))
