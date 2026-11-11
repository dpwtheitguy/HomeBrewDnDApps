#!/usr/bin/env python3
"""Link actual imported references to regional research cells without certifying audits."""
import collections,datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'catalog';PASS='gazetteer-equipment-2026-11-08'
qpath=C/'research/queue.json';q=json.loads(qpath.read_text());lookup={(t['entity_id'],t['category']):t for t in q['tasks']};updates=collections.defaultdict(list)
sources={'gazetteer-equipment-reference','gazetteer-bow-reference','gazetteer-npc-equipment-reference','gazetteer-publisher-preview-reference','gaz13-online-adaptation-reference'}
for line in (C/'items.jsonl').open():
 i=json.loads(line)
 if i['source_id'] not in sources:continue
 typ=i['type'];kind=i.get('record_kind')
 category='tools-gear' if kind in ['construction-component','furnishing-reference'] else 'armor' if typ in ['armor','shield'] else 'weapons' if typ in ['weapon','ammunition'] else 'magic-relics' if typ in ['ring','staff','wand','rod','cloak','gloves','boots','wondrous-item','scroll'] else None
 if not category:continue
 for a in i['associations']:
  if a['entity_id'].startswith('region:') and a['role']=='found-in' and (a['entity_id'],category) in lookup:updates[(a['entity_id'],category)].append(i)
for key,items in updates.items():
 t=lookup[key];first=PASS not in t.setdefault('research_passes',[])
 if first:t['research_passes'].append(PASS);t['search_attempts']+=1
 t['status']='source-leads-found';t['item_ids']=sorted(set(t['item_ids'])|{i['id'] for i in items})
 seen={e['url'] for e in t['evidence']}
 for i in items:
  url=i['provenance']['source_url']
  if url not in seen:
   t['evidence'].append({'url':url,'title':'Gazetteer equipment name / appearance evidence','note':'Found in structured source/preview research, not proof of cultural manufacture, completed original-book audit or reviewed 2024 conversion.','recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat()});seen.add(url)
qpath.write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print('Regional research cells linked to imported evidence:',len(updates))
