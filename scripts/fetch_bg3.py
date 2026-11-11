#!/usr/bin/env python3
"""Fetch BG3 wiki item facts, excluding descriptions, quotes and game artwork.
Uses permitted MediaWiki query endpoints, not restricted arbitrary Cargo queries.
Caches projected facts only. Re-run with --refresh to re-fetch existing batches.
"""
import argparse, hashlib, json, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalog/raw/bg3-wiki'
API = 'https://bg3.wiki/w/api.php'
TEMPLATES = {'weapon': 'Template:Weapon page', 'equipment': 'Template:Equipment page', 'misc': 'Template:Misc item page'}
ALLOWED = set('name,type,category,rarity,weight kg,weight lb,price,price honour,armour class,armour class bonus,armour type,armour,proficiency,damage,damage type,damage2,damage2 type,versatile damage,enchantment,handedness,melee or ranged,range,uid,uuid,icon,image,controller icon,finesse,light,thrown,two-handed,versatile,heavy,loading,ammunition,reach,dippable,story,unobtainable,where to find location'.split(','))

def request(params):
    url = API + '?' + urllib.parse.urlencode({'format':'json', 'formatversion':2, **params})
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'FighterCatalogResearch/0.1 (local item catalog; low request rate)'})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.load(r)
            if 'error' in data: raise RuntimeError(str(data['error']))
            time.sleep(.25)
            return data
        except (OSError, ValueError):
            if attempt == 2: raise
            time.sleep(2 ** attempt)

def split_top(text, delimiter='|'):
    parts, start, braces, links, i = [], 0, 0, 0, 0
    while i < len(text):
        two = text[i:i+2]
        if two == '{{': braces += 1; i += 2; continue
        if two == '}}': braces -= 1; i += 2; continue
        if two == '[[': links += 1; i += 2; continue
        if two == ']]': links -= 1; i += 2; continue
        if text[i] == delimiter and not braces and not links:
            parts.append(text[start:i]); start = i + 1
        i += 1
    return parts + [text[start:]]

def extract_templates(text, template_names, allowed):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    result, stack, i = [], [], 0
    while i < len(text)-1:
        if text[i:i+2] == '{{': stack.append(i+2); i += 2; continue
        if text[i:i+2] == '}}' and stack:
            start = stack.pop()
            chunks = split_top(text[start:i])
            name = re.sub(r'[ _]', '', chunks[0].strip()).lower()
            if name in template_names:
                facts = {}
                for chunk in chunks[1:]:
                    if '=' not in chunk: continue
                    key, value = chunk.split('=',1)
                    key = key.strip().lower()
                    if allowed(key) and value.strip(): facts[key] = value.strip()
                result.append({'template':name,'facts':facts})
            i += 2; continue
        i += 1
    return result

def extract(text):
    return extract_templates(text, {'weaponpage', 'equipmentpage', 'miscitempage'}, ALLOWED.__contains__)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--refresh',action='store_true'); args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    def save(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    pages={}
    for kind, template in TEMPLATES.items():
        path=OUT/f'{kind}-pages.json'
        if path.exists() and not args.refresh: rows=json.loads(path.read_text())
        else:
            rows=[]; continuation={}
            while True:
                d=request({'action':'query','list':'embeddedin','eititle':template,'einamespace':0,'eilimit':500,**continuation})
                rows.extend(d['query']['embeddedin'])
                if 'continue' not in d: break
                continuation=d['continue']
            save(path,rows)
        print(f'{kind}: {len(rows)} pages',flush=True)
        for row in rows: pages.setdefault(row['pageid'], {**row,'kinds':[]})['kinds'].append(kind)
    ids=sorted(pages)
    results=[]
    for offset in range(0,len(ids),50):
        batch=ids[offset:offset+50]
        key=hashlib.sha256(','.join(map(str,batch)).encode()).hexdigest()[:16]
        path=OUT/f'batch-{key}.json'
        if path.exists() and not args.refresh: rows=json.loads(path.read_text())
        else:
            d=request({'action':'query','prop':'revisions','pageids':'|'.join(map(str,batch)),'rvprop':'ids|timestamp|content','rvslots':'main'})
            rows=[]
            for page in d['query']['pages']:
                if 'missing' in page: raise RuntimeError(f'Missing page: {page}')
                rev=page['revisions'][0]
                rows.append({'pageid':page['pageid'],'title':page['title'],'revid':rev['revid'],'timestamp':rev['timestamp'],'templates':extract(rev['slots']['main']['content'])})
            save(path,rows)
        results.extend(rows)
        print(f'facts: {min(offset+50,len(ids))}/{len(ids)} pages',flush=True)
    for row in results: row['kinds']=pages[row['pageid']]['kinds']
    save(OUT/'items.json',sorted(results,key=lambda x:x['pageid']))
    save(OUT/'manifest.json',{'api':API,'templates':TEMPLATES,'page_count':len(results),'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'projection':'Whitelisted factual fields and image filenames only; no descriptions, quotes, page prose or image binaries.','policy':'https://bg3.wiki/wiki/bg3wiki:Copyrights','status':'research-metadata; not a tabletop adaptation or art license'})
    print('Saved projected item facts',flush=True)
if __name__=='__main__': main()
