#!/usr/bin/env python3
"""Persist an entity × category coverage matrix. Never marks a search complete by inference."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CAT=ROOT/'catalog'
path=CAT/'taxonomy/entities.json';data=json.loads(path.read_text());entities={x['id']:x for x in data['entities']}
def add(kind,key,label,parent,source,**extra):
 eid=kind+':'+key
 if eid not in entities:entities[eid]={'id':eid,'kind':kind,'label':label,'aliases':[],'parent_ids':[parent], 'evidence_url':source,'registry_status':'research-scope-not-fully-audited',**extra}
add('region','atruaghin-elk','Children of the Elk','region:atruaghin','https://www.pandius.com/atruitem.html',note='Fan source index association; original gazetteer not checked.')
people=json.loads((CAT/'settings/mystara/people-research-index.json').read_text())
slug=lambda x:re.sub(r'[^a-z0-9]+','-',x.casefold()).strip('-')
singulars={'Halflings':['Halfling','Hin'],'Lupins':['Lupin'],'Rakastas':['Rakasta'],'Tortles':['Tortle'],'Dwarves':['Dwarf'],'Elves':['Elf']}
for label in people['people']:
 add('people',slug(label),label,'setting:mystara',people['source_url'],note='Fan index heading; can be a broad group, creature, ancestry or fan addition. No playable species mechanics inferred.')
for label,aliases in singulars.items():
 if 'people:'+slug(label) in entities: entities['people:'+slug(label)]['aliases']=aliases
add('people','shadow-elves','Shadow Elves','people:elves','https://www.pandius.com/soulxtal.html',note='A setting people; not the Shadow Elf Territories region or a 2024 playable-species conversion.')
for label in people['hollow_world_cultures']:
 add('culture','hollow-'+slug(label),label+' (Hollow World)','region:hollow-world',people['hollow_culture_source'],note='Cultural identity; not automatic proficiency or a 2024 species.')
for key,label in [('robrenn','Robrenn'),('eusdria','Eusdria'),('renardy','Renardy'),('herath','Herath'),('slagovich','Slagovich'),('nimmur','Nimmur'),('shazak','Shazak'),('bellayne','Bellayne'),('torreon','Torreón'),('narvaez','Narvaez'),('saragon','Saragón'),('almarron','Almarrón'),('gargona','Gargoña'),('cimmaron','Cimmaron'),('guadalante','Guadalante'),('vilaverde','Vilaverde'),('texeiras','Texeiras')]:
 add('region',key,label,'region:savage-coast','https://www.pandius.com/svge_cst.html',note='Country or territory; boundaries and timeline require source-specific verification.')
for key,label in [('norwold','Norwold'),('heldann','Heldannic Territories'),('wendar','Wendar'),('denagoth','Denagoth'),('sind','Sind'),('ochalea','Ochalea'),('ostland','Ostland'),('vestland','Vestland'),('soderfjord','Soderfjord'),('qeodhar','Qeodhar'),('pearl-islands','Pearl Islands')]:
 add('region',key,label,'setting:mystara','https://www.pandius.com/magical_research_artefacts_optional_rules.pdf',note='Wider Mystara scope; parent is world, not an assertion that every region is part of the Known World.')
data['entities']=sorted(entities.values(),key=lambda x:x['id']);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
try:
 import yaml
 path.with_suffix('.yaml').write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True))
except ImportError:pass
CATEGORIES={'weapons':'weapons swords bows blades','armor':'armor armour shields helmets','clothing':'clothing dress jewelry textiles','tools-gear':'tools equipment instruments adventuring gear','trade-goods':'trade goods crafts food materials currency','consumables':'potions elixirs oils poisons medicines','magic-relics':'magic items relics artifacts enchanted','vehicles':'vehicles ships skyships mounts saddles'}
qpath=CAT/'research/queue.json';qpath.parent.mkdir(exist_ok=True)
old={x['id']:x for x in json.loads(qpath.read_text())['tasks']} if qpath.exists() else {}
tasks=[]
# Existing Mystara parent chain determines scope; don't mix Forgotten Realms entities into Mystara.
def in_mystara(eid,seen=None):
 if eid=='setting:mystara':return True
 seen=set() if seen is None else seen
 if eid in seen:return False
 seen.add(eid)
 return any(in_mystara(p,seen) for p in entities[eid]['parent_ids'])
for eid,e in sorted(entities.items()):
 if e['kind'] not in ('region','culture','people') or not in_mystara(eid):continue
 for cat,terms in CATEGORIES.items():
  tid='mystara:'+eid+':'+cat
  priority=0 if eid in ('region:karameikos','region:glantri') else 1 if e['kind']=='region' else 2
  row={'id':tid,'setting_id':'mystara','entity_id':eid,'label':e['label'],'category':cat,'priority':priority,
       'queries':[f'site:pandius.com "{e["label"]}" ({terms.replace(" "," OR ")})',f'"Mystara" "{e["label"]}" "{terms.split()[0]}"'],
       'status':'unsearched','search_attempts':0,'evidence':[],'item_ids':[],
       'negative_result_policy':'A failed search does not prove absence; preserve source and query history.'}
  if tid in old:row=old[tid]
  tasks.append(row)
for setting in ['forgotten-realms','planescape','ravenloft','greyhawk','sanctuary']:
 tid='discover:'+setting
 tasks.append(old.get(tid,{'id':tid,'setting_id':setting,'entity_id':'setting:'+setting,'label':entities['setting:'+setting]['label'],'category':'entity-discovery','priority':3,'queries':[f'{entities["setting:"+setting]["label"]} nations cultures peoples equipment source index'],'status':'unsearched','search_attempts':0,'evidence':[],'item_ids':[]}))
tasks.sort(key=lambda x:(x['priority'],x['entity_id'],x['category']))
qpath.write_text(json.dumps({'schema_version':1,'scope':'Seed registry, not an exhaustive nation/species list. Mystara first.','categories':CATEGORIES,'tasks':tasks},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'entities':len(entities),'research_tasks':len(tasks),'previous_progress_preserved':len(set(old)&{x['id'] for x in tasks})}))
