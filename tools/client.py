"""Bounded test/demo client for the real local child process. Not a network adapter."""
from __future__ import annotations
import json
import os
import queue
import subprocess
import threading
from pathlib import Path


class Client:
    def __init__(self, model: Path, pages: int = 64, page_tokens: int = 4,
                 live: int = 16, chunk: int = 4) -> None:
        binary = str(Path(os.environ.get('BQ_BINARY', 'build/batchquay')).resolve())
        self.proc = subprocess.Popen([binary, 'serve', str(model), str(pages),
            str(page_tokens), str(live), str(chunk)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.responses: queue.Queue[bytes | None] = queue.Queue(maxsize=64)
        self.reader = threading.Thread(target=self._read_responses,daemon=True)
        self.reader.start()
        try:
            greeting = self.read()
            if greeting.get('event') != 'hello' or greeting.get('protocol') != 1:
                raise RuntimeError('invalid native greeting')
            self.session = greeting['session']
        except BaseException:
            self.close()
            raise

    def _read_responses(self) -> None:
        assert self.proc.stdout is not None
        while True:
            line=self.proc.stdout.readline(2**20+1)
            if not line:
                self.responses.put(None);return
            self.responses.put(line)

    def read(self, timeout: float = 10.0) -> dict:
        try:
            line=self.responses.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError('native process did not respond') from exc
        if line is None:
            raise RuntimeError('native process exited before response')
        if len(line)>2**20 or not line.endswith(b'\n'):
            raise RuntimeError('native response exceeded limit')
        response=json.loads(line)
        if hasattr(self,'session') and response.get('session')!=self.session:
            raise RuntimeError('native response has wrong or missing session')
        return response

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

    def __enter__(self) -> 'Client':
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
