"""Regression for a real transient peak hidden by end-of-round reclamation."""
from __future__ import annotations
import json
import os
import subprocess
import unittest
import uuid
import shutil
import copy
from pathlib import Path
from tools.fixture import generate
from scripts.benchmark_evidence import validate
from tools import benchmark_measurements


class BenchmarkTests(unittest.TestCase):
    def test_transient_peak_precedes_terminal_reclamation(self) -> None:
        root=Path(__file__).resolve().parents[1]
        directory=root/'.local-runs'/('unit-benchmark-'+uuid.uuid4().hex)
        directory.mkdir(parents=True);self.addCleanup(shutil.rmtree,directory)
        model=directory/'tiny.bqw';generate(model)
        binary=Path(os.environ.get('BQ_BINARY','build/batchquay')).resolve()
        driver=binary.with_name('bq_benchmark'+('.exe' if os.name=='nt' else ''))
        payload='2\n4 3 1 2 3 4\n4 1 4 3 2 1\n'
        outputs=[]
        for variant in ('serial-recompute','contiguous','paged'):
            result=subprocess.run([str(driver),variant,str(model)],input=payload,text=True,
                                  capture_output=True,check=True,timeout=30)
            measured=json.loads(result.stdout)
            outputs.append([row['output'] for row in measured['requests']])
            if variant!='serial-recompute':
                # A's fifth token is cached while B still has four valid tokens.
                self.assertEqual(measured['logical_cache_bytes'],9*2*2*8*4)
            if variant=='paged':
                self.assertEqual(measured['peak_owned_pages'],3)
                self.assertGreaterEqual(measured['allocated_kv_bytes'],3*4*2*2*8*4)
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])

    def test_claimed_parity_without_native_outputs_is_rejected(self) -> None:
        # The independent review's prior false-green shape must not pass.
        forged=dict(schema_version=2,status='PASS',source_sha256='a'*64,model={},environment={},
                    repetitions=5,warmups_per_variant=1,workloads=[{},{}],
                    rows=[dict(output_parity=False,ttft_ms=999,peak_rss_bytes=1,logical_cache_bytes=0)]*30,
                    claims=dict(fused_batching=False))
        with self.assertRaisesRegex(ValueError,'model/binary'):
            validate(forged,Path('.'),Path('.'),'a'*64)

    def test_native_evidence_then_parity_timing_and_stream_corruption(self) -> None:
        root=Path(__file__).resolve().parents[1]
        directory=root/'.local-runs'/('unit-benchmark-evidence-'+uuid.uuid4().hex)
        directory.mkdir(parents=True);self.addCleanup(shutil.rmtree,directory)
        # All six fixed release workloads, with a smaller actual generated model
        # for bounded regression cost. This is never a reported performance run.
        model=directory/'validator-fixture.bqw';generate(model)
        baseline=benchmark_measurements.run(directory,5,model_path=model)
        validate(baseline,directory,root,baseline['source_sha256'])
        changed=copy.deepcopy(baseline)
        retained={'short-single','mixed-two'}
        for field in ('workloads','rows','warmup_rows','summary'):
            changed[field]=[row for row in changed[field] if row.get('id',row.get('workload')) in retained]
        self.assertEqual(len(changed['rows']),30)
        with self.assertRaisesRegex(ValueError,'complete fixed release workload coverage'):
            validate(changed,directory,root,baseline['source_sha256'])
        changed=copy.deepcopy(baseline)
        changed['workloads'][0]['output_lengths']=[7];changed['workloads'][0]['output_tokens']=7
        with self.assertRaisesRegex(ValueError,'fixed release workload definition'):
            validate(changed,directory,root,baseline['source_sha256'])
        changed=copy.deepcopy(baseline);changed['workloads'][0]['prompts'][0][0]^=1
        with self.assertRaisesRegex(ValueError,'fixed release prompt sequence'):
            validate(changed,directory,root,baseline['source_sha256'])
        for field,value,diagnostic in (('output_parity',False,'parity'),('ttft_ms',999,'timing')):
            changed=copy.deepcopy(baseline);changed['rows'][0][field]=value
            with self.assertRaisesRegex(ValueError,diagnostic):
                validate(changed,directory,root,baseline['source_sha256'])
        changed=copy.deepcopy(baseline);changed['warmup_rows']=[]
        with self.assertRaisesRegex(ValueError,'incomplete'):
            validate(changed,directory,root,baseline['source_sha256'])
        changed=copy.deepcopy(baseline);changed['rows'].append(changed['rows'][0])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            validate(changed,directory,root,baseline['source_sha256'])
        raw=directory/baseline['rows'][0]['raw_stdout_file']
        with raw.open('ab') as stream: stream.write(b'tampered')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            validate(baseline,directory,root,baseline['source_sha256'])


if __name__=='__main__': unittest.main(verbosity=2)
