from __future__ import annotations
import io
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.fetch_model import fetch


class FetchTests(unittest.TestCase):
    @staticmethod
    def profile(weight: bytes) -> dict:
        return dict(repository='example/model',revision='a'*40,
            files=['config.json','model.safetensors'],
            expected_weight_sha256=hashlib.sha256(weight).hexdigest(),
            expected_weight_bytes=len(weight))

    def test_resume_preserves_verified_files_after_network_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            profile=self.profile(b'checkpoint')
            with patch('urllib.request.urlopen',side_effect=[io.BytesIO(b'{}'),OSError('network failed')]):
                with self.assertRaisesRegex(OSError,'network failed'): fetch(dest,profile)
            self.assertEqual((dest/'config.json').read_bytes(),b'{}')
            with patch('urllib.request.urlopen',return_value=io.BytesIO(b'checkpoint')) as mock:
                result=fetch(dest,profile)
            self.assertEqual(mock.call_count,1)
            self.assertEqual(set(result['files']),{'config.json','model.safetensors'})
            self.assertFalse(list(dest.glob('*.partial')))
            with patch('urllib.request.urlopen',side_effect=AssertionError('unneeded network')):
                self.assertEqual(fetch(dest,profile),result)

    def test_changed_completed_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            profile=self.profile(b'weights')
            with patch('urllib.request.urlopen',side_effect=[io.BytesIO(b'{}'),io.BytesIO(b'weights')]):
                fetch(dest,profile)
            (dest/'config.json').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'): fetch(dest,profile)


if __name__=='__main__': unittest.main()
