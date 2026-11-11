#!/usr/bin/env python3
"""Collect names with explicit book labels; never export source descriptions or powers."""
import json,re,sys,time,urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'catalog/raw/setting-reference-indexes'
TARGETS={
 'Arms and Equipment Guide':('arms-equipment-3e-reference','Arms and Equipment Guide (3e)','publication:arms-equipment-3e','dnd-3e'),
 'Oriental Adventures':('oriental-adventures-3e-reference','Oriental Adventures (3e)','publication:oriental-adventures-3e','dnd-3e'),
 "Stronghold Builder's Guidebook":('stronghold-builder-reference',"Stronghold Builder’s Guidebook",'publication:stronghold-builder-3e','dnd-3e'),
}
PAGES={'staff':'staff','rods':'rod','rings':'ring','wondrousitems':'wondrous-item','potions':'potion','siegeengines':'weapon','cursed':'wondrous-item','alchemy':'adventuring-gear','alchemycharms':'wondrous-item','drowitems':'wondrous-item','artifact':'wondrous-item','artifactf':'wondrous-item','thayan':'wondrous-item'}
def sections(tree):
 for h in tree.xpath('//div[@id="main"]//h3'):
  nodes=[]
  for sibling in h.itersiblings():
   if sibling.tag in ['h1','h2','h3']:break
   nodes.append(sibling)
  text=' '.join(n.text_content() for n in nodes)
  sources=re.findall(r'Source:\s*([^\n\r]+)',text)
  # A source must be an explicit credit line, not a book name mentioned in prose.
  yield clean(h.text_content()),[clean(x) for x in sources],h

def main():
 collected={key:[] for key in TARGETS};audit=[]
 pages=[(f'https://realmshelps.net/magic/items/{p}.shtml',k) for p,k in PAGES.items()]+[('https://realmshelps.net/magic/magweapon-spec.shtml','weapon'),('https://realmshelps.net/magic/magarmor-spec.shtml','armor')]
 for url,kind in pages:
  try:
   tree=fetch(url);n=0
   for name,sources,h in sections(tree):
    for book in TARGETS:
     if book in sources:
      anchor=h.get('id') or h.get('name')
      row={'name':name,'source_type':kind,'url':url+('#'+anchor if anchor else ''),'evidence_kind':'secondary-explicit-book-credit','source_author':'Realms Helps index; original book authors not inferred','reported_book_codes':[book],'original_book_verified':False,'source_note':'Name and explicit source credit only. No source mechanics, prose, price, artwork or rarity imported; original page not verified.'}
      if kind=='staff' and not re.search(r'\bstaff\b',name,re.I):row['name']='Staff of '+name
      if kind=='rod' and not re.search(r'\brod\b',name,re.I):row['name']='Rod of '+name
      if kind=='ring' and not re.search(r'\bring\b',name,re.I):row['name']='Ring of '+name
      row['reported_heading']=name
      collected[book].append(row);n+=1
   audit.append({'url':url,'status':'inspected-name-and-book-credit','target_records':n})
  except Exception as e:
   audit.append({'url':url,'status':'failed','error':str(e)})
   if getattr(e,'code',None) in [401,403,429]:break
 for table_url,kind,path_part in [('https://realmshelps.net/stores/all-weapons.shtml','weapon','weapons/'),('https://realmshelps.net/stores/all-armor.shtml','armor','armor/')]:
  tree=fetch(table_url);n=0
  for tr in tree.xpath('//tr'):
   cells=tr.xpath('./td')
   if len(cells)<3:continue
   item_links=cells[0].xpath('.//a[contains(@href,"'+path_part+'")]')
   if not item_links:continue
   credit_links=cells[-1].xpath('.//a')
   credit_labels=[clean(a.text_content()) for a in credit_links]
   for book in TARGETS:
    if book not in credit_labels:continue
    a=item_links[0];collected[book].append({'name':clean(a.text_content()),'source_type':kind,'url':urllib.parse.urljoin(table_url,a.get('href')),'evidence_kind':'secondary-explicit-table-book-credit','reported_book_codes':[book],'original_book_verified':False,'source_note':'Name, type and explicit table source credit only. No source mechanics, prices or prose imported.'});n+=1
  audit.append({'url':table_url,'status':'inspected-table-name-and-book-credit','target_records':n})
 for book,rows in collected.items():
  key,label,entity,ruleset=TARGETS[book];path=OUT/(key+'.json')
  old=json.loads(path.read_text()) if path.exists() else None
  existing=old['records'] if old else []
  grouped={(r['name'].casefold(),r['source_type']):r for r in existing}
  for r in rows:grouped[(r['name'].casefold(),r['source_type'])]=r
  if not grouped:continue
  data={'source_id':key,'label':label,'entity_id':entity,'ruleset':ruleset,'source_url':'https://realmshelps.net/magic/items/index.shtml','retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Selected public item categories, explicit book-credit lines only. Not a complete original-book audit. Existing independently sourced references retained.','records':list(grouped.values())}
  path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(key,len(grouped))
 # Fan creations are separately labelled; regional placement never certifies GAZ appearance.
 url='https://pandius.com/magcitem.html';tree=fetch(url);rows=[];region=None
 for a in tree.xpath('//a[@name]'):
  p=a.getparent();title=p.xpath('./b[1]');author=p.xpath('.//i//a[contains(@href,"authors.html")]')
  if not title:continue
  name=clean(title[0].text_content())
  if not author:region=name;continue
  rows.append({'name':name,'source_type':'unclassified-item','url':url+'#'+a.get('name'),'evidence_kind':'named-fan-created-item','source_author':clean(author[0].text_content()),'reported_region':region,'original_book_verified':False,'source_note':'Fan creation, not certified Gazetteer content. Source prose, mechanics, powers and prices omitted; item category remains unverified.'})
 region_aliases={'Alfheim':'region:alfheim','Atruaghin Plateau':'region:atruaghin','Darokin':'region:darokin','Ierendi':'region:ierendi','Northern Reaches':'region:northern-reaches','Ochalea':'region:ochalea','Rockhome':'region:rockhome','Sind':'region:sind','The Five Shires':'region:five-shires','Thyatis':'region:thyatis','Ylaruam':'region:ylaruam'}
 for row in rows:
  if row['reported_region'] in region_aliases:row['regional_entity_id']=region_aliases[row['reported_region']]
 data={'source_id':'mystara-fan-names-reference','label':'Mystara regional fan-created item names','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Named, author-credited fan creations from a public regional collection. Not evidence of appearance in any TSR Gazetteer.','records':rows}
 (OUT/'mystara-fan-names-reference.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(data['source_id'],len(rows))
 (ROOT/'.cache/research/book-expansion-pass.json').write_text(json.dumps(audit,indent=2)+'\n')
if __name__=='__main__':main()
