"""Bounded test/demo client for the real local child process. Not a network adapter."""
from __future__ import annotations
import json
import os
import selectors
import subprocess
from pathlib import Path


class Client:
    def __init__(self, model: Path, pages: int = 64, page_tokens: int = 4,
                 live: int = 16, chunk: int = 4) -> None:
        binary = str(Path(os.environ.get('BQ_BINARY', 'build/batchquay')).resolve())
        self.proc = subprocess.Popen([binary, 'serve', str(model), str(pages),
            str(page_tokens), str(live), str(chunk)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''
        try:
            greeting = self.read()
            if greeting.get('event') != 'hello' or greeting.get('protocol') != 1:
                raise RuntimeError('invalid native greeting')
            self.session = greeting['session']
        except BaseException:
            self.close()
            raise

    def read(self, timeout: float = 10.0) -> dict:
        import time
        end = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = end-time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError('native process did not respond')
            part = os.read(self.proc.stdout.fileno(), 65536)
            if not part:
                raise RuntimeError('native process exited before response')
            self.buffer += part
            if len(self.buffer) > 2**20:
                raise RuntimeError('native response exceeded limit')
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)

    def raw(self, line: str) -> dict:
        self.proc.stdin.write((line+'\n').encode('utf-8'))
        self.proc.stdin.flush()
        return self.read()

    def command(self, operation: str, *args: object) -> dict:
        return self.raw(' '.join([operation, self.session, *map(str, args)]))

    def submit(self, owner: str, request: str, tokens: list[int], output: int) -> dict:
        return self.command('SUBMIT', owner, request, output, len(tokens), *tokens)

    def close(self) -> None:
        if getattr(self, 'proc', None) is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill(); self.proc.wait(timeout=5)
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream is not None:
                    stream.close()
        if getattr(self, 'selector', None) is not None:
            self.selector.close()

    def __enter__(self) -> 'Client':
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
