#!/usr/bin/env python3
"""Record reviewed/search-derived leads from the first matrix pass; no completeness claim."""
import json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'catalog/research/queue.json';d=json.loads(P.read_text());byid={r['id']:r for r in d['tasks']}
leads=[
('karameikos','armor','https://www.pandius.com/vllgwlcm.html','Welcome to our village','Fan scene describes Sulescu guard armor; not a unique armor definition.'),
('karameikos','clothing','https://www.pandius.com/vllgwlcm.html','Welcome to our village','Black guard cloaks are documented in a fan scene; no native-only claim.'),
('karameikos','consumables','https://www.pandius.com/karamage.html','The Mages Guild of Karameikos','Guild potion trade is a lead on availability, not a list of new potion identities.'),
('karameikos','magic-relics','https://www.pandius.com/dmsrvlkt.html','Dungeon Master Survival Kit review','Review names several relics; original cards not inspected.'),
('karameikos','tools-gear','https://www.pandius.com/karamage.html','The Mages Guild of Karameikos','Component, glassware and laboratory-supply leads; no new values inferred.'),
('karameikos','trade-goods','https://pandius.com/exp_imp.html','Cities and Ports: Exports and Imports','Fan export/import table; associations rather than unique item families.'),
('karameikos','vehicles','https://pandius.com/mfleet.html','Mystaran fleets','Named ships are instances and should not each become a new ship type.'),
('karameikos','weapons','https://www.pandius.com/swrdkara.html','Sword of Karameikos','Fan-original weapon inspected; independent 2024 draft added.'),
('glantri','armor','https://pandius.com/constab.html','The Constabulary of Glantri City','Fan constable equipment; reflects use, not exclusive cultural origin.'),
('glantri','clothing','https://www.pandius.com/mstrrobe.html','Robe of the Great School’s (Grand) Master','Two original 2024 robe drafts added; source is fan material.'),
('glantri','consumables','https://pandius.com/Herbalism_1.pdf','Glantri herbalism handbook','Thirty fictional plants reported by introduction; full item extraction pending.'),
('glantri','magic-relics','https://www.pandius.com/gsomstff.html','Staff of the Great School of Magic','Fan staff inspected; independent 2024 draft added.'),
('glantri','weapons','https://pandius.com/constab.html','The Constabulary of Glantri City','Hand crossbow and rapier use, not new exclusive weapon families.'),
('glantri','trade-goods','https://pandius.com/exp_imp.html','Cities and Ports: Exports and Imports','Fan trade table; exact commodity values remain unknown.'),
('rockhome','weapons','https://www.pandius.com/rkhmcpup.html','Updates to Your Rockhome Campaign','Military equipment leads across troop roles; article not a complete item inventory.'),
('rockhome','armor','https://www.pandius.com/dmsrvlkt.html','Dungeon Master Survival Kit review','Torcs of Dengar name/reference; conversion still pending.'),
('five-shires','weapons','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Source-reported GAZ8 page references. Some named goods originate elsewhere.'),
('five-shires','consumables','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Distinctive alchemical/food names recorded separately; no new mechanics guessed.'),
('five-shires','clothing','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Clothing mentions, not exclusive cultural equipment.'),
('five-shires','tools-gear','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Instrument and tool mentions; original book not checked.'),
('five-shires','magic-relics','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Blackflame items require a dedicated setting-system conversion.'),
('five-shires','vehicles','https://www.pandius.com/5shritems.html','New Weapons and Equipment mentioned in GAZ8','Transport and animal mentions; common types should be linked, not multiplied.'),
]
for region,cat,url,title,note in leads:
 r=byid['mystara:region:'+region+':'+cat]
 if not any(e['url']==url for e in r['evidence']):
  r['search_attempts']+=1;r['evidence'].append({'url':url,'title':title,'note':note,'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  r['status']='source-leads-found'
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
rows=[('Rod of Justice',19,'magic-relics'),('Armor of Blackflame',19,'armor'),('Sword of Blackflame',19,'weapons'),('Cloak of Blackflame',19,'clothing'),('Dagger of Blackflame',19,'weapons'),('Blacksling',19,'weapons'),('Sling orb of blinding',20,'consumables'),('Sling orb of marking',20,'consumables'),('Sling orb of irritation',20,'consumables'),('Fire-pot',34,'consumables'),('Fire Dart',34,'consumables'),('Sleep drugs',30,'consumables'),('Knockout gas',30,'consumables'),('Anaesthetics',30,'consumables'),('Truth-babble',30,'consumables'),('Befuddlement drug',30,'consumables'),('Delirium drug',30,'consumables'),('Life-draining drug',30,'consumables'),('Mallowfern oil',41,'trade-goods'),('Mallowfern perfume',None,'trade-goods'),('Shadowgate Winery wine',47,'trade-goods'),('Dark Hin Brewery ale',53,'trade-goods'),('Twilight Wine poison',25,'consumables'),('Titterbuk',46,'tools-gear'),('Halfling clan tapestries',None,'trade-goods'),('Blackflame',19,'magic-relics')]
mentions=[{'name':name,'reported_book':'GAZ8','reported_page':page,'category':cat,'setting_id':'mystara','region_entity_id':'region:five-shires','relation':'documented-for','source_url':'https://www.pandius.com/5shritems.html','source_author':'Håvard','source_kind':'fan-source-index','original_page_checked':False,'status':'reference-only-awaiting-conversion','note':'Mention in a regional source does not prove regional manufacture, exclusivity or availability. Not counted as a new playable item.'} for name,page,cat in rows]
(ROOT/'catalog/settings/mystara/five-shires-item-mentions.json').write_text(json.dumps(mentions,ensure_ascii=False,indent=2)+'\n')
print('Recorded',len(leads),'research cells and',len(mentions),'distinctive GAZ8 mentions.')
