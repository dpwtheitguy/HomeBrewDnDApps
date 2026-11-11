"""Manifest-driven adventure research drafts and deduplicated source appearances."""
from copy import deepcopy
import json
from pathlib import Path

def build_adventure_packs(items, icons, root):
    result=[]; sources=[]; byid={i['id']:i for i in items}
    for path in sorted((root/'catalog/settings').glob('*/adventure-pack.json')):
        pack=json.loads(path.read_text()); refs={r['id']:r for r in pack['sources']}
        for appearance in pack['appearances']:
            target=byid[appearance['item_id']]
            target.setdefault('associations',[]).append({'entity_id':appearance['entity_id'],'role':'found-in','status':appearance['status'],'evidence':{**refs[appearance['evidence_ref']],'locator':appearance['locator'],'mapping_note':appearance['mapping_note']}})
        for row in pack['drafts']:
            evidence=refs[row['evidence_ref']]; setting=row['setting_id']; name=row['name']
            associations=[{'entity_id':'setting:'+setting,'role':'setting','status':'editorial-pack-grouping','evidence':evidence},{'entity_id':row['entity_id'],'role':'inspired-by','status':'original-draft-from-research','evidence':evidence}]
            associations.extend(row.get('associations',[]))
            result.append({'id':row['id'],'name':name,'name_key':name.casefold(),'source_id':pack['id'],'ruleset':'dnd-2024','category':row['type'],'type':row['type'],
              'magic':True,'rarity':row['rarity'],'requires_attunement':row['attunement'],'tags':['magic','source:'+pack['id'],'conversion:homebrew','rarity:'+row['rarity']],
              'description':row['details'],'mechanics':{'source_fields':{'cost':str(row['estimated_value_gp'])},'original_adaptation_rules':row['details'],'automated_effects':[]},
              'provenance':{'provider':'Project original adaptation','evidence':evidence,'locator':row['locator'],'legacy_page_verified':row.get('legacy_page_verified',False),'original_publication_verified':False},
              'content_status':'original-conversion-draft','tabletop_status':'draft-dm-review-required','image':{**icons[row['icon']],'specific_art':None},'associations':associations,
              'conversion':{'kind':'original-homebrew-adaptation','version':'0.1.0','edition_target':'2024','changes':row['changes'],'pricing_status':'author-estimate-not-source-price','balance_status':'not-playtested','automated_effects_implemented':False},
              'presentation':{'tldr':row['tldr'],'flavor':row['flavor'],'details':row['details'],'creative_use':{'text':row['creative'],'requires_dm_ruling':True}}})
        for item, row in zip(result[-len(pack['drafts']):], pack['drafts']):
            if row.get('base_item_id'):
                base=byid[row['base_item_id']]
                item['provenance']['base_rules_id']=base['id']
                item['provenance']['base_rules_provenance']=base['provenance']
                for field in ('weapon','armor','properties'):
                    if field in base['mechanics']:item['mechanics'][field]=deepcopy(base['mechanics'][field])
        sources.append({'id':pack['id'],'name':pack['label'],'ruleset':'dnd-2024','record_count':len(pack['drafts']),'source_url':pack['sources'][0]['url'],'license_ids':['project-original-adaptations'], 'coverage':pack['coverage'],'distribution_status':'Original homebrew drafts; source adventure text and artwork excluded.'})
    return result,sources

def merge_entities(root):
    """Keep pack extensions reproducible after reseeding the base vocabulary."""
    import yaml
    path=root/'catalog/taxonomy/entities.json'; data=json.loads(path.read_text()); entities={r['id']:r for r in data['entities']}
    for pack in sorted([*(root/'catalog/settings').glob('*/adventure-pack.json'), *(root/'catalog/settings').glob('*/research-pack.json')]):
        for row in json.loads(pack.read_text())['entities']: entities[row['id']]=row
    data['entities']=sorted(entities.values(),key=lambda r:r['id'])
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');path.with_suffix('.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))

    profiles=root/'catalog/filters/presets.json'
    if profiles.exists():
        preset=json.loads(profiles.read_text())
        if not any(p['id']=='thunder-rift-workbench' for p in preset['profiles']):
            preset['profiles'].append({'id':'thunder-rift-workbench','label':'Thunder Rift research workbench','filters':{'settings':['thunder-rift']},'note':'Original drafts only; source appearances can be found through publication facets. Original-book audits remain pending.'})
        saved={p['id']:p for p in preset['profiles']}
        for path in sorted((root/'catalog/settings').glob('*/research-pack.json')):
            for profile in json.loads(path.read_text()).get('filter_profiles',[]):saved[profile['id']]=profile
        preset['profiles']=list(saved.values())
        profiles.write_text(json.dumps(preset,ensure_ascii=False,indent=2)+'\n'); profiles.with_suffix('.yaml').write_text(yaml.safe_dump(preset,allow_unicode=True,sort_keys=False))
    roadmap=root/'catalog/source-roadmap.json'
    if roadmap.exists():
        road=json.loads(roadmap.read_text())
        for path in sorted((root/'catalog/settings').glob('*/research-queue.json')):
            for work in json.loads(path.read_text()).get('workstreams',[]):
                row=next((r for r in road['sources'] if r['id']==work['id']),None)
                if row is None:
                    row={'id':work['id'],'label':work['label'],'priority':1};road['sources'].append(row)
                row['status']=work['status']
        roadmap.write_text(json.dumps(road,ensure_ascii=False,indent=2)+'\n');roadmap.with_suffix('.yaml').write_text(yaml.safe_dump(road,allow_unicode=True,sort_keys=False))
