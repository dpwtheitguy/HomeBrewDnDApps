#!/usr/bin/env python3
"""Read publisher-hosted public samples only; no account/paywall workarounds."""
import hashlib,json,re,sys,time,urllib.request,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1];cache=ROOT/'.cache/research/gazetteers';cache.mkdir(parents=True,exist_ok=True)
report=[]
for a in fetch('https://pandius.com/dthrurpg.html').xpath('//a[@href]'):
 label=clean(a.text_content());match=re.match(r'GAZ(\d+)\b',label);pid=re.search(r'/product/(\d+)/',a.get('href'))
 if not match or not pid or not 1<=int(match[1])<=14:continue
 n=int(match[1]);url=f'https://d1vzi28wh99zvq.cloudfront.net/pdf_previews/{pid[1]}-sample.pdf';dest=cache/f'gaz{n:02}-publisher-sample.pdf';row={'book_code':'GAZ'+str(n),'label':label,'product_id':pid[1],'preview_url':url,'status':'pending'}
 try:
  if not dest.exists():
   with urllib.request.urlopen(url,timeout=35) as r:body=r.read()
   if not body.startswith(b'%PDF'):raise ValueError('Not a PDF response')
   dest.write_bytes(body);time.sleep(.25)
  subprocess.run(['pdftotext','-layout',str(dest),str(dest.with_suffix('.txt'))],check=True,capture_output=True)
  row.update(status='sample-fetched-text-extracted-not-yet-visually-verified',sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),local_cache=str(dest.relative_to(ROOT)),sample_pages=len(dest.with_suffix('.txt').read_text().split('\f'))-1)
 except Exception as e:
  row.update(status='unavailable',error=str(e),http_status=getattr(e,'code',None))
 report.append(row);print(row['book_code'],row['status'],row.get('sample_pages',''),flush=True)
 if row.get('http_status') in [401,403,429]:break
(cache/'preview-fetch-report.json').write_text(json.dumps(report,indent=2)+'\n')
