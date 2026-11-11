#!/usr/bin/env python3
"""Cache OCR search text for user-supplied scanned books; verify images before import."""
import concurrent.futures,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];inv=ROOT/'catalog/research/local-pdf-inventory.json';data=json.loads(inv.read_text());base=ROOT/'.cache/research/local-pdfs';tool=ROOT/'.cache/tools/ocr'
env=dict(os.environ,LD_LIBRARY_PATH=str(tool/'usr/lib/x86_64-linux-gnu'),TESSDATA_PREFIX=str(tool/'usr/share/tesseract-ocr/5/tessdata'),OMP_THREAD_LIMIT='1')
for r in data['pdfs']:
 if r.get('ocr_text_cache') and (ROOT/r['ocr_text_cache']).is_file():continue
 if r['extracted_characters'] >= 1000:continue
 folder=base/'ocr'/r['sha256'];folder.mkdir(parents=True,exist_ok=True)
 def page(n):
  stem=folder/f'page-{n:03}';out=stem.with_suffix('.txt')
  if not out.exists():
   subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-r','135','-png','-singlefile',str(ROOT/r['file']),str(stem)],check=True,capture_output=True)
   temporary=stem.with_name(stem.name+'-pending')
   subprocess.run([str(tool/'usr/bin/tesseract'),str(stem.with_suffix('.png')),str(temporary),'--psm','1'],env=env,check=True,capture_output=True)
   temporary.with_suffix('.txt').replace(out)
   stem.with_suffix('.png').unlink()
  return n
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
  for ix,n in enumerate(ex.map(page,range(1,r['pages']+1))):
   if (ix+1)%10==0:print(Path(r['file']).name,ix+1,'/',r['pages'],flush=True)
 text='\f'.join((folder/f'page-{n:03}.txt').read_text() for n in range(1,r['pages']+1))+'\f';out=base/(r['sha256']+'-ocr.txt');out.write_text(text);r['ocr_text_cache']=str(out.relative_to(ROOT));r['ocr_search_text_requires_visual_verification']=True
 latest=json.loads(inv.read_text())
 current=next(source for source in latest['pdfs'] if source['sha256']==r['sha256'])
 current.update(ocr_text_cache=r['ocr_text_cache'],ocr_search_text_requires_visual_verification=True)
 temporary_inventory=inv.with_suffix('.tmp')
 temporary_inventory.write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n')
 temporary_inventory.replace(inv)
 print('OCR search cache ready:',r['file'],len(text),flush=True)
