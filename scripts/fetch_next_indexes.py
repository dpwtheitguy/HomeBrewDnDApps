#!/usr/bin/env python3
"""Resumable whitelisted public reference indexes; raw HTML stays in cache."""
import concurrent.futures,json,re,sys,urllib.parse
from pathlib import Path
from lxml import html
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,record,save,clean

def public_items(tree):
    parts=[]
    for script in tree.xpath('//script'):
        for m in re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)',script.text or ''):parts.append(json.loads(m[1]))
    payload=''.join(parts);candidates=[]
    for m in re.finditer(r'"items":\[',payload):
        try:
            data,_=json.JSONDecoder().raw_decode(payload[m.end()-1:])
            if data and isinstance(data[0],dict) and {'id','name','groupId'}<=data[0].keys():candidates.append(data)
        except ValueError:continue
    if len(candidates)!=1:raise ValueError('Public inventory payload changed; stop for review')
    return candidates[0]

def conan():
    url='https://conanexiles.th.gl/db/inventory';rows=[];excluded=[]
    ballista_ammunition_ids = {f'item_{number}' for number in range(89854, 89860)}
    for row in public_items(fetch(url)):
        kind=row['groupId'].removeprefix('inventory_group_')
        # Pet tokens belong in a future companion/creature registry, not this equipment pack.
        if kind=='petitem':excluded.append(row['id']);continue
        entry=record(row['name'],kind,'https://conanexiles.th.gl/db/inventory/'+row['id'],upstream_ids=[row['id']],evidence_kind='fan-public-inventory-index',ninja_relevance='backlog')
        if kind in ['buildingitem','decoration','craftingstations']:entry['record_kind']='construction-component'
        # The inventory groups these recipes under weapons. Keep their IDs and index them as ammunition.
        if kind == 'weapon' and row['id'] in ballista_ammunition_ids:
            entry['verified_source_type'] = 'ammunition'
        rows.append(entry)
    save('conan-exiles-reference',rows,game_id='conan-exiles',source_url=url,coverage='Public Conan Exiles Enhanced inventory snapshot. Names/categories/IDs only. Pet inventory tokens excluded for a future companion registry. Obtainability, DLC ownership and edition/patch equivalence unverified. Decorations and building pieces are reported separately from portable equipment; no art, game properties, recipes or random affix products imported.',excluded_pet_token_ids=excluded)

def diablo4():
    url='https://diablo4.th.gl/db/uniques';rows=[]
    for row in public_items(fetch(url)):
        parts=row.get('text','').split(' · ')
        kind=parts[1] if len(parts)>=2 else 'unique-item'
        rows.append(record(row['name'],kind,'https://diablo4.th.gl/db/uniques/'+row['id'],upstream_ids=[row['id']],evidence_kind='fan-public-unique-index',source_game_class=row['groupId'],ninja_relevance='backlog'))
    save('diablo-4-reference',rows,game_id='diablo-4',source_url=url,coverage='Public unique-item inventory snapshot. Source-game class names are reference metadata, not D&D class restrictions. No game effects, numeric affixes, market prices or current-season completeness claim.')

def torment():
    base='https://shrines.rpgclassics.com/pc/planescape/';rows=[];failures=[]
    # These are inventory tables, not standalone spell pages or NPC rosters.
    pages=[('weapons.shtml','weapon'),('armor.shtml','armor'),('items.shtml','misc'),('tattoos.shtml','tattoo'),('miscellaneous.shtml','misc')]
    for page,kind in pages:
        url=base+page
        try:tree=fetch(url)
        except Exception as e:failures.append({'url':url,'error':str(e)});continue
        for tr in tree.xpath('//tr'):
            cells=tr.xpath('./td')
            if len(cells)<3 or len(cells)>10:continue
            first=cells[0];name=clean(first.text_content())
            if name and name not in ['Name','Item','Weapons'] and len(name)<120 and not first.xpath('.//table'):
                # Actual rows in this shrine have an image cell followed by the name in some tables.
                if not name and len(cells)>1:name=clean(cells[1].text_content())
                anchors=tr.xpath('preceding::a[@name][1]')
                section=anchors[0].get('name') if anchors else kind
                if 'scroll' in name.casefold():section='scroll'
                rows.append(record(name.rstrip('*'),section,url,evidence_kind='fan-inventory-table',source_annotation_star=name.endswith('*'),ninja_relevance='backlog'))
    save('planescape-torment-reference',rows,game_id='planescape-torment',source_url=base,coverage='Selected historical inventory tables (weapons, armor, tattoos, equipment and miscellany). Not all engine or Enhanced Edition items. Source-game effects, spell lists and story text excluded.',failures=failures)

if __name__=='__main__':conan();diablo4();torment()
