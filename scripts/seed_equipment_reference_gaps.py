#!/usr/bin/env python3
"""Small evidence-backed reference batches for remaining requested edition families."""
import json,time
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'catalog/raw/setting-reference-indexes';out.mkdir(parents=True,exist_ok=True)
for key,label,entity,ruleset,url,entries,note in [
 ('return-temple-reference','Return to the Temple of Elemental Evil','return-temple','dnd-3e','https://en.wikipedia.org/wiki/Return_to_the_Temple_of_Elemental_Evil',[('Orb of Oblivion','wondrous-item'),('Orb of Silvery Death','wondrous-item')],'Two named artifact leads attested by public indexed appendix excerpts; original 3.0 pages not verified. No artifact mechanics imported.'),
 ('arms-equipment-3e-reference','Arms and Equipment Guide (3e)','arms-equipment-3e','dnd-3e','https://manuals.plus/m/fe584cc50f1d9d620c5864ae7681abaacbc445244b4321dc6ceb84e21807ac6d',[('Amulet of Ooze Riding','wondrous-item')],'Selected table-of-contents name lead only; not a complete equipment or magic-item import.'),
 ('amazons-valkyries-equipment-reference','Amazons vs Valkyries: Arms and Equipment','amazons-valkyries-equipment','third-party-5e','https://d1vzi28wh99zvq.cloudfront.net/pdf_previews/329482-sample.pdf',[(n,'armor') for n in ['Manica','Cardiophylax','Lamellar, Bone or Horn','Helm and Greaves','Lamellar, Leather','Linothorax (Poor)','Scale Mantle','Linothorax (Good)','Lamellar, Metal','Banded Mail']],'Selected armor names from the publisher’s 2024 revised preview p.5. This is one third-party 5e guide, not an official same-title successor to the 3e book. No modified armor rules, source illustrations, feats or source prose imported.')]:
 records=[{'name':n,'source_type':t,'url':url,'evidence_kind':'publisher-preview-name-table' if key.startswith('amazons') else 'secondary-indexed-name-lead','source_note':note,'original_book_verified':False,'ninja_relevance':'backlog'} for n,t in entries]
 if key=='return-temple-reference':
  for r in records:r['url']='https://anyflip.com/vmtwn/jpyq/basic/151-200'
 data={'source_id':key,'label':label,'entity_id':'publication:'+entity,'ruleset':ruleset,'source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':note,'records':records}
 if key=='return-temple-reference':data['setting_id']='greyhawk'
 (out/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
p=ROOT/'catalog/settings/backlog/research-pack.json';d=json.loads(p.read_text())
for key,label in [('return-temple','Return to the Temple of Elemental Evil'),('arms-equipment-3e','Arms and Equipment Guide (3e)'),('adventurers-vault-1','Adventurer’s Vault'),('adventurers-vault-2','Adventurer’s Vault 2'),('amazons-valkyries-equipment','Amazons vs Valkyries: Arms and Equipment')]:
 if not any(e['id']=='publication:'+key for e in d['entities']):d['entities'].append({'id':'publication:'+key,'kind':'publication','label':label,'aliases':[],'parent_ids':[],'note':'Selected source reference metadata; original book audit and 2024 conversion pending.'})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False))
p=ROOT/'catalog/resources/requested-resources.json';d=json.loads(p.read_text())
if not any(r['id']=='amazons-valkyries-equipment' for r in d['resources']):d['resources'].append({'id':'amazons-valkyries-equipment','label':'Amazons vs Valkyries: Arms and Equipment','kind':'publication','aliases':['Bloodstone Press 5e equipment guide'],'bibliography_url':'https://d1vzi28wh99zvq.cloudfront.net/pdf_previews/329482-sample.pdf','selectors':{'entity_ids':['publication:amazons-valkyries-equipment']},'child_resource_ids':[],'original_item_audit_status':'pending','coverage_note':'One explicitly identified third-party guide within the user’s open 5e equipment-guide category. Preview names only; no exact-title equivalence to WotC 3e guide.','request_scope':'resolved-candidate-within-requested-source-category'})
next(r for r in d['resources'] if r['id']=='arms-equipment-5e')['child_resource_ids']=['amazons-valkyries-equipment']
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False))
p=ROOT/'catalog/item.schema.json';d=json.loads(p.read_text())
for ruleset in ['dnd-3e','dnd-4e','adnd-2e']:
 if ruleset not in d['properties']['ruleset']['enum']:d['properties']['ruleset']['enum'].append(ruleset)
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('Remaining equipment/Temple batch: 13 selected reference names')
