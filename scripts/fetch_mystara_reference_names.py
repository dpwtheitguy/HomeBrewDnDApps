#!/usr/bin/env python3
"""Index attested Mystara names and reported books, never powers or rarity claims."""
import hashlib,json,re,sys,time
from pathlib import Path
from lxml import html
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'catalog/raw/setting-reference-indexes';out.mkdir(parents=True,exist_ok=True)
ALIASES={'WotI':'TSR-1082','DotE':'TSR-1037','CoM':'TSR-1094','Rules Cyclopedia':'RC',"Master DM's Guide":'MASTER','Joshuan\'s Almanac':'JA','Savage Baronies':'TSR-9500','Glantri: Kingdom of Magic':'TSR-2511'}
def code(v):
 v=v.strip()
 return ALIASES.get(v,'GAZ'+v[3:] if v.casefold().startswith('gaz') else v)
def save(key,label,entity,url,records,coverage):
 data={'source_id':key,'label':label,'entity_id':entity,'setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':coverage,'records':records}
 (out/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(key,len(records),flush=True)
def main():
 url='https://pandius.com/artflist.html';text=fetch(url).text_content();body=text.split("The list I've got so far:",1)[1].split('*Note:',1)[0];rows=[]
 for line in body.splitlines():
  m=re.fullmatch(r'\s*(.+?)\s*\(([^()]*)\)\s*',line)
  if not m:continue
  name=clean(m[1]);books=[code(v) for v in m[2].split(',')]
  rows.append({'name':name,'source_type':'wondrous-item','url':url,'evidence_kind':'fan-item-and-reported-source-index','source_author':'Andrew Theisen','reported_book_codes':books,'original_book_verified':False,'source_note':'The author explicitly includes some ordinary magic items among artifact candidates. Rarity and powers are not imported or certified.','ninja_relevance':'backlog'})
 save('mystara-artifact-name-reference','Mystara reported artifact and magic-item names','topic:mystara-frontiers',url,rows,'Fan-reported names and book codes only. The source calls itself a complete list but explicitly describes a work in progress and proposed artifact expansions. No completeness or rarity claim is inherited.')
 refs=json.loads((ROOT/'catalog/settings/mystara/five-shires-item-mentions.json').read_text());rows=[]
 for r in refs:
  category={'magic-relics':'wondrous-item','weapons':'weapon','clothing':'clothing','armor':'armor','consumables':'consumable','trade-goods':'material','tools-gear':'adventuring-gear'}.get(r['category'],'wondrous-item')
  rows.append({'name':r['name'],'source_type':category,'url':r['source_url'],'evidence_kind':'fan-gazetteer-name-and-page-index','source_author':r['source_author'],'reported_book_codes':['GAZ8'],'reported_page':r['reported_page'],'original_book_verified':False,'source_note':r['note'],'ninja_relevance':'backlog'})
 save('gaz8-name-reference','GAZ8 selected distinctive names','topic:mystara-frontiers','https://www.pandius.com/5shritems.html',rows,'Selected 26 distinctive mentions already retained in the research files, now searchable as references. Reported GAZ8 page numbers are not original-page verification. A mention is not proof of local origin or manufacture; none is a playable conversion.')
if __name__=='__main__':main()
