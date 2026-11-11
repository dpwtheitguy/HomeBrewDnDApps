#!/usr/bin/env python3
"""Offline catalog search. Examples: --profile mystara-workbench --origin Karameikos
--culture Thayan | --region Glantri | --setting Mystara --tag magic | dag --sort relevance
Repeated values OR within a facet; different facets AND; repeated --tag AND.
"""
import argparse,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shared'))
from catalog_search import search

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('query',nargs='?',default='')
    for flag in ['ruleset','source','type','tag','setting','region','culture','origin','rarity','people']:p.add_argument('--'+flag,action='append')
    p.add_argument('--resource',action='append')
    p.add_argument('--profile',default='all-research');p.add_argument('--relationship')
    p.add_argument('--include-unattributed',action='store_true');p.add_argument('--sort',choices=['name','rarity','relevance','value'],default='name')
    p.add_argument('--magic',choices=['any','yes','no','unknown']);p.add_argument('--attunement',choices=['any','yes','no','unknown'])
    p.add_argument('--min-value');p.add_argument('--max-value');p.add_argument('--value-economy')
    p.add_argument('--limit',type=int,default=20);p.add_argument('--json',action='store_true');a=p.parse_args()
    db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3');db.row_factory=sqlite3.Row
    try:rows=search(db,ROOT/'catalog',a.query,a.profile,a.ruleset,a.source,a.type,a.tag,a.setting,a.region,a.culture,a.origin,a.relationship,a.include_unattributed,a.sort,a.limit,a.rarity,a.magic,a.attunement,a.min_value,a.max_value,a.value_economy,a.people,resources=a.resource)
    except ValueError as e:p.error(str(e))
    if a.json:print(json.dumps([json.loads(r['data_json']) for r in rows],ensure_ascii=False,indent=2))
    else:
        for r in rows:print(f'{r["name"]} | {r["ruleset"]} | {r["source_id"]} | {r["type"]}\n  {r["id"]}')
        print(f'{len(rows)} result(s), limit {a.limit}, profile {a.profile}')
    db.close()
if __name__=='__main__':main()
