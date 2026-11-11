#!/usr/bin/env python3
"""Names visually checked on publisher samples. No source prose, tables or art export."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.cache/research/gazetteers'
previews={r['book_code']:r for r in json.loads((CACHE/'preview-fetch-report.json').read_text())};rows=[]
def add(name,code,page,kind,heading=None,record_kind=None,**extra):
 d=previews[code];row={'name':name,'source_type':kind,'url':d['preview_url']+'#page='+str(page),'evidence_kind':'visually-checked-publisher-preview-name','source_author':'TSR / Wizards of the Coast publisher sample','reported_book_codes':[code],'original_book_verified':True,'regional_role':'found-in','regional_status':'publisher-preview-regional-presence','preview_sha256':d['sha256'],'locator':{'preview_pdf_page':page,'printed_page':page if code in ['GAZ8','GAZ13'] else None,'source_section':'Map legend' if code=='GAZ7' else 'Partial Armor chart' if code=='GAZ10' else 'Clans' if code=='GAZ8' else 'Introduction'},'verified_fields':['name','appearance-on-cited-page'],'reported_heading':heading or name,'source_note':'Item name/appearance visually checked on the public publisher preview. This does not verify full powers, price, 2024 compatibility or a complete book audit.',**extra}
 if record_kind:row['record_kind']=record_kind
 regions={'GAZ7':'northern-reaches','GAZ8':'five-shires','GAZ10':'broken-lands','GAZ13':'shadow-elves'};row['regional_entity_id']='region:'+regions[code];rows.append(row)
add('Crucible of Blackflame','GAZ8',6,'unclassified-item')
add('Clan Tapestry','GAZ8',6,'unclassified-item','Clan Tapestries',name_normalization_note='Singular searchable label derived from plural section heading.')
add('Clan Stronghold','GAZ8',6,'construction-component','Clan Strongholds and Offices','construction-component')
add('Chamber of the Ancestors','GAZ8',6,'construction-component',record_kind='construction-component')
add('Soul Crystal','GAZ13',2,'gem','Soul Crystals',name_normalization_note='Singular searchable label derived from plural mention.')
for name in ['Earthen Rampart','Timber Palisade','Drainage Ditch','Boardwalk','Fire Pit','Pillars','Guard Platform','Stairs','Doors']:
 add(name,'GAZ7',5,'construction-component',record_kind='construction-component')
for name in ['Table','Sleeping Bench','Stool and Bench','High Seat','Screen','Chests']:
 add(name,'GAZ7',5,'furnishing',record_kind='furnishing-reference')
add('Gate Tower','GAZ7',1,'construction-component',record_kind='construction-component')
for name in ['Main Longhouse','Hut','Shed']:
 add(name,'GAZ7',6,'construction-component',record_kind='construction-component')
add('Partial Armor','GAZ10',1,'armor',component_labels=['Shield','Head','Torso','Shoulder (one)','Arm (one upper)','Elbow (both)','Arm (one lower)','Hands (both)','Waist & Back End','Leg (one upper)','Knees (both)','Legs (one lower)','Feet (both)'],scope_note='One partial-armor reference with its printed component labels; material/body-part combinations are not expanded into catalog items. No armor-class values, racial rules, defects or random tables copied.')
data={'source_id':'gazetteer-publisher-preview-reference','label':'Gazetteer publisher-preview item and construction names','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':'https://pandius.com/dthrurpg.html','retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'25 selected name/appearance references visually verified on publisher-hosted samples. GAZ7 includes actual map furnishings/construction labels; these are not new portable magic items. GAZ10 partial-armor combinations are not generated. No book is audited in full.','records':rows}
assert len(rows)==25
(ROOT/'catalog/raw/setting-reference-indexes/gazetteer-publisher-preview-reference.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print('Publisher-preview name references:',len(rows))
