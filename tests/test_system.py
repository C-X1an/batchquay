from __future__ import annotations
import json
import os
import random
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from tools.client import Client
from tools.fixture import generate

BIN = str(Path(os.environ.get('BQ_BINARY', 'build/batchquay')).resolve())


class SystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.model = Path(self.tmp.name)/'tiny.bqw'
        generate(self.model)

    def test_interleaving_matches_isolated_execution(self) -> None:
        def run(prompts: dict) -> dict:
            with Client(self.model) as c:
                result = {k: [] for k in prompts}
                for owner, prompt in prompts.items():
                    self.assertEqual(c.submit(owner, 'r', prompt, 8)['event'], 'accepted')
                for _ in range(20):
                    for e in c.command('STEP')['events']:
                        if e['event'] == 'token':
                            result[e['owner']].append(e['token'])
                    if c.command('STATUS')['live'] == 0:
                        break
                stats = c.command('STATUS')
                self.assertEqual((stats['reserved'], stats['physical'], stats['live']), (0,0,0))
                for tokens in result.values():
                    self.assertEqual(len(tokens),8)
                return result
        together = run({'a':[1,2,3], 'b':[8,9,10,11,12,13,14]})
        self.assertEqual(together['a'],run({'a':[1,2,3]})['a'])
        self.assertEqual(together['b'],run({'b':[8,9,10,11,12,13,14]})['b'])

    def test_cancel_and_stale_generation(self) -> None:
        with Client(self.model) as c:
            g = c.submit('a','r',[1,2,3],8)['generation']
            c.command('STEP')
            self.assertEqual(c.command('CANCEL','a','r',g+1)['code'],'E_STALE')
            self.assertEqual(c.command('CANCEL','other','r',g)['code'],'E_NOT_FOUND')
            self.assertEqual(c.command('CANCEL','a','r',g)['event'],'cancelled')
            for _ in range(10):
                self.assertEqual(c.command('STEP')['events'],[])
            newer = c.submit('a','r',[5],1)['generation']
            self.assertGreater(newer,g)
            self.assertEqual(c.command('CANCEL','a','r',g)['code'],'E_STALE')
            self.assertEqual(c.command('STATUS')['live'],1)

    def test_admission_and_maximum_position_bound(self) -> None:
        with Client(self.model,pages=16,page_tokens=16) as c:
            self.assertEqual(c.submit('a','r',[1]*128,128)['event'],'accepted')
            before=c.command('STATUS')
            self.assertEqual(before['reserved'],16)
            self.assertEqual(c.submit('b','r',[2],1)['code'],'E_CAPACITY')
            self.assertEqual(c.command('STATUS'),before)
            self.assertEqual(c.submit('b','r',[2]*128,129)['code'],'E_LIMIT')
            for _ in range(160):
                c.command('STEP')
            self.assertEqual(c.command('STATUS')['reserved'],0)

    def test_malformed_protocol_finite_campaign(self) -> None:
        rng=random.Random(101)
        with Client(self.model) as c:
            lines=['', 'HELLO 2', 'HELLO 1 extra', 'BOGUS '+c.session,
                'STATUS '+c.session+' extra', 'X'*9000,
                f'SUBMIT {c.session} bad"id r 1 1 2',
                f'SUBMIT {c.session} a r 1 18446744073709551616',
                f'SUBMIT {c.session} a r 1 2 3',
                f'SUBMIT {c.session} a r -1 1 3',
                f'SUBMIT {c.session} a r 1 1 99',
                f'SUBMIT {c.session} a r 1 1 3 extra']
            lines += [f'SUBMIT {c.session} a r 1 {rng.randrange(257,100000)} 1' for _ in range(200)]
            for line in lines:
                self.assertEqual(c.raw(line)['event'],'error',line[:80])
                self.assertEqual(c.command('STATUS')['live'],0)
            self.assertEqual(c.submit('a','good',[1],1)['event'],'accepted')

    def test_kill_restart_rejects_old_session(self) -> None:
        with Client(self.model) as c:
            c.submit('a','r',[1],8);c.command('STEP');old=c.session
            c.proc.kill();c.proc.wait(timeout=5)
        with Client(self.model) as d:
            self.assertNotEqual(old,d.session)
            self.assertEqual(d.raw('STEP '+old)['code'],'E_SESSION')
            self.assertEqual(d.command('STATUS')['live'],0)

    def test_loader_rejects_structural_and_nonfinite_damage(self) -> None:
        raw=self.model.read_bytes()
        mutations=[b'',raw[:43],raw[:-4],raw+b'xxxx',b'BAD!'+raw[4:]]
        for offset,number in [(4,2),(8,2**32-1),(12,0),(24,0),(28,3)]:
            m=bytearray(raw);struct.pack_into('<I',m,offset,number);mutations.append(bytes(m))
        for f in [float('nan'),float('inf'),float('-inf')]:
            m=bytearray(raw);struct.pack_into('<f',m,44,f);mutations.append(bytes(m))
        for i,data in enumerate(mutations):
            path=Path(self.tmp.name)/f'bad{i}.bqw';path.write_bytes(data)
            result=subprocess.run([BIN,'logits',str(path),'1'],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')
            self.assertIn(result.stderr.strip(),{'E_MODEL','E_VERSION'})

    def test_invalid_cli_token_rejected(self) -> None:
        for value in ['-1','37','1junk','18446744073709551616']:
            result=subprocess.run([BIN,'logits',str(self.model),value],capture_output=True,timeout=5)
            self.assertEqual(result.returncode,2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
