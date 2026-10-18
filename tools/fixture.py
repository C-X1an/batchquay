"""Generate reproducible synthetic weights. No trained-model capability is implied."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path

DEFAULT = dict(vocab=37, dim=16, hidden=32, layers=2, heads=4, kv_heads=2,
               max_positions=256, epsilon=1e-5, rope_theta=10000.0)


def generate(path: Path, seed: int = 1729, config: dict | None = None) -> dict:
    cfg = dict(DEFAULT if config is None else config)
    d, f, layers = cfg['dim'], cfg['hidden'], cfg['layers']
    kv = cfg['kv_heads'] * (d // cfg['heads'])
    rng = random.Random(seed)
    values: list[float] = []

    def tensor(count: int, norm: bool = False) -> None:
        values.extend([1.0] * count if norm else [rng.gauss(0, 0.12) for _ in range(count)])

    tensor(cfg['vocab'] * d)
    for _ in range(layers):
        tensor(d, True)
        for n in (d*d, kv*d, kv*d, d*d):
            tensor(n)
        tensor(d, True)
        for n in (f*d, f*d, d*f):
            tensor(n)
    tensor(d, True)
    header = struct.pack('<4s8I2f', b'BQW1', 1, cfg['vocab'], d, f, layers,
                         cfg['heads'], cfg['kv_heads'], cfg['max_positions'],
                         cfg['epsilon'], cfg['rope_theta'])
    data = header + struct.pack(f'<{len(values)}f', *values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return dict(kind='SYNTHETIC_RANDOM_WEIGHTS', seed=seed, config=cfg,
                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('.local-runs/tiny.bqw'))
    p.add_argument('--seed', type=int, default=1729)
    args = p.parse_args()
    print(json.dumps(generate(args.output, args.seed), indent=2))


if __name__ == '__main__':
    main()
