#!/usr/bin/env python3
"""Closed ledger of explicitly requested sources plus enumerated Mystara inventory.
Registration is not item-audit completion. Ambiguous edition families stay explicit.
"""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'catalog/resources';out.mkdir(parents=True,exist_ok=True)
resources=[]
def add(i,label,kind,url,selectors=None,aliases=(),children=(),note=''):
 resources.append({'id':i,'label':label,'kind':kind,'aliases':list(aliases),'bibliography_url':url,'selectors':selectors or {},'child_resource_ids':list(children),'original_item_audit_status':'pending','coverage_note':note,'request_scope':'user-requested-or-enumerated-subsource'})
mystara=json.loads((ROOT/'catalog/settings/mystara/source-inventory.json').read_text())
canonical={'TSR-1037':'dawn-emperors','TSR-1094':'champions-mystara','TSR-2500':'karameikos-box','TSR-2502':'hail-the-heroes','TSR-2509':'night-of-the-vampire','TSR-2511':'glantri-box','TSR-2513':'mark-of-amber','DRAGONS-DEN':'dragons-den','GOBLINS-LAIR':'goblins-lair','HAUNTED-TOWER':'haunted-tower'}
for r in mystara:
 iid=canonical.get(r['id'],'mystara-'+r['id'].casefold())
 selector={'reported_book_codes':[r['id']]}
 if r['id'].startswith('GAZ'):selector['entity_ids']=['publication:gaz14'] if r['id']=='GAZ14' else []
 known={'dawn-emperors':['publication:dawn-emperors'],'champions-mystara':['publication:champions-mystara'],'karameikos-box':['region:karameikos'],'glantri-box':['region:glantri'],'hail-the-heroes':['publication:hail-the-heroes'],'night-of-the-vampire':['publication:night-of-the-vampire'],'mark-of-amber':['publication:mark-of-amber'],'dragons-den':['publication:dragons-den'],'goblins-lair':['publication:goblins-lair'],'haunted-tower':['publication:haunted-tower']}
 if iid in known:selector['entity_ids']=known[iid]
 add(iid,r['title'],'publication',r['bibliography_url'],selector,[r['id']],note=r.get('note','')+' Regional matches are contextual leads, not proof of appearance in this exact book.')
add('setting-mystara','Mystara','setting','https://www.pandius.com/',{'entity_ids':['setting:mystara']},['Mystara campaign setting'])
add('known-world','The Known World','region','https://www.pandius.com/guide/',{'entity_ids':['region:known-world']},['Known World'])
add('mystara-gazetteers','Mystara Gazetteers GAZ1–GAZ14','source-series','https://www.acaeum.com/indexes/miscellaneous/gaz.html',children=['mystara-gaz'+str(n) for n in range(1,15)],note='All fourteen titles are registered individually; original item audits remain separate.')
add('mystara-boxed-sets','Mystara boxed sets','source-series','https://www.pandius.com/mclctrgd.html',children=[canonical.get(r['id'],'mystara-'+r['id'].casefold()) for r in mystara if r['kind'] in ['campaign-box','adventure-box']],note='The enumerated campaign/adventure-box inventory is a bibliographic starting set, not an assertion that adjacent Basic/Thunder Rift products share canonical geography.')
for key,label in [('thyatian','Thyatian'),('alphatian','Alphatian')]:add('culture-'+key,label+' equipment','culture','https://www.pandius.com/',{'entity_ids':['culture:'+key,'region:'+('thyatis' if key=='thyatian' else 'alphatia')]},[key])
for key,label,aliases in [('forgotten-realms','Forgotten Realms',['Faerûn']),('planescape','Planescape',['Platescape']),('ravenloft','Ravenloft',[]),('greyhawk','Greyhawk',[])]:add('setting-'+key,label,'setting','https://en.wikipedia.org/wiki/'+label.replace(' ','_'),{'entity_ids':['setting:'+key]},aliases)
for key,label,url in [('baldurs-gate-1','Baldur’s Gate I','https://baldursgateee.th.gl/db/inventory'),('baldurs-gate-2','Baldur’s Gate II','https://mikesrpgcenter.com/bgate2/'),('baldurs-gate-3','Baldur’s Gate 3','https://bg3.wiki/'),('diablo-1','Diablo I','https://diablobytes.com/diablo-i/items/uniques/'),('diablo-2','Diablo II','https://classic.battle.net/diablo2exp/items/'),('diablo-3','Diablo III','https://github.com/d07RiV/d3planner'),('diablo-4','Diablo IV','https://diablo4.th.gl/db/uniques')]:
 add(key,label,'game',url,{'entity_ids':['game:'+key]},note='Selected public metadata only. Game versions and tabletop conversion completeness are not inferred.')
for key,label,url,entity,aliases in [
 ('zanzer',"Zanzer’s Dungeon / Escape from Zanzer’s Dungeon",'https://pandius.ix.iq.pl/zanzrtem.html','publication:zanzer',["Zanzars Dungeon","Zanzar’s Dungeon"]),
 ('return-temple','Return to the Temple of Elemental Evil','https://en.wikipedia.org/wiki/Return_to_the_Temple_of_Elemental_Evil','publication:return-temple',[]),
 ('complete-ninja-handbook',"The Complete Ninja’s Handbook (2e)",'https://d1vzi28wh99zvq.cloudfront.net/pdf_previews/16904-sample.pdf','publication:complete-ninja-handbook',['2nd edition Ninjas handbook','PHBR15']),
 ('oriental-adventures-3e','Oriental Adventures (2001, 3.0)','https://dnd-wiki.org/wiki/Publication%3AOriental_Adventures_%283e%29','publication:oriental-adventures-3e',['Oriental Adventures 3rd edition']),
 ('hero-builder-3e','Hero Builder’s Guidebook','https://www.tsrarchive.com/3e/3e2-pa.html','publication:hero-builder-3e',['hero builders guidebook']),
 ('curse-of-strahd','Curse of Strahd','https://cori-spells.github.io/wikidot/dnd5e.wikidot.com/wondrous-items_cos.html','publication:curse-of-strahd',[]),
 ('tomb-annihilation','Tomb of Annihilation','https://dnd5e.wikidot.com/wondrous-items:toa','publication:tomb-annihilation',[]),
 ('rime-frostmaiden','Icewind Dale: Rime of the Frostmaiden','https://dnd5e.wikidot.com/wondrous-items:id:rf','publication:rime-frostmaiden',['Frostmaidens','Rime of the Frostmaiden'])]:add(key,label,'publication',url,{'entity_ids':[entity]},aliases,note='Source title registered; selected references or drafts do not certify full original-book coverage.')
add('arms-equipment-3e','Arms and Equipment Guide (2003, 3.0)','publication','https://dnd-wiki.org/wiki/Publication%3AArms_and_Equipment_Guide_%283e%29',{'entity_ids':['publication:arms-equipment-3e']})
add('adventurers-vault-1','Adventurer’s Vault (4e)','publication','https://forgottenrealms.fandom.com/wiki/Adventurer%27s_Vault',{'entity_ids':['publication:adventurers-vault-1']})
add('adventurers-vault-2','Adventurer’s Vault 2 (4e)','publication','https://forgottenrealms.fandom.com/wiki/Adventurer%27s_Vault_2',{'entity_ids':['publication:adventurers-vault-2']})
add('arms-equipment-4e','4e arms and equipment guides','source-category','https://forgottenrealms.fandom.com/wiki/Adventurer%27s_Vault',children=['adventurers-vault-1','adventurers-vault-2'],note='Interpreted as the Adventurer’s Vault series; not an official 4e book with the exact 3e title.')
add('arms-equipment-5e','5e arms and equipment guides','source-category','https://www.dndbeyond.com/equipment',{'source_ids':['open5e-srd-2014','open5e-srd-2024']},note='An open source category, not a uniquely identified official title. Core equipment is present. Specific third-party guides need individual bibliography and item audits; no exact-title equivalence claimed.')
add('core-5e','D&D 5e / 2014 core equipment','rules-source','https://www.dndbeyond.com/srd',{'source_ids':['open5e-srd-2014']},note='Open SRD coverage only; not every PHB/DMG/Monster Manual item or illustration.')
add('core-2024','D&D revised 2024 / 5.5e core equipment','rules-source','https://www.dndbeyond.com/srd',{'source_ids':['open5e-srd-2024']},note='Open SRD coverage only; full core-book audit and executable mechanics remain pending.')
add('worldbuilding','Worldbuilding: camp, fort, castle, city, village and dungeon','topic','https://www.dndbeyond.com/posts/1828-exploring-bastions-from-the-2024-dungeon-masters',{'entity_ids':['topic:worldbuilding']},['world building'])
add('indigenous-game-inspiration','Indigenous-led game and media inspiration','source-category','https://www.neveralonegame.com/never-alone',{'entity_ids':['game:never-alone','game:mulaka','game:when-rivers-were-trails']},note='Distinct Iñupiat, Rarámuri and Anishinaabe contexts; current campaign adaptations are new fiction, not authentic artifacts. This is an open research category, not a closed list of all Indigenous media.')
add('ninja-games-and-media','Ninja equipment across games and media','source-category','https://www.fromsoftware.jp/manual/sekiroshadowsdietwice/stadia/action2.html',{'entity_ids':['topic:ninja-equipment']},note='An open research category. The current selected game indexes do not mean every ninja game has been audited.')
# Include the additional worldbuilding titles used to answer the user’s question.
for key,label,url,entity in [('stronghold-builder-3e','Stronghold Builder’s Guidebook','https://en.wikipedia.org/wiki/Stronghold_Builder%27s_Guidebook','publication:stronghold-builder-3e'),('castle-guide-2e','The Castle Guide','https://www.tsrarchive.com/add/add-dmgr.html','publication:castle-guide-2e'),('bastions-2024','Bastions (2024 DMG)','https://www.dndbeyond.com/posts/1828-exploring-bastions-from-the-2024-dungeon-masters','publication:bastions-2024')]:add(key,label,'publication',url,{'entity_ids':[entity]})
assert len({r['id'] for r in resources})==len(resources)
data={'schema_version':1,'resources':resources,'completion_policy':'A registered title is not an item import. Original item audits are never completed automatically from row counts, title matching or related regional gear. Source categories remain open unless a finite bibliography is explicitly defined.'}
p=out/'requested-resources.json';p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))
print('Requested and enumerated source resources',len(resources))
