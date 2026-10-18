from __future__ import annotations
import json
import os
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
import numpy as np
from tools.fixture import DEFAULT, generate
from tools.reference import load, logits

BIN = str(Path(os.environ.get('BQ_BINARY', 'build/batchquay')).resolve())


class NumericalTests(unittest.TestCase):
    def test_seeded_full_prefix_equivalence(self) -> None:
        """100 sequences, 3 model shapes/seeds, 3 native execution variants."""
        maximum, sum_sq, count = 0.0, 0.0, 0
        rng = random.Random(20261019)
        with tempfile.TemporaryDirectory() as tmp:
            models = []
            for i, kv_heads in enumerate((1, 2, 4)):
                path = Path(tmp) / f'm{i}.bqw'
                generate(path, 1729+i, dict(DEFAULT, kv_heads=kv_heads))
                cfg, weights = load(path)
                models.append((path, cfg, weights))
            for case in range(100):
                path, cfg, weights = models[case % len(models)]
                tokens = [rng.randrange(cfg['vocab']) for _ in range(1+case % 32)]
                expected = logits(cfg, weights, tokens)
                for flag in ([], ['--paged'], ['--recompute']):
                    result = subprocess.run([BIN, 'logits', *flag, str(path), *map(str, tokens)],
                        capture_output=True, text=True, timeout=20, check=True)
                    observed = np.asarray(json.loads(result.stdout)['logits'])
                    self.assertEqual(expected.shape, observed.shape)
                    self.assertTrue(np.isfinite(observed).all())
                    error = np.abs(observed - expected)
                    max_error, rms = float(error.max()), float(np.sqrt(np.mean(error**2)))
                    self.assertLessEqual(max_error, 3e-5, f'case={case}, variant={flag}')
                    self.assertLessEqual(rms, 3e-6, f'case={case}, variant={flag}')
                    maximum = max(maximum, max_error)
                    sum_sq += float(np.sum(error**2)); count += int(error.size)
        print(json.dumps(dict(sequences=100, variants=3, logit_values=count,
            max_absolute_error=maximum, rms_error=(sum_sq/count)**0.5,
            oracle='independent full-prefix float64 over FP32 weights')))

    def test_reference_causal_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'m.bqw'; generate(path)
            cfg, w=load(path)
            a=logits(cfg,w,[1,2,3]); b=logits(cfg,w,[1,2,3,9,8,7])
            np.testing.assert_allclose(a,b[:3],rtol=1e-12,atol=1e-12)


if __name__ == '__main__':
    unittest.main(verbosity=2)
