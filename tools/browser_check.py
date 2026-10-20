"""Optional browser QA of generated HTML; actual browser execution, not image simulation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main() -> None:
    from playwright.sync_api import sync_playwright
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('.local-runs/demo'))
    p.add_argument('--executable',default='/usr/bin/chromium');args=p.parse_args()
    content=(args.directory/'report.html').read_text()
    rows=[]
    with sync_playwright() as engine:
        browser=engine.chromium.launch(executable_path=args.executable,headless=True)
        for name,width in [('desktop',1440),('mobile',390)]:
            page=browser.new_page(viewport={'width':width,'height':900})
            page.set_content(content,wait_until='load')
            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            if overflow: raise AssertionError('horizontal overflow')
            if page.locator('script,iframe,object,embed').count(): raise AssertionError('active embedded content')
            if page.locator('[src^="http"],link[href^="http"]').count(): raise AssertionError('external resources')
            page.keyboard.press('Tab');focused=page.locator(':focus').get_attribute('href')
            if focused!='#trace': raise AssertionError('skip link is not keyboard reachable')
            page.keyboard.press('Enter')
            page.screenshot(path=str(args.directory/f'{name}.png'),full_page=True)
            rows.append(dict(view=name,width=width,horizontal_overflow=overflow,first_focus=focused))
            page.close()
        browser.close()
    report=dict(status='PASS',mode='Owned HTML loaded through set_content; filesystem navigation is restricted in author browser. DOM/layout/keyboard tested, not an externally hosted URL.',views=rows)
    (args.directory/'browser-review.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
