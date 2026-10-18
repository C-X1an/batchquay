"""Defensive local safetensors -> BQW1 conversion. Never loads pickle or remote code."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path


def convert(source: Path, output: Path) -> dict:
    import numpy as np
    import torch
    from safetensors import safe_open
    raw=(source/'config.json').read_bytes()
    if len(raw)>1<<20:
        raise ValueError('oversized configuration')
    cfg=json.loads(raw)
    if (cfg.get('model_type')!='llama' or cfg.get('hidden_act')!='silu'
        or cfg.get('architectures')!=['LlamaForCausalLM'] or cfg.get('tie_word_embeddings') is not True
        or cfg.get('attention_bias',False) or cfg.get('mlp_bias',False)
        or cfg.get('rope_scaling') is not None or cfg.get('rope_interleaved',False)
        or cfg.get('pretraining_tp',1)!=1):
        raise ValueError('unsupported model semantics')
    v,d,f,l,h,kh=(cfg[x] for x in ('vocab_size','hidden_size','intermediate_size',
        'num_hidden_layers','num_attention_heads','num_key_value_heads'))
    for value,bound in zip((v,d,f,l,h,kh),(65536,2048,8192,64,32,32)):
        if type(value) is not int or not 0<value<=bound:
            raise ValueError('invalid bounded model dimension')
    if d%h or h%kh or (d//h)%2:
        raise ValueError('invalid head dimensions')
    positions=min(cfg['max_position_embeddings'],256)
    if type(positions) is not int or positions<=0:
        raise ValueError('invalid positions')
    epsilon,theta=cfg['rms_norm_eps'],cfg['rope_theta']
    if not np.isfinite([epsilon,theta]).all() or min(epsilon,theta)<=0:
        raise ValueError('invalid normalization/rope constants')
    kv=kh*d//h
    specs=[('model.embed_tokens.weight',(v,d))]
    for layer in range(l):
        base=f'model.layers.{layer}.'
        specs.extend((base+name,shape) for name,shape in (
            ('input_layernorm.weight',(d,)),('self_attn.q_proj.weight',(d,d)),
            ('self_attn.k_proj.weight',(kv,d)),('self_attn.v_proj.weight',(kv,d)),
            ('self_attn.o_proj.weight',(d,d)),('post_attention_layernorm.weight',(d,)),
            ('mlp.gate_proj.weight',(f,d)),('mlp.up_proj.weight',(f,d)),('mlp.down_proj.weight',(d,f))))
    specs.append(('model.norm.weight',(d,)))
    expected=44+4*sum(int(np.prod(shape)) for _,shape in specs)
    if expected>1<<30:
        raise ValueError('model payload exceeds one GiB')
    weights=source/'model.safetensors'
    if weights.stat().st_size>1<<30:
        raise ValueError('source weights exceed one GiB')
    digest=hashlib.sha256()
    output.parent.mkdir(parents=True,exist_ok=True)
    created=False
    try:
        with safe_open(weights,framework='pt',device='cpu') as tensors, output.open('xb') as out:
            created=True
            names=set(tensors.keys());required={name for name,_ in specs}
            if not required<=names or names-required-{'lm_head.weight'}:
                raise ValueError('unexpected/missing tensor names')
            if 'lm_head.weight' in names:
                if not torch.equal(tensors.get_tensor('lm_head.weight'),tensors.get_tensor('model.embed_tokens.weight')):
                    raise ValueError('untied output head')
            header=struct.pack('<4s8I2f',b'BQW1',1,v,d,f,l,h,kh,positions,epsilon,theta)
            out.write(header);digest.update(header)
            for name,shape in specs:
                tensor=tensors.get_tensor(name)
                if tuple(tensor.shape)!=shape or tensor.dtype not in (torch.float16,torch.bfloat16,torch.float32):
                    raise ValueError(f'unsupported tensor shape/dtype: {name}')
                array=tensor.to(dtype=torch.float32).contiguous().numpy().astype('<f4',copy=False)
                if not np.isfinite(array).all():
                    raise ValueError(f'nonfinite tensor: {name}')
                block=array.tobytes();out.write(block);digest.update(block)
        if output.stat().st_size!=expected:
            raise ValueError('converted length mismatch')
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    def file_sha(path: Path) -> str:
        hsh=hashlib.sha256()
        with path.open('rb') as stream:
            while block:=stream.read(1<<20): hsh.update(block)
        return hsh.hexdigest()
    info=dict(format='BQW1',bytes=expected,output_sha256=digest.hexdigest(),
        config_sha256=hashlib.sha256(raw).hexdigest(),source_weight_sha256=file_sha(weights),
        source_kind='local operator-selected safetensors; match download receipt for pinned-origin claim',
        torch_version=torch.__version__)
    output.with_suffix('.conversion.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(convert(a.source,a.output),indent=2))
