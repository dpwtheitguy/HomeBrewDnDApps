#!/usr/bin/env python3
import collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'catalog'
q=json.loads((C/'research/queue.json').read_text());entities=json.loads((C/'taxonomy/entities.json').read_text())['entities']
counts=json.loads((C/'reports/counts.json').read_text());states=collections.Counter(t['status'] for t in q['tasks'])
sources={e['url'] for t in q['tasks'] for e in t['evidence']}
r={'registry_entities':len(entities),'entity_kinds':dict(collections.Counter(e['kind'] for e in entities)),
   'research_tasks':len(q['tasks']),'task_statuses':dict(states),'evidence_urls':len(sources),
   'full_book_audits_completed':0,'reviewed_conversions':0,
   'mystara_draft_records':counts['by_source']['mystara-draft-conversions'],
   'distinctive_GAZ8_mentions_not_counted_as_converted_items':len(json.loads((C/'settings/mystara/five-shires-item-mentions.json').read_text())),
   'limitations':['Registry is a seed, not an exhaustive list of every nation or people across settings.','Other requested settings still need entity discovery and item imports.','A source lead is not an inspected sourcebook or a validated conversion.','No absence of cultural equipment is inferred from a negative web search.']}
adventure=json.loads((C/'settings/thunder-rift/adventure-pack.json').read_text())
r['adventure_draft_records']=len(adventure['drafts'])
r['adventure_appearances_reusing_existing_items']=len(adventure['appearances'])
r['adventure_additional_item_leads']=len(adventure.get('item_leads',[]))
r['adventure_workstreams']=json.loads((C/'settings/thunder-rift/research-queue.json').read_text())['workstreams']
ninja=json.loads((C/'settings/ninja/research-pack.json').read_text())
r['construction_records']=counts.get('construction_records',0)
r['construction_proposals']=counts.get('construction_proposals',0)
r['skyship_proposals']=counts.get('vehicle_proposals',0)
r['mystara_frontier_drafts']=len(json.loads((C/'settings/mystara-frontiers/research-pack.json').read_text())['items'])
r['ninja_draft_records']=len(ninja['items'])
r['ninja_draft_modes']=dict(collections.Counter(i['mode'] for i in ninja['items']))
r['setting_reference_records']={p.stem:len(json.loads(p.read_text())['records']) for p in sorted((C/'raw/setting-reference-indexes').glob('*.json'))}
r['game_reference_records']={p.stem:len(json.loads(p.read_text())['records']) for p in sorted((C/'raw/game-reference-indexes').glob('*.json'))}
r['target_15000_source_record_gap']=max(0,15000-counts['source_records'])
r['current_objective']='Source coverage across every requested setting/resource; no item-count ceiling.'
resource_report=C/'reports/resource-coverage.json'
if resource_report.exists():
 coverage=json.loads(resource_report.read_text());r['registered_resources']=coverage['registered_resources'];r['resource_coverage_statuses']=coverage['by_coverage_status']
r['target_15000_distinct_name_gap']=max(0,15000-counts['distinct_normalized_names'])
r['target_note']='The 15,000 milestone is tracked separately for source records and normalized names; neither proves semantic uniqueness or playable 2024 conversion.'
(C/'reports/research-coverage.json').write_text(json.dumps(r,indent=2)+'\n')
lines=['# Research coverage','',f"Current entity registry: {r['registry_entities']}. Research matrix: {r['research_tasks']:,} tasks.",'','| Status | Cells |','|---|---:|']
lines += [f'| {k} | {v:,} |' for k,v in sorted(states.items())]
lines += ['',f"Distinct source URLs attached to matrix cells: {len(sources)}.",f"Mystara catalog drafts: {r['mystara_draft_records']}. GAZ8 distinctive mentions retained separately: {r['distinctive_GAZ8_mentions_not_counted_as_converted_items']}.",'','Full book audits completed: 0. Playtested/reviewed conversions: 0.','',*['- '+x for x in r['limitations']],'','See `docs/SEARCH-AND-RESEARCH.md` for the method and `catalog/research/queue.json` for per-cell evidence.']
lines += ['', '## Boxed-adventure pass', '', f"Original drafts: {r['adventure_draft_records']}; appearances reusing existing definitions: {r['adventure_appearances_reusing_existing_items']}; additional leads: {r['adventure_additional_item_leads']}.", '', '| Workstream | Status |', '|---|---|']
lines += [f"| {w['label']} | {w['status']} |" for w in r['adventure_workstreams']]
lines += ['', 'No original-book item audits completed. See catalog/settings/thunder-rift/README.md for source distinctions.']
lines += ['', '## Ninja and game-reference pass', '', f"Ninja 2024 project drafts: {r['ninja_draft_records']}. Modes: {r['ninja_draft_modes']}.", '', '| Reference index (adaptation pending) | Records |', '|---|---:|']
lines += [f'| {k} | {v:,} |' for k,v in r['game_reference_records'].items()]
lines += ['', f"Remaining gap to 15,000 source records: {r['target_15000_source_record_gap']:,}. Gap to 15,000 distinct normalized names: {r['target_15000_distinct_name_gap']:,}. Neither measure proves playable or semantically unique items.", '', 'Full 2e Ninja Handbook and 2001 OA equipment/magic audits remain pending. Mark of Amber is queued with publisher-preview evidence.']
lines += ['', '## Worldbuilding and Mystara frontiers', '', f"Construction records: {r['construction_records']}; original construction proposals: {r['construction_proposals']}; new regional/expedition drafts: {r['mystara_frontier_drafts']} (including {r['skyship_proposals']} original skyships).", '', 'The false Children of the Buffalo clan tag was removed. GAZ14 clan scopes are Bear, Horse, Elk, Turtle and Tiger. Real Iñupiat, Rarámuri and Anishinaabe contexts remain distinct from fictional campaign adaptations.']
lines += ['', '## Source-book name indexes', '', '| Source (full chapter audit pending) | Selected names |', '|---|---:|']
lines += [f'| {k} | {v:,} |' for k,v in r['setting_reference_records'].items()]
lines += ['', 'Every compiled record includes source references, applied changes, verification status and a content fingerprint. Large source-reference totals are not completed 2024 conversions.']
(C/'reports/RESEARCH.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(r))
