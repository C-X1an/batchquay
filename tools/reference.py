"""Independent dense, full-prefix mathematical oracle; no native cache/scheduler code.

Uses float64 contractions over FP32 weights. This is a numerical oracle for the
closed architecture, not a replacement for real-checkpoint Transformers checks.
"""
from __future__ import annotations
import struct
from pathlib import Path
import numpy as np


def load(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    header = struct.unpack('<4s8I2f', raw[:44])
    if header[:2] != (b'BQW1', 1):
        raise ValueError('unsupported fixture')
    v, d, f, layers, h, kh, positions, eps, theta = header[2:]
    cfg = dict(vocab=v, dim=d, hidden=f, layers=layers, heads=h, kv_heads=kh,
               max_positions=positions, epsilon=eps, rope_theta=theta)
    data = np.frombuffer(raw, dtype='<f4', offset=44).astype(np.float64)
    cursor = 0

    def take(shape: tuple[int, ...]) -> np.ndarray:
        nonlocal cursor
        n = int(np.prod(shape))
        result = data[cursor:cursor+n].reshape(shape)
        cursor += n
        return result

    weights: dict = {'embed': take((v, d)), 'layers': []}
    kv = kh * d // h
    for _ in range(layers):
        weights['layers'].append(dict(norm1=take((d,)), q=take((d, d)),
            k=take((kv, d)), v=take((kv, d)), o=take((d, d)), norm2=take((d,)),
            gate=take((f, d)), up=take((f, d)), down=take((d, f))))
    weights['norm'] = take((d,))
    if cursor != len(data):
        raise ValueError('unexpected fixture data')
    return cfg, weights


def logits(cfg: dict, w: dict, tokens: list[int]) -> np.ndarray:
    n, h, kh = len(tokens), cfg['heads'], cfg['kv_heads']
    d, hd = cfg['dim'], cfg['dim'] // h
    x = w['embed'][tokens].copy()
    inv_freq = cfg['rope_theta'] ** (-np.arange(0, hd, 2, dtype=np.float64) / hd)
    angles = np.arange(n)[:, None, None] * inv_freq[None, None, :]

    def norm(z: np.ndarray, weight: np.ndarray) -> np.ndarray:
        return z / np.sqrt(np.mean(z*z, axis=-1, keepdims=True) + cfg['epsilon']) * weight

    def rope(z: np.ndarray) -> np.ndarray:
        a, b = np.split(z, 2, axis=-1)
        return np.concatenate((a*np.cos(angles)-b*np.sin(angles),
                               b*np.cos(angles)+a*np.sin(angles)), axis=-1)

    for layer in w['layers']:
        normalized = norm(x, layer['norm1'])
        q = rope((normalized @ layer['q'].T).reshape(n, h, hd))
        k = rope((normalized @ layer['k'].T).reshape(n, kh, hd))
        v = (normalized @ layer['v'].T).reshape(n, kh, hd)
        k, v = np.repeat(k, h//kh, axis=1), np.repeat(v, h//kh, axis=1)
        scores = np.einsum('thd,shd->hts', q, k) / np.sqrt(hd)
        scores = np.where(np.tril(np.ones((n, n), dtype=bool))[None], scores, -np.inf)
        probabilities = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
        probabilities /= probabilities.sum(axis=-1, keepdims=True)
        attended = np.einsum('hts,shd->thd', probabilities, v).reshape(n, d)
        x += attended @ layer['o'].T
        normalized = norm(x, layer['norm2'])
        gate = normalized @ layer['gate'].T
        x += ((gate / (1 + np.exp(-gate))) * (normalized @ layer['up'].T)) @ layer['down'].T
    return norm(x, w['norm']) @ w['embed'].T
