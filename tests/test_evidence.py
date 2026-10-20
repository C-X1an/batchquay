from __future__ import annotations
import copy
import os
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch
from html.parser import HTMLParser
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

    def test_unit_fixture_cannot_be_published_as_integration(self) -> None:
        path=self.receipt('unit-publication-control')
        with self.assertRaisesRegex(ValueError,'successful integration'):
            evidence.publish(path)

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
        captured=json.loads((artifact_path/'record.json').read_bytes())['artifacts'][0]['path']
        (evidence.ROOT/captured).write_text('{"status":"FAIL"}\n')
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
        self.assertTrue(command_matches(['make','BUILD=build-host','CMAKE=cmake','PYTHON=python3','verify'],{'kind':'make','target':'verify'}))
        self.assertFalse(command_matches(['make','verify'],{'kind':'make','target':'verify'}))
        self.assertFalse(command_matches(['python','-c','print("replacement")','-m','tools.browser_check'],
                                         {'kind':'python-module','module':'tools.browser_check'}))

    def test_inherited_recipe_replacement_is_removed_from_execution(self) -> None:
        poisoned=dict(os.environ,PYTHON='echo INHERITED_RECIPE_CONTROL',PYTHONOPTIMIZE='2')
        # Reproduce an external caller without this parent Make's command-line
        # PYTHON binding; that binding otherwise outranks the poisoned variable.
        for name in ('MAKEFLAGS','GNUMAKEFLAGS','MAKEOVERRIDES','MFLAGS','MAKELEVEL','MAKEFILES'):
            poisoned.pop(name,None)
        unsafe=subprocess.run(['make','security'],env=poisoned,cwd=evidence.ROOT,
                              capture_output=True,text=True,check=True,timeout=15)
        self.assertIn('INHERITED_RECIPE_CONTROL',unsafe.stdout)
        with patch.dict(os.environ,poisoned,clear=True):
            path=run('unit-inherited-environment',['make','security'],evidence_class='unit_fixture')
            assertion=run('unit-inherited-assertion-control',
                [sys.executable,'-c','assert False, "OPTIMIZATION_CONTROL"'],evidence_class='unit_fixture')
        self.addCleanup(shutil.rmtree,path)
        self.addCleanup(shutil.rmtree,assertion)
        self.assertEqual(verify(assertion)['exit_code'],1)
        self.assertIn('AssertionError',(assertion/'stderr.txt').read_text())
        info=verify(path)
        self.assertEqual(info['exit_code'],0)
        output=(path/'stdout.txt').read_text()
        self.assertNotIn('INHERITED_RECIPE_CONTROL',output)
        self.assertIn('PASS locked acceptance and phase plan',output)
        self.assertTrue(command_matches(info['command'],{'kind':'make','target':'security'}))

    def test_raw_stream_corruption_and_missing_original_are_rejected(self) -> None:
        path=self.receipt('unit-raw-corruption')
        with (path/'raw.stdout.txt').open('ab') as stream:stream.write(b'tampered')
        with self.assertRaisesRegex(ValueError,'raw stdout stream changed'):verify(path)
        other=self.receipt('unit-raw-missing')
        (other/'raw.stderr.txt').unlink()
        with self.assertRaisesRegex(ValueError,'raw stderr stream missing'):verify(other)
        # Published bundles intentionally omit originals; explicit metadata-only
        # scope still checks their retained transformed bytes and sealed record.
        self.assertEqual(verify(other,raw=False)['exit_code'],0)

    def test_source_output_overwrite_preserves_snapshot_then_tamper_is_rejected(self) -> None:
        directory=self.artifact_directory('unit-snapshot')
        source=directory/'semantic.json';source.write_bytes(b'{"version":1}\n')
        path=self.receipt('unit-snapshot-receipt',{'semantic':source})
        source.write_bytes(b'{"version":2}\n')
        info=verify(path)
        captured=evidence.ROOT/info['artifacts'][0]['path']
        self.assertEqual(captured.read_bytes(),b'{"version":1}\n')
        captured.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'artifact changed'):verify(path)

    def test_published_native_report_keeps_observations_link(self) -> None:
        directory=self.artifact_directory('unit-native-publication')
        build=Path(os.environ.get('BUILD','build')).resolve()
        binary=build/('batchquay.exe' if os.name=='nt' else 'batchquay')
        with patch.dict(os.environ,{'BQ_BINARY':str(binary)}):
            # Actual native integration, never a stand-in for the pretrained gate.
            path=run('publisher-native-control',[sys.executable,'-m','tools.demo','--output',str(directory)],
                     artifacts={'demo-trace':directory/'trace.json'},evidence_class='integration')
        self.addCleanup(shutil.rmtree,path)
        self.assertEqual(verify(path)['exit_code'],0)
        published=evidence.publish(path,'unit-native-publication-'+uuid.uuid4().hex)
        self.addCleanup(shutil.rmtree,published)
        class Links(HTMLParser):
            def __init__(self):super().__init__();self.paths=[]
            def handle_starttag(self,tag,attrs):
                if tag=='a':self.paths.extend(value for key,value in attrs if key=='href')
        parser=Links();parser.feed((published/'artifacts/report.html').read_text())
        self.assertIn('trace.json',parser.paths)
        self.assertTrue((published/'artifacts/trace.json').is_file())
        self.assertEqual(verify(published)['status'],'PASS')


if __name__=='__main__':
    unittest.main(verbosity=2)
