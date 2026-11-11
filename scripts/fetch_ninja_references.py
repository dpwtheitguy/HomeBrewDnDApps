#!/usr/bin/env python3
"""Collect public names/types/links only. Requires lxml; never executes upstream JS.
Use the bundled Python runtime on this host. Cached HTML remains outside exports.
"""
import concurrent.futures,hashlib,html as html_std,json,re,subprocess,time,urllib.parse,urllib.request
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parents[1]; CACHE=ROOT/'.cache/research/ninja';CACHE.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'catalog/raw/game-reference-indexes';OUT.mkdir(parents=True,exist_ok=True)
UA='FighterCatalogResearch/0.1 (public item names and source links only)'
def clean(s):return re.sub(r'\s+',' ',s).strip()
def fetch(url):
 path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
 if not path.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=25) as r:body=r.read()
  path.write_bytes(body);time.sleep(.15)
 return html.fromstring(path.read_bytes())
def record(name,kind,url,**kw):return {'name':clean(name),'source_type':kind,'url':url,**kw}
def save(key,rows,**meta):
 # Within-source name/type identity; repeated IDs become variants rather than rows.
 grouped={}
 for row in rows:
  k=(row['name'].casefold(),row['source_type'].casefold())
  if k not in grouped:grouped[k]=row
  elif row.get('upstream_ids'):grouped[k].setdefault('upstream_ids',[]).extend(row['upstream_ids'])
 rows=list(grouped.values())
 data={'source_id':key,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'content':'Names, types, source links and variant identifiers only; no copied descriptions, powers, flavor, art or prices.','records':rows,**meta}
 (OUT/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(key,len(rows),flush=True)
def nioh():
 url='https://liukang1080.github.io/gamewiki/nioh2/tools/smithing_texts/weapon_texts.html';tree=fetch(url);rows=[]
 for table in tree.xpath('//table'):
  heading=table.xpath('preceding::h2[1]')
  if not heading:continue
  kind=clean(heading[0].text_content()).replace(' Smithing Texts','')
  for tr in table.xpath('.//tr'):
   cells=tr.xpath('./td')
   # Continuation rows have only enemy/mission columns: never import those as weapons.
   if len(cells)!=3:continue
   name=clean(cells[0].text_content())
   if name and name!='-':rows.append(record(name,kind,url,evidence_kind='fan-smithing-index',ninja_relevance='direct' if any(x in kind for x in ['Kusarigama','Tonfa','Fists']) or any(x in name.casefold() for x in ['ninja','shinobi','hayabusa','jonin','chunin']) else 'adjacent-martial'))
 save('nioh-2-reference',rows,game_id='nioh-2',coverage='Weapons attested by smithing-text names, not every weapon or armor set. Smithing texts themselves and set-piece combinations are not counted.',source_url=url)
def sekiro():
 url='https://sekiroshadowsdietwice.wiki.fextralife.com/Prosthetic+Tools';t=fetch(url); rows=[]
 for a in t.xpath('//h3[contains(@class,"special")]//a[@title] | //li[contains(text(),"Upgrades:")]//a[@title]'):
  name=a.get('title');href=a.get('href')
  if name and href:rows.append(record(name,'prosthetic-tool',urllib.parse.urljoin(url,href),evidence_kind='fan-tool-index',ninja_relevance='direct'))
 save('sekiro-reference',rows,game_id='sekiro',source_url=url,coverage='Prosthetic-tool table only; upgraded tools retain distinct names, not every crafting combination.')
def diablo2():
 base='https://classic.battle.net';index=base+'/diablo2exp/items/weaponsandarmor.shtml';rows=[];errors=[]
 t=fetch(index)
 urls=sorted({urllib.parse.urljoin(index,a.get('href')) for a in t.xpath('//a[@href]') if re.search(r'/items/(normal|exceptional|elite)/(?!u)[a-z]+\.shtml$',urllib.parse.urljoin(index,a.get('href')))})
 def page(url):
  try:
   tree=fetch(url); found=[]
   for td in tree.xpath('//td[img]'):
    names=td.xpath('.//b')
    for e in names:
     name=clean(e.text_content())
     if name:found.append(record(name,url.rsplit('/',1)[-1][:-6],url,evidence_kind='official-base-item-table',tier=url.split('/')[-2],ninja_relevance='direct' if 'katars.shtml' in url else 'backlog'))
   return found
  except Exception as e:errors.append({'url':url,'error':str(e)});return []
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for found in ex.map(page,urls):rows.extend(found)
 alpha=base+'/diablo2exp/items/uniques-alpha.shtml';tree=fetch(alpha)
 for a in tree.xpath('//a[@href]'):
  href=a.get('href');name=clean(a.text_content())
  if name and re.search(r'/items/(normal|exceptional|elite)/u[a-z]+\.shtml',href):rows.append(record(name,href.rsplit('/',1)[-1][1:-6],urllib.parse.urljoin(alpha,href),evidence_kind='official-unique-name-index',quality='unique',ninja_relevance='direct' if 'uassassin' in href else 'backlog'))
 save('diablo-2-reference',rows,game_id='diablo-2',source_url=index,coverage='Official Arreat Summit base-item tables and alphabetic unique-name index; historical LoD-era reference, not current Resurrected patch coverage. No affix products or upgraded unique instances generated.',pages_attempted=len(urls)+1,failures=errors)
def diablo3():
 repo=ROOT/'.cache/upstream/d3planner';commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip();rows=[]
 for path in sorted((repo/'scripts/data').glob('item_*.js')):
  if path.stem in ['item_cache','item_classes','item_icons']:continue
  for match in re.finditer(r'^  \{\s*\n(.*?)^  \},?',path.read_text(),re.M|re.S):
   block=match[1]
   def field(key):
    m=re.search(r'^    '+key+r':\s*("(?:[^"\\]|\\.)*")',block,re.M)
    return json.loads(m[1]) if m else None
   iid,name,kind=field('id'),field('name'),field('type')
   if iid and name and kind:rows.append(record(name,kind,f'https://github.com/d07RiV/d3planner/blob/{commit}/scripts/data/{path.name}',upstream_ids=[iid],quality=field('quality'),evidence_kind='pinned-fan-planner-metadata',ninja_relevance='direct' if kind=='fistweapon' else 'backlog'))
 save('diablo-3-reference',rows,game_id='diablo-3',source_url='https://github.com/d07RiV/d3planner',upstream_commit=commit,coverage='Planner named equipment, grouped by name and type across legacy/patch IDs. No current-patch completeness claimed. Apache code license does not relicense Blizzard names/art.',collapsed_variant_ids=sum(len(r.get('upstream_ids',[])) for r in rows))
if __name__=='__main__':
 nioh();sekiro();diablo3();diablo2()

def backlog_indexes():
    url='https://baldursgateee.th.gl/db/inventory';tree=fetch(url);parts=[];rows=[]
    for script in tree.xpath('//script'):
        for m in re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)',script.text or ''):parts.append(json.loads(m[1]))
    payload=''.join(parts); candidates=[]
    for m in re.finditer(r'"items":\[',payload):
        try:
            data,_=json.JSONDecoder().raw_decode(payload[m.end()-1:])
            if data and isinstance(data[0],dict) and str(data[0].get('id','')).startswith('item_'):candidates.append(data)
        except ValueError:continue
    if len(candidates)!=1:raise ValueError('BGEE public inventory payload changed')
    for item in candidates[0]:
        rows.append(record(item['name'],item['groupId'].removeprefix('items_'),'https://baldursgateee.th.gl/db/inventory/'+item['id'],upstream_ids=[item['id']],evidence_kind='fan-game-inventory-index',ninja_relevance='backlog'))
    save('baldurs-gate-1-reference',rows,game_id='baldurs-gate-1',source_url=url,coverage='Public BG Enhanced Edition inventory metadata including SoD/engine entries where indexed. Name/type families collapse duplicate resource IDs. Not every record is obtainable in normal play; no original/EE version equivalence asserted.',raw_resource_count=len(candidates[0]))
    url='https://mikesrpgcenter.com/bgate2/cheats.html';tree=fetch(url);rows=[]
    prefixes={'sw':'sword','dagg':'dagger','bow':'bow','xbow':'crossbow','blun':'mace','hamm':'hammer','halb':'halberd','staf':'staff','sper':'spear','ax':'axe','arow':'ammunition','bolt':'ammunition','bull':'ammunition','scrl':'scroll','potn':'potion','wand':'wand','ring':'ring','amul':'amulet','boot':'boots','brac':'gloves','belt':'belt','clck':'cloak','helm':'helmet','plat':'armor','chan':'armor','leat':'armor','shld':'shield','key':'key','book':'book'}
    for tr in tree.xpath('//tr'):
        cells=tr.xpath('./td')
        for idx,cell in enumerate(cells[1:],1):
            code=clean(cell.text_content())
            if re.fullmatch(r'[a-z]{2,6}[a-z0-9]{2,4}',code) and any(c.isdigit() for c in code):
                name=clean(cells[idx-1].text_content())
                if name and name!=code and len(name)<150:
                    typ=next((v for k,v in prefixes.items() if code.startswith(k)),'misc')
                    rows.append(record(name,typ,url,upstream_ids=[code],evidence_kind='fan-resource-code-index',ninja_relevance='backlog'))
    save('baldurs-gate-2-reference',rows,game_id='baldurs-gate-2',source_url=url,coverage='Historical BGII item resource-code index; name/type groups collapse same-named IDs. Scroll names are inventory scroll references, not standalone spell imports. Obtainability and EE differences unverified.')
    url='https://diablobytes.com/diablo-i/items/uniques/';tree=fetch(url);rows=[]
    for tr in tree.xpath('//tr[contains(@class,"uq-row")]'):
        cells=tr.xpath('./td');first=cells[0]
        name=clean(''.join(first.itertext()).replace('⚔️',''))
        heading=tr.xpath('preceding::h2[1]');kind=clean(heading[0].text_content()) if heading else 'misc'
        rows.append(record(name,kind,url,evidence_kind='fan-unique-item-table',ninja_relevance='backlog'))
    save('diablo-1-reference',rows,game_id='diablo-1',source_url=url,coverage='Selected unique-item tables from a secondary database. No Hellfire or current mod completeness claimed; not every listed item necessarily drops normally.')

if __name__=='__main__':backlog_indexes()
