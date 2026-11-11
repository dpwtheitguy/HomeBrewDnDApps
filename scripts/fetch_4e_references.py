#!/usr/bin/env python3
"""Read name/publication/slot facts for AV1/AV2. Never export power text.
Static source pages are cached outside the artifact. Stop on access/rate denial.
"""
import concurrent.futures,hashlib,json,re,threading,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parents[1];BASE='https://www.dyasdesigns.com/dnd4e/static-site/item/';CACHE=ROOT/'.cache/research/4e';CACHE.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'catalog/raw/setting-reference-indexes';OUT.mkdir(parents=True,exist_ok=True)
lock=threading.Lock();last=[0.0];stop=threading.Event()
def clean(v):return re.sub(r'\s+',' ',v).strip()
def page(url):
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
    if path.exists():return html.fromstring(path.read_bytes())
    if stop.is_set():raise RuntimeError('Access/rate denial stopped uncached requests')
    with lock:
        delay=.25-(time.monotonic()-last[0])
        if delay>0:time.sleep(delay)
        last[0]=time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FighterCatalogResearch/0.1 (names, publication references and slots only)'}),timeout=20) as r:b=r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401,403,429):stop.set()
        raise
    path.write_bytes(b);return html.fromstring(b)
def main():
    tree=page(BASE+'index.html');links=[]
    for a in tree.xpath('//a[@href]'):
        href=a.get('href','')
        if href.startswith('./item'):
            # First text node is the title; the preview snippet is deliberately excluded.
            title=clean(a.text or '')
            if not title:
                title_nodes=a.xpath('./h2|./h3|./strong|./div[1]');title=clean(title_nodes[0].text_content()) if title_nodes else ''
            links.append((urllib.parse.urljoin(BASE,href),title))
    results=[];failures=[];started=time.monotonic()
    def inspect(pair):
        url,title=pair
        try:
            t=page(url);published=[]
            entries=t.xpath('//main/article')
            if not entries:return None
            entry=entries[0]
            for e in entry.xpath('./p[@class="publishedIn"]'):
                text=clean(e.text_content())
                if text.startswith('Published in '):published.append(text)
            publication=' '.join(published)
            if "Adventurer's Vault" not in publication:return None
            headings=entry.xpath('./h1');name=clean(headings[0].text_content()) if headings else title
            name=re.sub(r'\s*Level\s+\d.*$','',name).strip()
            # Slot/type labels are functional metadata only, not descriptions or powers.
            body=clean(' '.join(p.text_content() for p in entry.xpath('./p[@class="mistat"]')));kind='wondrous-item'
            if headings and headings[0].get('class')=='miset':
                name=re.sub(r'(?:Heroic|Paragon|Epic) Tier$', '', name).strip()
                kind='item-set'
            for token,typ in [('Waist Slot','belt'),('Feet Slot','boots'),('Hands Slot','gloves'),('Head Slot','helmet'),('Neck Slot','amulet'),('Arms Slot','wondrous-item'),('Weapon:','weapon'),('Armor:','armor'),('Alchemical Item:','consumable')]:
                if kind!='item-set' and token in body:kind=typ;break
            return {'name':name,'source_type':kind,'url':url,'evidence_kind':'fan-compendium-publication-index','published_in':publication,'original_book_verified':False,'normalization_note':'Removed displayed level/rarity from the item name; source level and enhancement variants are not expanded into separate items.'}
        except Exception as e:return {'failed_url':url,'error':str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        for n,result in enumerate(ex.map(inspect,links),1):
            if result and 'failed_url' in result:failures.append(result)
            elif result:results.append(result)
            if n%100==0:print(json.dumps({'inspected':n,'total':len(links),'AV_matches':len(results),'failures':len(failures),'elapsed_seconds':round(time.monotonic()-started)}),flush=True)
    summary={'pages_in_public_index':len(links),'matches':len(results),'failures':failures,'coverage':'Reference index pass only; no original PDF or rule mechanics audit.'}
    (CACHE/'pass-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    for num in (1,2):
        rows=[r for r in results if ("Adventurer's Vault 2" in r['published_in'])==(num==2)]
        # Source records remain level-independent: no enhancement/level cross-product.
        rows=list({(r['name'].casefold(),r['source_type']):r for r in rows}.values())
        key='adventurers-vault-'+str(num)+'-reference'
        output=OUT/(key+'.json')
        if output.exists():
            existing=json.loads(output.read_text())['records']
            verified={r['name'].casefold():r for r in existing if r['evidence_kind']=='publication-page-reference'}
            table_aliases={r['url']:r for r in existing if r.get('source_table_locator')}
            rows=[r for r in rows if r['name'].casefold() not in verified]
            for row in rows:
                prior=table_aliases.get(row['url'])
                if prior and prior['name']==row['name']:
                    row.update(aliases=prior['aliases'],source_table_locator=prior['source_table_locator'])
            rows.extend(verified.values())
        data={'source_id':key,'label':'Adventurer’s Vault'+(' 2' if num==2 else ''),'entity_id':'publication:adventurers-vault-'+str(num),'ruleset':'dnd-4e','source_url':BASE+'index.html','retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Selected public compendium entries reporting this publication; names/slots/publication references only. Not every sourcebook entry is guaranteed to be in the mirror. Level/enhancement variants are not expanded. All 2024 adaptation remains pending.','records':rows}
        output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(key,len(rows),flush=True)
if __name__=='__main__':main()
