"""Import curated 2024 drafts separately from source-only game reference indexes."""
from copy import deepcopy
import hashlib,json,re

def build_research_packs(items,icons,root):
    byid={i['id']:i for i in items};result=[];sources=[]
    for path in sorted((root/'catalog/settings').glob('*/research-pack.json')):
        pack=json.loads(path.read_text());refs={r['id']:r for r in pack['sources']};start=len(result)
        for row in pack['items']:
            base=deepcopy(byid[row['base_item_id']]) if row.get('base_item_id') else None
            name=row['name'];magic=row.get('magic',False);evidence=refs[row['evidence_ref']]
            item=deepcopy(base) if base else {'mechanics':{},'description':None}
            item.update(id=row['id'],name=name,name_key=name.casefold(),source_id=pack['id'],ruleset='dnd-2024',category=row['type'],type=row['type'],magic=magic,rarity=row.get('rarity'),requires_attunement=row.get('attunement',False),
                        content_status='original-conversion-draft',tabletop_status='draft-dm-review-required',image={**icons[row['icon']],'specific_art':None})
            item['tags']=sorted(set(row.get('tags',[]))|{'theme:'+pack.get('theme','ninja'),'source:'+pack['id'],'conversion:'+row['mode'],'magic' if magic else 'mundane'})
            item['provenance']={'provider':'Project original adaptation','evidence':evidence,'original_publication_verified':False,'locator':row.get('locator'),'base_rules_id':base['id'] if base else None}
            if row.get('source_note'):item['provenance']['adaptation_note']=row['source_note']
            if base:item['provenance']['base_rules_provenance']=base['provenance']
            item['description']=row['details'];item['mechanics']['original_adaptation_rules']=row['details'];item['mechanics']['automated_effects']=[]
            item['mechanics'].setdefault('source_fields',{})['cost']=str(row['estimated_value_gp'])
            item['conversion']={'kind':row['mode'],'version':'0.1.0','edition_target':'2024','changes':row['changes'],'pricing_status':'author-estimate-not-source-price','balance_status':'not-playtested','automated_effects_implemented':False}
            item['presentation']={k:row[k] for k in ['tldr','details','flavor']};item['presentation']['creative_use']={'text':row['creative'],'requires_dm_ruling':True}
            item['associations']=[{'entity_id':pack.get('topic_entity_id','topic:ninja-equipment'),'role':'inspired-by','status':'editorial-theme','evidence':evidence},{'entity_id':row['entity_id'],'role':'inspired-by','status':'original-draft-not-source-transcription','evidence':evidence}]
            item['associations'].extend(row.get('associations',[]))
            if row.get('record_kind'):item['record_kind']=row['record_kind']
            if row.get('structure'):item['structure']=deepcopy(row['structure'])
            if row.get('vehicle'):item['vehicle']=deepcopy(row['vehicle'])
            result.append(item)
        sources.append({'id':pack['id'],'name':pack['label'],'ruleset':'dnd-2024','record_count':len(result)-start,'source_url':pack['sources'][0]['url'],'coverage':pack['coverage'],'license_ids':['project-original-adaptations-plus-CC-BY-4.0-base-rules'],'distribution_status':'Original drafts, source names/references and attributed SRD base rules only. No official sourcebook prose or art.'})
    for path in sorted([*(root/'catalog/raw/game-reference-indexes').glob('*.json'), *(root/'catalog/raw/setting-reference-indexes').glob('*.json')]):
        data=json.loads(path.read_text());start=len(result)
        for link in data.get('existing_catalog_links', []):
            item = byid[link['item_id']]
            if item['name'] != link['name']:
                raise ValueError(f"Unexpected name for {link['item_id']} in {path}")
            evidence = {key: link[key] for key in ('url', 'kind', 'locator')}
            if 'note' in link:
                evidence['note'] = link['note']
            associations = item.setdefault('associations', [])
            if not any(a['entity_id'] == data['entity_id'] and a['role'] == 'appearance' for a in associations):
                associations.append({
                    'entity_id': data['entity_id'], 'role': 'appearance',
                    'status': link.get('status', 'publisher-confirmed'), 'evidence': evidence,
                })
            item['provenance'].setdefault('additional_sources', []).append(evidence)
        for row in data['records']:
            # A later source review can refine classification without changing the record ID.
            kind=row['source_type'];name=row['name'];typ,icon=classify_reference(row.get('verified_source_type',kind))
            identity=name.casefold()+'|'+kind.casefold();iid=data['source_id']+':'+hashlib.sha256(identity.encode()).hexdigest()[:16]
            evidence={'url':row['url'],'kind':row['evidence_kind'],'author':row.get('source_author'),'edition':row.get('reported_edition')};game=data.get('entity_id') or 'game:'+data['game_id'];ruleset=data.get('ruleset','game-reference')
            assoc=[{'entity_id':game,'role':'origin','status':'source-index-reference','evidence':evidence}]
            if data.get('game_id','').startswith('baldurs-gate-'):assoc.append({'entity_id':'setting:forgotten-realms','role':'setting','status':'game-setting','evidence':evidence})
            if data.get('game_id','').startswith('diablo-'):assoc.append({'entity_id':'setting:sanctuary','role':'setting','status':'game-setting','evidence':evidence})
            if data.get('setting_id'):assoc.append({'entity_id':'setting:'+data['setting_id'],'role':'setting','status':'source-setting','evidence':evidence})
            if data.get('game_id')=='planescape-torment':assoc.append({'entity_id':'setting:planescape','role':'setting','status':'game-setting','evidence':evidence})
            if data.get('game_id')=='conan-exiles':assoc.append({'entity_id':'setting:hyborian-age','role':'setting','status':'game-setting','evidence':evidence})
            if row.get('regional_entity_id'):assoc.append({'entity_id':row['regional_entity_id'],'role':row.get('regional_role','origin'),'status':row.get('regional_status','fan-created-regional-association'),'evidence':evidence})
            tags={'source:'+data['source_id'],'reference:source',game,'source-type:'+re.sub(r'[^a-z0-9]+','-',kind.casefold()).strip('-')}
            if row.get('ninja_relevance')=='direct':
                tags.add('theme:ninja');assoc.append({'entity_id':'topic:ninja-equipment','role':'inspired-by','status':'editorial-theme','evidence':evidence})
            entry={'id':iid,'name':name,'name_key':name.casefold(),'source_id':data['source_id'],'ruleset':ruleset,'category':typ,'type':typ,'magic':None,'rarity':None,'requires_attunement':None,'tags':sorted(tags),'description':None,'mechanics':{'source_type':kind,'reference_metadata':{k:v for k,v in row.items() if k not in ['name','url','evidence_kind']},'automated_effects':[]},'provenance':{'provider':row.get('provider','Public source reference index'),'source_url':row['url'],'retrieved_at':data['retrieved_at'],'upstream_commit':data.get('upstream_commit'),'evidence':evidence,'locator':row.get('locator') or row.get('reported_locator')},'content_status':'factual-metadata-only','tabletop_status':'adaptation-needed','image':{**icons[icon],'specific_art':None},'associations':assoc,'presentation':{'tldr':'Source item reference; 2024 compatibility or adaptation is pending.','details':None,'flavor':None,'creative_use':{'text':None,'requires_dm_ruling':True}}}
            if row.get('pdf_sha256'):
                entry['provenance']['source_file_sha256']=row['pdf_sha256']
            if row.get('original_book_verified'):
                entry['provenance'].update(original_publication_verified=True,legacy_page_verified=True,verified_fields=row.get('verified_fields',[]),source_file_sha256=row.get('preview_sha256') or row.get('pdf_sha256'),local_file=row.get('local_pdf'),locator=row.get('locator'),verification_scope=row.get('verification_scope','Item name and appearance in the cited public preview only; rules and full-book completeness are not verified.'))
            if row.get('record_kind'):
                entry['record_kind']=row['record_kind'];entry['tags']=sorted(set(entry['tags'])|{'theme:worldbuilding'})
                entry['associations'].append({'entity_id':'topic:worldbuilding','role':'inspired-by','status':'editorial-theme','evidence':evidence})
            result.append(entry)
        sources.append({'id':data['source_id'],'name':data.get('source_name',data.get('label',data.get('game_id','Source'))+' public item reference index'),'ruleset':data.get('ruleset','game-reference'),'record_count':len(result)-start,'source_url':data['source_url'],'license_ids':['metadata-only-no-content-license-claimed'],'coverage':data['coverage'],'distribution_status':'Factual names/types/source references only. Game prose, mechanics, art and code not included.'})
    return result,sources

def classify_reference(kind):
    k=kind.casefold()
    exact={'food':('food','food'),'furnishing':('furnishing','gear'),'wondrous-item':('wondrous-item','gear'),'buildingitem':('construction-component','gear'),'decoration':('construction-component','gear'),'craftingstations':('construction-component','gear'),'material':('material','gear'),'component':('material','gear'),'consumable':('consumable','potion'),'tools':('tools','tools'),'warpaints':('dye','dye'),'tattoo':('wondrous-item','gear'),'tattoos':('wondrous-item','gear'),'teeth':('weapon','dagger'),'eyes':('wondrous-item','gear'),'lenses':('wondrous-item','gear'),'earrings':('wondrous-item','amulet'),'edged':('weapon','sword'),'missiles':('ammunition','ammunition'),'candy':('consumable','food'),'construction-component':('construction-component','gear'),'weapons':('weapon','weapon'),'weapon':('weapon','weapon'),'jewelry':('amulet','amulet'),'clothing':('clothing','clothing'),'miscellaneous':('misc','gear'),'scroll':('scroll','scroll'),'scrolls':('scroll','scroll'),'books':('book','book'),'book':('book','book'),'ammunition':('ammunition','ammunition'),'potion':('potion','potion'),'potions':('potion','potion'),'keys':('key','key'),'key':('key','key'),'gems':('gem','gem'),'pelts':('helmet','helmet'),'barbhelms':('helmet','helmet'),'shrunkenheads':('shield','shield'),'gloves':('gloves','gloves'),'cloak':('cloak','cloak')}
    if k in ('orb', 'rod', 'spellcasting-focus'):
        return 'spellcasting-focus', 'gear'
    if k == 'item-set':
        return 'item-set', 'gear'
    if k == 'musical-instruments':
        return 'instrument', 'instrument'
    if k in {'land-vehicle', 'waterborne-vehicle', 'mount'}:
        return k, k
    if k == 'flying-vehicle':
        return k, 'gear'
    if k in ('container', 'containers'):
        return 'container', 'container'
    if k in exact:return exact[k]
    for terms,typ,icon in [(['ring','finger'],'ring','ring'),(['amulet','neck'],'amulet','amulet'),(['helm','head','circlet'],'helmet','helmet'),(['glove','hands'],'gloves','gloves'),(['boot','feet'],'boots','boots'),(['belt','waist'],'belt','belt'),(['shield','mojo','source','quiver'],'shield','shield'),(['armor','armour','torso','shoulder','wrists','legs','bracer','pant','leather','chain','plate'],'armor','armor'),(['prosthetic'],'wondrous-item','tools'),(['dagger','knife','katars','assassin','fist','claw'],'weapon','dagger'),(['sword','odachi'],'weapon','sword'),(['axe','hatchet'],'weapon','axe'),(['spear','polearm','glaive'],'weapon','spear'),(['staff','staves','daibo'],'weapon','staff'),(['bow','ranged'],'weapon','bow'),(['mace','hammer','club'],'weapon','hammer'),(['flail','kusarigama','tonfa'],'weapon','flail'),(['wand'],'wand','wand')]:
        if any(t in k for t in terms):return typ,icon
    return 'misc','gear'
