from __future__ import annotations
import copy
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from scripts import evidence
from scripts.evidence import run, verify
from scripts.release_verify import contract_errors, command_matches
from tools.demo import render


class EvidenceTests(unittest.TestCase):
    def receipt(self, name: str, artifacts: dict[str, Path] | None = None) -> Path:
        path=run(name,[sys.executable,'-c','print("receipt-control")'],
                 artifacts=artifacts,evidence_class='unit_fixture')
        self.addCleanup(shutil.rmtree,path)
        return path

    def artifact_directory(self, prefix: str) -> Path:
        path=evidence.ROOT/'.local-runs'/f'{prefix}-{uuid.uuid4().hex}'
        path.mkdir(parents=True)
        self.addCleanup(shutil.rmtree,path)
        return path

    def test_changed_output_is_rejected(self) -> None:
        path=self.receipt('integrity-test')
        self.assertEqual(verify(path)['exit_code'],0)
        with (path/'stdout.txt').open('ab') as out: out.write(b'tampered')
        with self.assertRaisesRegex(ValueError,'changed'): verify(path)

    def test_public_stream_retains_raw_and_discloses_path_transform(self) -> None:
        path=run('unit-path-redaction',[sys.executable,'-c','import os; print(os.getcwd()); print("diagnostic-preserved")'],
                 evidence_class='unit_fixture')
        self.addCleanup(shutil.rmtree,path)
        record=verify(path)
        raw=(path/'raw.stdout.txt').read_bytes();public=(path/'stdout.txt').read_bytes()
        self.assertIn(str(evidence.ROOT).encode(),raw)
        self.assertNotIn(str(evidence.ROOT).encode(),public)
        self.assertIn(b'diagnostic-preserved',public)
        self.assertEqual(record['environment']['raw_stdout_sha256'],evidence.sha(raw))
        self.assertIn('path-prefixes-v1',record['environment']['stream_transform'])

    def test_source_manifest_tamper_is_rejected(self) -> None:
        path=self.receipt('source-integrity-test')
        data=json.loads((path/'source_manifest.json').read_text());data['src/model.cpp']='0'*64
        (path/'source_manifest.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'changed'): verify(path)

    def test_record_output_and_artifact_tampering_are_rejected(self) -> None:
        record_path=self.receipt('record-tamper-test')
        record=json.loads((record_path/'record.json').read_text())
        record['category']='unrelated'
        (record_path/'record.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'record.json'):
            verify(record_path)

        stream_path=self.receipt('stream-tamper-test')
        (stream_path/'stderr.txt').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'stderr.txt'):
            verify(stream_path)

        artifact_dir=self.artifact_directory('unit-artifact')
        artifact=artifact_dir/'semantic.json';artifact.write_text('{"status":"PASS"}\n')
        artifact_path=self.receipt('artifact-tamper-test',{'semantic':artifact})
        artifact.write_text('{"status":"FAIL"}\n')
        with self.assertRaisesRegex(ValueError,'artifact changed'):
            verify(artifact_path)

    def test_path_escape_is_rejected(self) -> None:
        artifact_dir=self.artifact_directory('unit-path')
        artifact=artifact_dir/'semantic.json';artifact.write_text('{}\n')
        path=self.receipt('path-escape-test',{'semantic':artifact})
        record=json.loads((path/'record.json').read_text())
        old_label=record['artifacts'][0]['label'];old_path=record['artifacts'][0]['path']
        record['artifacts'][0]['path']='../escape.json'
        (path/'record.json').write_text(json.dumps(record,sort_keys=True)+'\n')
        bundle=json.loads((path/'bundle_manifest.json').read_text())
        old_key=f"artifact:{old_label}:{old_path}"
        digest=bundle['files'].pop(old_key)
        bundle['files']['artifact:semantic:../escape.json']=digest
        bundle['files']['record.json']=evidence.sha((path/'record.json').read_bytes())
        (path/'bundle_manifest.json').write_text(json.dumps(bundle,sort_keys=True)+'\n')
        with self.assertRaisesRegex(ValueError,'unsafe relative path'):
            verify(path)
        with self.assertRaisesRegex(ValueError,'escapes repository'):
            verify(evidence.ROOT.parent)

    def test_git_sha1_and_sha256_object_ids_are_valid(self) -> None:
        path=self.receipt('git-id-test')
        base=json.loads((path/'record.json').read_text())
        for size in (40,64):
            candidate=copy.deepcopy(base)
            candidate['git_commit']='a'*size
            candidate['git_tree']='b'*size
            self.assertEqual(evidence._validate_record(candidate),candidate)
        for bad in ('a'*39,'a'*65,'A'*40):
            candidate=copy.deepcopy(base);candidate['git_commit']=bad
            with self.assertRaisesRegex(ValueError,'git_commit'):
                evidence._validate_record(candidate)

    def test_unrelated_receipt_substitution_is_rejected(self) -> None:
        mapping=json.loads((evidence.ROOT/'verification/criterion_evidence_map.json').read_text())
        record={
            'schema_version':2,'evidence_class':'unit_fixture','category':'core',
            'command':['make','verify'],'status':'PASS','exit_code':0,'timed_out':False,
        }
        output='\n'.join(
            marker for criterion in mapping['criteria'].values()
            for requirement in criterion['receipts'] for marker in requirement.get('markers',[])
        )
        labels={
            label for criterion in mapping['criteria'].values()
            for requirement in criterion['receipts'] for label in requirement.get('artifacts',[])
        }
        # This is the original false-green construction: all 24 entries point to
        # one passing core fixture. Every criterion must now retain an error.
        for criterion,fixed in mapping['criteria'].items():
            problems=[]
            for requirement in fixed['receipts']:
                problems.extend(contract_errors(record,requirement,mapping['commands'],output,labels))
            self.assertTrue(problems,criterion)
        integration=dict(record,evidence_class='integration')
        real_requirement=mapping['criteria']['AC-012']['receipts'][0]
        self.assertIn("expected category 'real-model'",
                      contract_errors(integration,real_requirement,mapping['commands'],output,labels))

    def test_report_escapes_untrusted_strings(self) -> None:
        marker='<script>alert("x")</script>'
        page=render([dict(label=marker,response=dict(event=marker))],marker)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('src="http',page)

    def test_executed_replacement_make_recipe_is_rejected(self) -> None:
        directory=self.artifact_directory('unit-replacement-make')
        makefile=directory/'replacement.mk'
        makefile.write_text('verify:\n\t@echo PASS owner_rejection\n',encoding='utf-8')
        command=['make','-f',str(makefile),'verify']
        result=subprocess.run(command,capture_output=True,check=True,text=True,timeout=15)
        self.assertIn('PASS owner_rejection',result.stdout)
        self.assertFalse(command_matches(command,{'kind':'make','target':'verify'}))
        for command in (['make','-n','verify'],['make','--eval=verify:;','verify'],
                        ['make','PYTHON=$(info false-green)','verify'],['make','CMAKE=echo','verify'],
                        ['make','BUILD=../other','verify'],['make','PYTHON=python3','PYTHON=echo','verify']):
            self.assertFalse(command_matches(command,{'kind':'make','target':'verify'}),command)
        self.assertTrue(command_matches(['make','BUILD=build-host','PYTHON=python3','verify'],{'kind':'make','target':'verify'}))
        self.assertFalse(command_matches(['python','-c','print("replacement")','-m','tools.browser_check'],
                                         {'kind':'python-module','module':'tools.browser_check'}))


if __name__=='__main__':
    unittest.main(verbosity=2)
