#!/usr/bin/env python3
"""Gazetteer references: explicit book labels, trade categories and NPC equipment.
No legacy/gameplay prose, spells, stats, source art, generic variants or prices exported.
"""
import collections,hashlib,json,re,sys,time,urllib.parse,urllib.request
from pathlib import Path
from lxml import html
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.cache/research/gazetteers';OUT=ROOT/'catalog/raw/setting-reference-indexes';CACHE.mkdir(parents=True,exist_ok=True)
REGIONS={1:'karameikos',2:'ylaruam',3:'glantri',4:'ierendi',5:'alfheim',6:'rockhome',7:'northern-reaches',8:'five-shires',9:'minrothad',10:'broken-lands',11:'darokin',12:'ethengar',13:'shadow-elves',14:'atruaghin'}
def save(key,label,rows,url,coverage):
 data={'source_id':key,'label':label,'entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':coverage,'records':rows}
 (OUT/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(key,len(rows),flush=True)
def base(name,kind,url,codes,author,evidence='fan-explicit-gazetteer-equipment-reference'):
 row={'name':name,'source_type':kind,'url':url,'evidence_kind':evidence,'source_author':author,'reported_book_codes':codes,'original_book_verified':False,'regional_role':'found-in','regional_status':'source-reported-regional-presence','source_note':'Name/type and explicitly reported book association only. Source mechanics, prose, prices, rarity and culture-based proficiency are not imported.'}
 if len(codes)==1 and re.fullmatch(r'GAZ\d+',codes[0]):row['regional_entity_id']='region:'+REGIONS[int(codes[0][3:])]
 return row

def known_world():
 url='https://pandius.com/kw_uwae.html';t=fetch(url);rows=[]
 # Alias rows are one item, not generated variants. Preserve the source name separately.
 aliases={'Arrow, Heavy/Takadi':'Arrow, Heavy','Arrow, Light/Moraki':'Arrow, Light'}
 used=set()
 for li in t.xpath('//li'):
  s=clean(li.text_content());codes=sorted(set('GAZ'+str(int(n)) for n in re.findall(r'\bGaz\s*(\d+)\b',s,re.I)))
  if not codes:continue
  title=re.split(r'\s*\(|\s+-\s+|:',s,maxsplit=1)[0].strip();title=aliases.get(title,title)
  key=(title.casefold(),tuple(codes))
  if key in used:continue
  used.add(key)
  kind='ammunition' if title.startswith('Arrow,') else 'armor' if title.startswith('Armor,') else 'unclassified-item' if title.startswith('Fire Crystal') else 'weapon'
  row=base(title,kind,url,codes,'Håvard');row['reported_heading']=re.split(r'\s*\(|\s+-\s+|:',s,maxsplit=1)[0].strip()
  if title.startswith(('Ballista','Balilsta','Catapult','Ram,','War Machine','Wreacking','Ammunition, Flail','Drop,','Slide,')):
   row['record_kind']='construction-component';row['source_type']='construction-component';row['source_note']+=' Siege/installed domain; not automatically portable inventory.'
  rows.append(row)
 save('gazetteer-equipment-reference','Gazetteer unusual equipment and siege references',rows,url,'Only entries explicitly labelled GAZ1–14 in a public fan source index. Generic uncited entries excluded. Heavy/Takadi and Light/Moraki arrow aliases collapse to one record each. Reported spellings retained; no original-book verification.')
 # One cross-reference can add an item missing from the broader equipment index.
 url='https://pandius.com/bow_rev.html';t=fetch(url);rows=[]
 for tr in t.xpath('//tr'):
  cells=tr.xpath('./td');text=[clean(c.text_content()) for c in cells]
  if len(text)<3:continue
  codes=sorted(set('GAZ'+str(int(n)) for n in re.findall(r'\bGaz\s*(\d+)\b',text[-1],re.I)))
  if codes:rows.append(base(text[0],'ammunition' if 'arrow' in text[0].lower() else 'weapon',url,codes,'Håvard','fan-bow-table-explicit-source-column'))
 save('gazetteer-bow-reference','Gazetteer bow and arrow source references',rows,url,'Names and source-column labels only. Fan revised bow mechanics and prices are excluded.')

def trade_goods():
 url='https://pandius.com/domneco.html';t=fetch(url);rows=[]
 for ul in t.xpath('//ul')[:2]:
  for li in ul.xpath('./li'):
   name=clean(li.text_content()).strip('` ')
   if not name:continue
   row=base(name,'material',url,['GAZ9','GAZ11'],'Giampaolo Agosta','fan-reported-joint-gazetteer-trade-list');row['record_kind']='trade-category';rows.append(row)
 save('gazetteer-trade-reference','GAZ9 / GAZ11 reported trade merchandise categories',rows,url,'Reported joint Gazetteer trade categories before the author’s expanded domain-resource tables. One record per source category; combined labels are not split into invented variants. Animals and monsters remain broad merchandise categories, not individual creatures or player items. No source prices or tax formulas imported.')

GEAR=re.compile(r'\b(?:bracers of defen[cs]e(?:\s+AC\s*\d+)?|ring of protection|plate mail|chain mail|chain shirt|leather armo[u]?r|shield|longsword|shortsword|long sword|short sword|dagger|sword|mace|staff|battle axe|war hammer|short bow|long bow|crossbow|spear|bow)(?:\s*\+\s*\d+)?',re.I)
def npc_gear(text):
 # Scope to the original-style combat paragraph, not spells, design changes or sidebar links.
 m=re.search(r'BECMI Combat Notes:\s*([^\n]+)',text);found=[]
 if m:
  paragraph=re.split(r'Languages:|His languages|General Skills:|His general skills',m[1])[0]
  found += [clean(x[0]) for x in GEAR.finditer(paragraph)]
 m=re.search(r'Magic Items in Possession:\s*([^\n]+)',text)
 if m:
  possession=re.sub(r'\([^()]*\)','',m[1]).strip().rstrip('.')
  found += [clean(x) for x in possession.split(',') if clean(x).lower() not in ['none','nil','']]
 # Never infer the legacy special dagger is merely an ordinary +2 dagger.
 if re.search(r'Dagger\s*\+2,\s*\+3\s+vs\.?\s*Spell',text,re.I):found=[x for x in found if not re.fullmatch(r'dagger\s*\+\s*2',x,re.I)]+['Dagger +2 (+3 vs. Spell-Casters)']
 return list(dict.fromkeys(re.sub(r'\s*\+\s*(\d+)',r' +\1',x.casefold().replace('defence','defense').replace('armour','armor')).replace('( +','(+') for x in found))

def npc_references():
 audit=[];grouped={};allposts={}
 for gaz in range(1,15):
  query=urllib.parse.urlencode({'search':'GAZ'+str(gaz),'number':100,'fields':'found,posts,URL,title,content'})
  url='https://public-api.wordpress.com/rest/v1.1/sites/thedarkelf007.home.blog/posts/?'+query
  path=CACHE/f'blog-gaz{gaz}-api.json'
  try:
   if path.exists():d=json.loads(path.read_text())
   else:
    with urllib.request.urlopen(url,timeout=30) as r:d=json.load(r)
    path.write_text(json.dumps(d));time.sleep(.25)
   posts=d.get('posts',[]);candidates=[p for p in posts if p['title'].startswith('DnD NPC')]
   audit.append({'query':'GAZ'+str(gaz),'found':d.get('found'),'returned':len(posts),'npc_candidates':len(candidates),'pagination_complete':d.get('found',0)<=len(posts),'url':url})
   for p in candidates:allposts[p['URL']]=p
  except Exception as e:
   audit.append({'query':'GAZ'+str(gaz),'error':str(e)})
   if getattr(e,'code',None) in [401,403,429]:break
 for url,p in allposts.items():
  text=html.fromstring(p['content']).text_content();credit=re.search(r'Source\s*[–—:-]\s*GAZ\s*(\d+)\s+p\.?\s*(\d+)',text,re.I) or re.search(r'0e-gaz-0?(\d+)\s+p\.?\s*(\d+)',text[:3000],re.I)
  if not credit:continue
  gaz=int(credit[1]);code='GAZ'+str(gaz)
  if gaz not in REGIONS:continue
  for name in npc_gear(text):
   key=(gaz,name)
   if key not in grouped:
    kind='armor' if any(k in name for k in ['armor','mail','shirt']) else 'shield' if name.startswith('shield') else 'ring' if name.startswith('ring') else 'scroll' if name.startswith('scroll') else 'wand' if name.startswith('wand') else 'wondrous-item' if name.startswith(('bracers','drums')) else 'weapon'
    row=base(name,kind,url,[code],'thedarkelf007','secondary-npc-equipment-with-book-page-credit');row['reported_page']=int(credit[2]);row['attested_appearances']=[];row['source_note']+=' Source is a campaign blog and may include editorial changes. Page credit is reported, not independently checked.';grouped[key]=row
   grouped[key]['attested_appearances'].append({'npc':html.fromstring('<span>'+p['title']+'</span>').text_content().removeprefix('DnD NPC '),'url':url,'reported_book':code,'reported_page':int(credit[2])})
 save('gazetteer-npc-equipment-reference','Gazetteer NPC equipment appearance references',list(grouped.values()),'https://thedarkelf007.home.blog/','Explicit GAZ-number/page credit required. Equipment scoped to BECMI combat notes and possession lists only; spell lists, rewritten character details, sidebar links and monthly summaries excluded. Identical item labels grouped per book with all attested NPC appearances. Query search is bounded to 100 posts per book; pagination gaps are recorded separately.')
 (CACHE/'npc-query-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
if __name__=='__main__':known_world();trade_goods();npc_references()
