"""Produce a script-free offline inspector from actual native process observations."""
from __future__ import annotations
import argparse
import html
import json
from pathlib import Path
from tools.client import Client
from tools.fixture import generate
from scripts.evidence import identity, manifest


def render(trace: list[dict], source: str) -> str:
    rows=[]
    for i,item in enumerate(trace,1):
        rows.append(f'<tr><th scope="row">{i:02}</th><td>{html.escape(item["label"])}</td>'
                    f'<td><pre>{html.escape(json.dumps(item["response"],indent=2))}</pre></td></tr>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>BatchQuay | An execution you can inspect</title><style>
:root{color-scheme:light dark;--bg:#0d1524;--panel:#172337;--ink:#eef3fb;--muted:#b4c2d9;--line:#344760;--accent:#8fe3d0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1160px;margin:auto;padding:56px 28px}header{border-bottom:1px solid var(--line);padding-bottom:36px}
.kicker{text-transform:uppercase;letter-spacing:.18em;color:var(--accent);font-size:.78rem;font-weight:700}
h1{font-size:clamp(2.8rem,6vw,5rem);line-height:1.06;letter-spacing:-.05em;margin:14px 0 20px}
h2{font-size:1.65rem;margin:36px 0 12px}.lead{max-width:760px;color:var(--muted);font-size:1.2rem}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:30px 0}.card{padding:22px;background:var(--panel);border:1px solid var(--line)}
.card strong{display:block;font-size:1.3rem;margin-bottom:8px}.card p{margin:0;color:var(--muted)}
a{color:var(--accent)}a:focus-visible{outline:3px solid var(--accent);outline-offset:6px}
.notice{border-left:3px solid var(--accent);padding:12px 20px;background:var(--panel)}
table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{text-align:left;vertical-align:top;padding:16px;border-bottom:1px solid var(--line)}
thead{background:var(--panel)}th:first-child{width:6%}th:nth-child(2){width:25%}pre,code{font-family:ui-monospace,monospace;font-size:.84rem;overflow-wrap:anywhere;white-space:pre-wrap}pre{margin:0}
footer{margin-top:36px;color:var(--muted);font-size:.9rem}.skip{position:absolute;left:-9999px}.skip:focus{left:20px;top:10px}
@media(max-width:650px){main{padding:36px 16px}.grid{grid-template-columns:1fr}th,td{padding:10px}th:first-child{width:10%}th:nth-child(2){width:28%}}
@media(prefers-color-scheme:light){:root{--bg:#f5f7fb;--panel:#e8eef6;--ink:#132039;--muted:#425574;--line:#bdcada;--accent:#126b5b}}
</style></head><body><a class="skip" href="#trace">Skip to execution trace</a><main>
<header><div class="kicker">Experimental CPU inference / actual native execution</div><h1>BatchQuay</h1>
<p class="lead">Follow a request from admission to completion. Inspect a denial. Cancel another request and watch its cache return.</p>
<p><a href="#trace">Inspect the trace</a> &nbsp; / &nbsp; <a href="trace.json">Raw observations</a></p></header>
<div class="grid"><section class="card"><strong>Admit deliberately</strong><p>Reserve the full bounded request before execution.</p></section>
<section class="card"><strong>Keep ownership explicit</strong><p>Pages belong to one live request generation.</p></section>
<section class="card"><strong>Make endings terminal</strong><p>Cancellation invalidates work before acknowledgment.</p></section></div>
<p class="notice"><strong>Synthetic-model demonstration.</strong> This report is generated from the real C++ executable using deterministic random weights. It does not establish pretrained-model conformance, useful generated language, production readiness or security certification.</p>
<h2 id="trace" tabindex="-1">An execution you can inspect</h2><table><thead><tr><th scope="col">#</th><th scope="col">Operation</th><th scope="col">Observed response</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><footer>
<p>Source identity: <code>'''+html.escape(source)+'''</code></p><p>No JavaScript, external assets, model API, network listener or fabricated application screenshot. Owner labels are trusted-controller inputs, not authentication.</p></footer></main></body></html>'''


def produce(out: Path) -> dict:
    out.mkdir(parents=True,exist_ok=True)
    model=out/'tiny.bqw';model_info=generate(model)
    trace=[]
    with Client(model,pages=4,page_tokens=4) as c:
        def record(label: str,response: dict) -> dict:
            trace.append(dict(label=label,response=response));return response
        a=record('Admit alpha',c.submit('alpha','a',[1,2],3))
        b=record('Admit beta',c.submit('beta','b',[8,9,10],3))
        denial=record('Deny over-capacity work',c.submit('gamma','c',[4],2))
        record('Prefill one bounded round',c.command('STEP'))
        cancelled=record('Cancel beta',c.command('CANCEL','beta','b',b['generation']))
        for i in range(3):
            record(f'Decode round {i+1}',c.command('STEP'))
        stats=record('All terminal resources reclaimed',c.command('STATUS'))
    if a['event']!='accepted' or denial.get('code')!='E_CAPACITY' or cancelled['event']!='cancelled':
        raise RuntimeError('demo observations did not establish intended paths')
    if stats['live'] or stats['reserved'] or stats['physical']:
        raise RuntimeError('demo leaked cache capacity')
    source=identity(manifest())
    (out/'trace.json').write_text(json.dumps(dict(source_sha256=source,model=model_info,trace=trace),indent=2)+'\n')
    (out/'report.html').write_text(render(trace,source))
    return dict(report=str(out/'report.html'),source_sha256=source,observed=['admitted','denied','cancelled','finished','reclaimed'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('.local-runs/demo'))
    print(json.dumps(produce(p.parse_args().output),indent=2))
