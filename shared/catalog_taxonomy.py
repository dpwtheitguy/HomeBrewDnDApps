"""Entity aliases, geographic descendants and evidence-backed item associations."""
import json,re,unicodedata
from pathlib import Path

def key(value):
    return re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().casefold())

class Taxonomy:
    def __init__(self,path):
        data=json.loads(Path(path).read_text());self.entities={r['id']:r for r in data['entities']};self.aliases={}
        for row in self.entities.values():
            for label in [row['id'],row['id'].split(':',1)[1],row['label'],*row['aliases']]:
                self.aliases.setdefault(key(label),set()).add(row['id'])
    def resolve(self,value,kind=None):
        matches={eid for eid in self.aliases.get(key(value),set()) if kind is None or self.entities[eid]['kind']==kind}
        if len(matches)!=1: raise ValueError(f'Unknown or ambiguous {kind or "origin"}: {value}')
        return next(iter(matches))
    def descendants(self,eid):
        if eid not in self.entities: raise ValueError('Unknown entity '+eid)
        result={eid}
        while True:
            added={r['id'] for r in self.entities.values() if set(r['parent_ids'])&result}
            if added<=result:return result
            result|=added

def associate(item,taxonomy):
    associations=list(item.get('associations',[]))
    def add(eid,role,evidence,status):
        if eid not in taxonomy.entities: raise ValueError('Unknown association '+eid)
        if not any(a['entity_id']==eid and a['role']==role for a in associations):
            associations.append({'entity_id':eid,'role':role,'evidence':evidence,'status':status})
    if 'mystara' in item.get('setting_ids',[]):
        evidence=item['provenance'].get('evidence',{})
        add('setting:mystara','setting',evidence,'draft-setting-association')
        for region in item.get('conversion',{}).get('culture_ids',[]):
            eid='region:'+region
            if eid in taxonomy.entities:add(eid,'cultural-association',evidence,'fan-reported-unverified')
    for culture in item.get('conversion',{}).get('cultural_identity_ids',[]):
        add(culture,'cultural-association',item['provenance'].get('evidence',{}),'editorial-regional-style-inference')
    if item['ruleset']=='bg3':
        add('setting:forgotten-realms','setting',{'url':item['provenance'].get('source_url')},'game-setting')
        add('game:baldurs-gate-3','origin',{'url':item['provenance'].get('source_url')},'game-source')
    item['associations']=associations
    item['setting_ids']=sorted({a['entity_id'].split(':',1)[1] for a in associations if a['entity_id'].startswith('setting:') and a['role']=='setting'})
    item['origin_region_ids']=sorted({a['entity_id'] for a in associations if a['entity_id'].startswith('region:') and a['role'] in ('origin','cultural-association')})
    item['origin_culture_ids']=sorted({a['entity_id'] for a in associations if a['entity_id'].startswith('culture:') and a['role'] in ('origin','cultural-association')})
    tags=set(item['tags'])
    # Earlier drafts used culture tags for regions. Replace those with typed region tags.
    for region in item.get('conversion',{}).get('culture_ids',[]):tags.discard('culture:'+region)
    for a in associations:
        tags.add(a['role']+':'+a['entity_id'])
        if a['role'] in ('setting','origin','cultural-association'):tags.add(a['entity_id'])
    item['tags']=sorted(tags)
    item['family_id']=item.get('conversion',{}).get('parent_item_id') or item['id']
    item['base_item_id']=item.get('provenance',{}).get('base_rules_id')
    item['taxonomy_status']='partially-attributed' if associations else 'unattributed'
    return item
