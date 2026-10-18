from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file
from tools.fixture import DEFAULT, generate
from tools.reference import load
from tools.convert_model import convert


class ConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.original=self.root/'original.bqw';generate(self.original)
        cfg,w=load(self.original)
        self.config=dict(model_type='llama',architectures=['LlamaForCausalLM'],hidden_act='silu',
            tie_word_embeddings=True,attention_bias=False,mlp_bias=False,
            vocab_size=cfg['vocab'],hidden_size=cfg['dim'],intermediate_size=cfg['hidden'],
            num_hidden_layers=cfg['layers'],num_attention_heads=cfg['heads'],
            num_key_value_heads=cfg['kv_heads'],max_position_embeddings=cfg['max_positions'],
            rms_norm_eps=cfg['epsilon'],rope_theta=cfg['rope_theta'])
        tensors={'model.embed_tokens.weight':w['embed'],'model.norm.weight':w['norm']}
        mapping={'norm1':'input_layernorm.weight','norm2':'post_attention_layernorm.weight',
            'q':'self_attn.q_proj.weight','k':'self_attn.k_proj.weight','v':'self_attn.v_proj.weight',
            'o':'self_attn.o_proj.weight','gate':'mlp.gate_proj.weight','up':'mlp.up_proj.weight','down':'mlp.down_proj.weight'}
        for i,layer in enumerate(w['layers']):
            tensors.update({f'model.layers.{i}.{mapping[key]}':value for key,value in layer.items()})
        self.tensors={key:torch.from_numpy(value.copy()).float() for key,value in tensors.items()}
        self.save()

    def save(self) -> None:
        (self.root/'config.json').write_text(json.dumps(self.config))
        save_file(self.tensors,self.root/'model.safetensors')

    def test_conversion_exact_and_deterministic(self) -> None:
        one=convert(self.root,self.root/'one.bqw');two=convert(self.root,self.root/'two.bqw')
        self.assertEqual(one['output_sha256'],two['output_sha256'])
        self.assertEqual((self.root/'one.bqw').read_bytes(),self.original.read_bytes())

    def test_unsupported_bias_is_not_silently_dropped(self) -> None:
        self.config['attention_bias']=True;self.save()
        with self.assertRaisesRegex(ValueError,'semantics'): convert(self.root,self.root/'bad.bqw')
        self.assertFalse((self.root/'bad.bqw').exists())

    def test_nonfinite_and_extra_tensor_rejected(self) -> None:
        self.tensors['model.norm.weight'][0]=float('nan');self.save()
        with self.assertRaisesRegex(ValueError,'nonfinite'): convert(self.root,self.root/'nan.bqw')
        self.assertFalse((self.root/'nan.bqw').exists())
        self.tensors['model.norm.weight'][0]=1
        self.tensors['unexpected.weight']=torch.zeros(1);self.save()
        with self.assertRaisesRegex(ValueError,'tensor names'): convert(self.root,self.root/'extra.bqw')

    def test_existing_destination_is_preserved(self) -> None:
        path=self.root/'protected.bqw';path.write_bytes(b'keep existing output')
        with self.assertRaises(FileExistsError): convert(self.root,path)
        self.assertEqual(path.read_bytes(),b'keep existing output')


if __name__=='__main__': unittest.main(verbosity=2)
