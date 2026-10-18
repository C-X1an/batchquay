from __future__ import annotations
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.evidence import run, verify
from tools.demo import render


class EvidenceTests(unittest.TestCase):
    def test_changed_output_is_rejected(self) -> None:
        path=run('integrity-test',['python','-c','print("receipt-control")'])
        self.addCleanup(shutil.rmtree,path)
        self.assertEqual(verify(path)['exit_code'],0)
        with (path/'stdout.txt').open('ab') as out: out.write(b'tampered')
        with self.assertRaisesRegex(ValueError,'payload changed'): verify(path)

    def test_source_manifest_tamper_is_rejected(self) -> None:
        path=run('source-integrity-test',['python','-c','print("receipt-control")'])
        self.addCleanup(shutil.rmtree,path)
        data=json.loads((path/'source_manifest.json').read_text());data['src/model.cpp']='0'*64
        (path/'source_manifest.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'source manifest changed'): verify(path)

    def test_report_escapes_untrusted_strings(self) -> None:
        marker='<script>alert("x")</script>'
        page=render([dict(label=marker,response=dict(event=marker))],marker)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('src="http',page)


if __name__=='__main__':
    unittest.main(verbosity=2)
