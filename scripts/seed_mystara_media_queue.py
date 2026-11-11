#!/usr/bin/env python3
"""Register researched Mystara media; a title/queue entry never creates an item."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];F=ROOT/'catalog/settings/mystara-media';F.mkdir(parents=True,exist_ok=True)
url='https://pandius.com/prodlist.html';timeline='https://pandius.com/vgamtime.html'
games=[('shadow-over-mystara','Dungeons & Dragons: Shadow over Mystara',['Shadow of Mystara'],'game-item-index-pending'),('tower-of-doom','Dungeons & Dragons: Tower of Doom',[],'game-item-index-pending'),('order-of-griffon','Dungeons & Dragons: Order of the Griffon',[],'game-item-index-pending'),('warriors-eternal-sun','Dungeons & Dragons: Warriors of the Eternal Sun',[],'game-item-index-pending'),('fantasy-empires','Fantasy Empires',[],'equipment-and-construction-audit-pending'),('dnd-stronghold-1993','Dungeons & Dragons: Stronghold (1993)',['Stronghold 1993'],'setting-placement-and-construction-audit-pending'),('chronicles-of-mystara','Dungeons & Dragons: Chronicles of Mystara',[],'compilation-deduplication-required')]
novels=[('tainted-sword','The Tainted Sword','Penhaligon Trilogy'),('dragons-tomb','The Dragon’s Tomb','Penhaligon Trilogy'),('fall-of-magic','The Fall of Magic','Penhaligon Trilogy'),('rogues-riches','Rogues to Riches','Young Quest'),('son-of-dawn','Son of Dawn','Young Quest'),('dragonlord-mystara','Dragonlord of Mystara','Dragonlord Chronicles'),('dragonking-mystara','Dragonking of Mystara','Dragonlord Chronicles'),('dragonmage-mystara','Dragonmage of Mystara','Dragonlord Chronicles'),('dark-knight-karameikos','Dark Knight of Karameikos',None),('black-vessel','The Black Vessel',None)]
entities=[];tasks=[];resources=[]
def resource(key,label,kind,entity,aliases=(),children=(),note=''):
 return {'id':key,'label':label,'kind':kind,'aliases':list(aliases),'bibliography_url':timeline if kind=='game' else url,'selectors':{'entity_ids':[entity]} if entity else {},'child_resource_ids':list(children),'original_item_audit_status':'pending','coverage_note':note or 'Bibliographic/media identity only. No item inventory or original-text audit completed.','request_scope':'user-requested-mystara-games-and-novels'}
for slug,label,aliases,status in games:
 eid='game:'+slug
 entities.append({'id':eid,'kind':'game','label':label,'aliases':aliases,'parent_ids':[] if slug=='dnd-stronghold-1993' else ['setting:mystara'],'note':'Compilation of Tower of Doom and Shadow over Mystara; do not duplicate their item definitions.' if slug=='chronicles-of-mystara' else 'Mystara placement is a fan research lead requiring verification, not a confirmed setting attribution; distinct from Stronghold Crusader.' if slug=='dnd-stronghold-1993' else 'Game source kept separate from tabletop Gazetteer canon. Item rules require explicit 2024 adaptation.'})
 tasks.append({'id':'media:'+slug,'entity_id':eid,'label':label,'medium':'game','status':status,'priority':'after-current-gazetteer-pass','evidence_urls':[timeline],'item_ids':[],'categories':['weapons','armor','tools-gear','consumables','magic-relics','construction'],'completed_item_audit':False})
 resources.append(resource('media-'+slug,label,'game',eid,aliases,note=entities[-1]['note']))
for slug,label,series in novels:
 eid='publication:novel-'+slug
 entities.append({'id':eid,'kind':'publication','label':label,'aliases':[],'parent_ids':['setting:mystara'],'note':'Mystara novel bibliography. Named equipment needs an inspected passage or attributed item-specific secondary evidence; a novel title is not an item definition.'})
 tasks.append({'id':'novel:'+slug,'entity_id':eid,'label':label,'series':series,'medium':'novel','status':'equipment-passage-audit-pending','priority':'after-current-gazetteer-pass','evidence_urls':[url],'item_ids':[],'categories':['weapons','armor','clothing','tools-gear','magic-relics','vehicles'],'completed_item_audit':False})
 resources.append(resource('novel-'+slug,label,'publication',eid))
resources += [resource('mystara-video-games','Mystara video-game equipment','series',None,children=['media-'+r[0] for r in games]),resource('mystara-novels','Mystara novel equipment','series',None,children=['novel-'+r[0] for r in novels])]
pack={'id':'mystara-media-registry','label':'Mystara video-game and novel research registry (no item definitions)','theme':'mystara-media','topic_entity_id':'setting:mystara','coverage':'Seven game/compilation research streams and ten novels registered. No item is inferred from a title. Stronghold placement remains uncertain; compilations require deduplication.','sources':[{'id':'mystara-media-bibliography','url':url,'kind':'fan-bibliography-and-medium-index','author':'Vaults of Pandius bibliography contributors'}],'entities':entities,'items':[],'filter_profiles':[]}
(F/'research-pack.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2)+'\n')
(F/'research-queue.json').write_text(json.dumps({'scope':'Item-specific evidence and later 2024 adaptation from Mystara games and novels','registration_is_not_import':True,'tasks':tasks},ensure_ascii=False,indent=2)+'\n')
p=ROOT/'catalog/resources/requested-resources.json';d=json.loads(p.read_text());ids={r['id'] for r in resources};d['resources']=[r for r in d['resources'] if r['id'] not in ids]+resources;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False))
print('Queued',len(games),'game/compilation streams and',len(novels),'novels; item definitions added: 0')
