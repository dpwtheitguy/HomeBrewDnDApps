#!/usr/bin/env python3
"""Save public D&D Beyond listing metadata only; no detail pages or paid content."""
import html,json,re,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'catalog/raw/dndbeyond-public-index'
BASE='https://www.dndbeyond.com/magic-items?filter-partnered-content=f'

def parse(text):
    rows=[]
    blocks=re.split(r'<div class="info"[^>]*data-type="magic-items"',text)[1:]
    for block in blocks:
        slug=re.search(r'data-slug="([^"]+)"',block)
        link=re.search(r'<a class="link" href="(/magic-items/[^"?]+)"[^>]*>(.*?)</a>',block,re.S)
        if not slug or not link: continue
        def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>','',s))).strip()
        def field(cls):
            m=re.search(r'<span class="'+cls+r'">(.*?)</span>',block,re.S)
            return clean(m[1]) if m else None
        images=sorted(set(html.unescape(x) for x in re.findall(r'https://www\.dndbeyond\.com/avatars/[^\s\'"<>]+',block)))
        rows.append({'slug':slug[1],'name':clean(link[2]),'url':'https://www.dndbeyond.com'+link[1],
                     'rarity':field('rarity'),'type':field('type'),'subtype':field('subtype'),
                     'requires_attunement':'i-req-attunement' in block,
                     'image_reference_urls':images,'status':'public-index-metadata-only'})
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    def fetch(page):
        path=OUT/f'page-{page:03}.json'
        if path.exists(): return json.loads(path.read_text())
        req=urllib.request.Request(BASE+f'&page={page}',headers={'User-Agent':'FighterCatalogResearch/0.1 (public item-name index)'})
        with urllib.request.urlopen(req,timeout=45) as r: text=r.read().decode()
        rows=parse(text)
        if not rows: raise RuntimeError(f'No listing metadata on page {page}; stopping')
        last=max([int(x) for x in re.findall(r'/magic-items\?[^"<>]*?page=(\d+)',text)] or [page])
        data={'page':page,'last_page':last,'items':rows}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');time.sleep(.5)
        return data
    first=fetch(1); total=first['last_page']; rows=[]
    for page in range(1,total+1):
        data=fetch(page);rows.extend(data['items']);print(f'Public listing {page}/{total}',flush=True)
    unique={r['slug']:r for r in rows}
    if len(unique)!=len(rows): raise RuntimeError('Pagination duplicates; inspect source drift before combining')
    (OUT/'items.json').write_text(json.dumps(list(unique.values()),ensure_ascii=False,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps({'url':BASE,'pages':total,'records':len(unique),
        'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'coverage':'Public magic-item list with partnered-content filter disabled; not a full sourcebook export. Editions and book provenance are not exposed by these cards and remain unknown.',
        'content':'Names, type, rarity, attunement flag, source links, image URL references only. No detail descriptions or downloaded artwork.'},indent=2)+'\n')
if __name__=='__main__':main()
