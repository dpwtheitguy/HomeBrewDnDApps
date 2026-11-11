#!/usr/bin/env python3
"""Build a traceable internet-research seed, not a claim of exhaustive book extraction.
Editorial source facts are deliberately separated from our original rules conversions.
"""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'catalog/settings/mystara'
OUT.mkdir(parents=True,exist_ok=True)

def write(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (OUT/Path(name).with_suffix('.yaml')).write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True))

GAZ=[('The Grand Duchy of Karameikos','karameikos'),('The Emirates of Ylaruam','ylaruam'),('The Principalities of Glantri','glantri'),('The Kingdom of Ierendi','ierendi'),('The Elves of Alfheim','alfheim'),('The Dwarves of Rockhome','rockhome'),('The Northern Reaches','northern-reaches'),('The Five Shires','five-shires'),('The Minrothad Guilds','minrothad'),('The Orcs of Thar','broken-lands'),('The Republic of Darokin','darokin'),('The Golden Khan of Ethengar','ethengar'),('The Shadow Elves','shadow-elves'),('The Atruaghin Clans','atruaghin')]
books=[]
for i,(title,region) in enumerate(GAZ,1):
    books.append({'id':f'GAZ{i}','title':title,'kind':'gazetteer','region_ids':[region],'setting_id':'mystara','bibliography_url':'https://www.acaeum.com/indexes/miscellaneous/gaz.html','item_audit_status':'not-fully-inspected','note':'Bibliographic identity verified; no claim of complete item extraction or checked page citations.'})
boxed=[('1037','Dawn of the Emperors: Thyatis and Alphatia',1989,'campaign-box'),('1054','Hollow World Campaign Set',1990,'campaign-box'),('1082','Wrath of the Immortals',1992,'campaign-box'),('1094','Champions of Mystara: Heroes of the Princess Ark',1993,'campaign-box'),('2500','Karameikos: Kingdom of Adventure',1994,'campaign-box'),('2502','Hail the Heroes',1994,'adventure-box'),('2504','Red Steel',1994,'campaign-box'),('2509','Night of the Vampire',1994,'adventure-box'),('2511','Glantri: Kingdom of Magic',1995,'campaign-box'),('2513','Mark of Amber',1995,'adventure-box'),('9500','Savage Baronies',1995,'campaign-box')]
for code,title,year,kind in boxed:
    books.append({'id':'TSR-'+code,'title':title,'year':year,'kind':kind,'setting_id':'mystara','bibliography_url':'https://pandius.com/prod_tl.html','item_audit_status':'not-fully-inspected'})
for code,title in [('HWR1','Sons of Azca'),('HWR2','Kingdom of Nithia'),('HWR3','The Milenian Empire'),('PC1','Tall Tales of the Wee Folk'),('PC2','Top Ballista'),('PC3','The Sea People'),('PC4','Night Howlers'),('PWA1',"Poor Wizard’s Almanac & Book of Facts"),('PWA2',"Poor Wizard’s Almanac II & Book of Facts"),('PWA3',"Poor Wizard’s Almanac III & Book of Facts"),('JA',"Joshuan’s Almanac & Book of Facts"),('RC','Rules Cyclopedia'),('AC4','The Book of Marvelous Magic'),('AC11','The Book of Wondrous Inventions'),('SCS','Savage Coast Campaign Book'),('DRAGON-PRINCESS-ARK','Voyage of the Princess Ark articles'),('DA1','Adventures in Blackmoor'),('DA2','Temple of the Frog'),('DA3','City of the Gods'),('DA4','The Duchy of Ten')]:
    books.append({'id':code,'title':title,'kind':'supplement-or-adventure','setting_id':'mystara','bibliography_url':'https://www.pandius.com/prodlist.html','item_audit_status':'not-fully-inspected'})
# Adjacent/core boxes are tracked separately; not all are Mystara-specific setting boxes.
for code,title in [('BASIC-1981','Basic Set (Moldvay)'),('EXPERT-1981','Expert Set (Cook/Marsh)'),('BASIC-1983','Basic Rules (Mentzer)'),('EXPERT-1983','Expert Rules (Mentzer)'),('COMPANION','Companion Rules'),('MASTER','Master Rules'),('IMMORTALS','Immortals Rules'),('CLASSIC-1994','Classic Dungeons & Dragons Game'),('DRAGONS-DEN',"Dragon’s Den"),('GOBLINS-LAIR',"The Goblin’s Lair"),('HAUNTED-TOWER','The Haunted Tower')]:
    books.append({'id':code,'title':title,'kind':'core-or-adjacent-box','setting_id':'mystara-adjacent','bibliography_url':'https://pandius.com/prod_tl.html','item_audit_status':'not-fully-inspected','note':'Core/adjacent coverage; confirm setting relevance per item.'})
write('source-inventory.json',books)
REFS=[
('items','Items research directory','https://www.pandius.com/items.html','Various','directory'),
('blades','Swords & Blades from BECMI material','https://pandius.com/swrdbld.html','Håvard','fan-source-index'),
('armor','Mystaran Armour','https://www.pandius.com/mystarmr.html','Håvard','fan-conversion'),
('savage-equipment','Equipment and Economics','https://pandius.com/sc_equip.html','Savage Coast Campaign Book, hosted at Pandius','legacy-setting-text'),
('savage-magic','Magic','https://www.pandius.com/sc_magic.html','Savage Coast Campaign Book, hosted at Pandius','legacy-setting-text'),
('trade','Cities and Ports: Exports and Imports','https://pandius.com/exp_imp.html','John Hare','fan-cultural-economy'),
('coffee','The Amazing Travels of Goods and People Part 1','https://pandius.com/trvlgp1.html','See article attribution','fan-cultural-economy'),
('magic-items','Magic Items of Mystara','https://www.pandius.com/magcitem.html','Gilles Leblanc, Jacob Skytte, Geoff Gander, Joe Kelly, Kevin Wyton','fan-original-items'),
('soul-crystal','Soul Crystal','https://www.pandius.com/soulxtal.html','WingofCoot','fan-conversion'),
('shadow-items','Shadow Elf specific Magical Items','https://pandius.com/selfmgci.html','See article attribution','mixed-fan-and-reported-canon'),
('chime','Chime of Time','https://www.pandius.com/timechim.html','Andrew Theisen','fan-conversion'),
('egg','Egg of Wonder','https://www.pandius.com/eggowndr.html','Andrew Theisen','fan-conversion'),
('hurricane','Hurricane Lamp','https://www.pandius.com/hurrlamp.html','Andrew Theisen','fan-conversion'),
('lamp','Lamp of Long Burning','https://www.pandius.com/lb_lamp.html','Andrew Theisen','fan-conversion'),
('boat','Undersea Boat','https://www.pandius.com/undrseab.html','Andrew Theisen','fan-conversion'),
('equipment-index','BECMI equipment index','https://www.pandius.com/BECMI_Indexes.ods','Peter','index-download-unavailable-http-403'),
('trade-goods','Superior Trade Goods of the Known World and Beyond','https://www.pandius.com/SuperiorTradeGoodsoftheKnownWorldandBeyond.docx','Jesper Andersen','discovered-not-inspected'),
('arcane-books','Magic and arcane books index','https://www.pandius.com/Books_of_Mystara_03.xlsx','LoZompatore','discovered-not-inspected'),
('armoury','The Mystaran Armoury v1.6','https://www.pandius.com/The_Mystaran_Armoury_v1.6.pdf','Marco Dalmonte','discovered-not-fully-inspected')]
refs=[{'id':a,'title':b,'url':c,'author':d,'kind':e,'setting_id':'mystara','license_status':'No blanket reuse license verified; item facts, links and original adaptation text only.'} for a,b,c,d,e in REFS]
write('research-sources.json',refs)
# name, target SRD base, culture, source, reported book. These are selected mappings, not entire legacy stat blocks.
reskins=[]
def add(name,base,region,ref,book,note=''):
    reskins.append({'name':name,'base_item_pk':'srd-2024_'+base,'culture_ids':[region], 'evidence_ref':ref,'reported_book':book,'source_page_verified':False,
                    'conversion_kind':'2024-base-item-reskin','conversion_status':'draft-needs-setting-and-play-review',
                    'conversion_note':note or 'Uses the named 2024 base item unchanged. Legacy special bonuses and size-based rules are not carried over.',
                    'lore_status':'fan-reported-setting-association; original book not checked'})
for name,base,region,book in [('Yataghan','shortsword','ylaruam','GAZ2'),('Claymore','longsword','glantri','GAZ3'),('Darokinian Rapier','rapier','darokin','GAZ11'),('Katar','shortsword','ethengar','GAZ12'),('Khopesh','scimitar','nithia','HWR2'),('Sword Staff','glaive','nithia','HWR2'),('Needle Dagger','dagger','milenian-empire','HWR3'),('Ta-Agsu','dagger','milenian-empire','HWR3')]:add(name,base,region,'blades',book)
for name,base,region,book in [('Suit Armor','plate-armor','known-world','RC'),('Ethengar Lamellar','scale-mail','ethengar','GAZ12-reported-indirectly'),('Layered Shell Armor','scale-mail','sea-people','PC3'),('Piece Shell Armor','chain-mail','sea-people','PC3'),('Thyatian Banded Armor','scale-mail','thyatis','TSR-1037'),('Target Buckler','shield','known-world','not-identified'),('Tower Shield','shield','known-world','not-identified'),('Snakeskin Leather Jerkin','leather-armor','atruaghin-bear','GAZ14-reported-indirectly'),('Turtle Clan Vest','leather-armor','atruaghin-turtle','GAZ14-reported-indirectly'),('Buffalo Hide Shield','shield','atruaghin','GAZ14-reported-indirectly'),('Horned Shield','shield','known-world','not-identified'),('Knife Shield','shield','known-world','not-identified'),('Sword Shield','shield','known-world','not-identified'),('Tusked Shield','shield','known-world','not-identified'),('Daxan Shield','shield','atruaghin-tiger','GAZ14-reported-indirectly')]:add(name,base,region,'armor',book)
for name,base,region in [('Brol','greataxe','gurrash'),('Bok','javelin','cayma'),('Cayma Crossbow','light-crossbow','cayma'),('Hessta','dart','cayma'),('Flight Lance','lance','ee-aar'),('Machete','scimitar','savage-coast'),('Maga','mace','gurrash'),('Main-Gauche','dagger','savage-coast'),('Nonaka','club','savage-coast'),('Sa','dagger','savage-coast'),('Scythe','glaive','savage-coast'),('Stiletto','dagger','savage-coast'),('Grooka','dagger','cayma'),('Matara','longsword','bellayne'),('Mishiya','shortsword','bellayne'),('Savage Coast Rapier','rapier','savage-coast'),('Sabre','scimitar','savage-coast'),('War Claws','dagger','rakasta'),('Wheellock Belt Pistol','pistol','savage-coast'),('Wheellock Horse Pistol','pistol','savage-coast')]:add(name,base,region,'savage-equipment','SCS')
write('conversion-inputs.json',reskins)
# Complex names and setting materials remain references until their unique mechanics are converted.
complex_refs=[]
for name,kind,ref,culture in [('Bolas','weapon','savage-equipment','savage-coast'),('Boomerang','weapon','savage-equipment','wallara'),('Cayma Sleep Grenade','consumable','savage-equipment','cayma'),('Cayma Choke Grenade','consumable','savage-equipment','cayma'),('Cayma Fog Grenade','consumable','savage-equipment','cayma'),('Lasso','gear','savage-equipment','savage-coast'),('Cinnabryl','material','savage-equipment','savage-coast'),('Cinnabryl Amulet','amulet','savage-equipment','savage-coast'),('Cinnabryl Talisman','amulet','savage-equipment','savage-coast'),('Crimson Essence','potion','savage-equipment','savage-coast'),('Crimson Essence Base','alchemy','savage-equipment','savage-coast'),('Crimson Essence Ingredients','alchemy','savage-equipment','savage-coast'),('Crimson Essence Vial','container','savage-equipment','savage-coast'),('Red Steel','material','savage-equipment','savage-coast'),('Steel Seed','material','savage-equipment','savage-coast'),('Vermeil','material','savage-equipment','savage-coast'),('Glassteel','material','savage-equipment','ee-aar'),('Smokepowder','consumable','savage-equipment','savage-coast'),('Soul Crystal','wondrous-item','soul-crystal','shadow-elves'),('Ring of Rafiel','ring','shadow-items','shadow-elves'),("Telemon’s Sword",'weapon','shadow-items','shadow-elves'),("Tanadaleyo’s Gloves of Ogre Strength",'gloves','shadow-items','shadow-elves'),('Enchanted Lava-Fishing Rod','gear','shadow-items','shadow-elves'),('Ring of the Shadow Thief','ring','shadow-items','shadow-elves'),('Serpent Blade','weapon','magic-items','alfheim'),('Slayer','ammunition','magic-items','alfheim'),('Elven Gloves','gloves','magic-items','alfheim'),('Grim Jaw','weapon','magic-items','atruaghin'),('Berries of Health','consumable','magic-items','atruaghin'),('Undersea Boat','vehicle','boat','known-world')]:
    complex_refs.append({'name':name,'type':kind,'evidence_ref':ref,'culture_ids':[culture],'tags':['mystara','setting:mystara','conversion:pending'],'status':'source-reference-not-playable-conversion','evidence_url':next(x['url'] for x in refs if x['id']==ref)})
write('complex-item-references.json',complex_refs)
# Cultural associations reference commodities; they are not counted as unique magic items.
associations=[('coffee','ylaruam','Jaboor'),('oil','ylaruam','Jaboor'),('glassware','ylaruam','Jaboor'),('porcelain','ylaruam','Ylaruam'),('semiprecious-stones','ylaruam','Ylaruam'),('silk','thyatis','Thyatis'),('weapons','rockhome','Dengar/Evermur'),('armor','rockhome','Dengar/Evermur'),('tobacco','five-shires','Shireton'),('beer','five-shires','Shireton'),('wine','five-shires','Shireton'),('pottery','glantri','Glantri City'),('books','glantri','Glantri City'),('cloth','minrothad','Cove Harbour'),('tea','minrothad','Gapton'),('tools','minrothad','Stronghold'),('hides','ethengar','Ethengar'),('salt','ethengar','Ethengar'),('mounts','ethengar','Ethengar'),('pottery','karameikos','Kelven'),('glassware','karameikos','Kelven'),('fish','ierendi','Ierendi'),('textiles','atruaghin','Atruaghin'),('tobacco','atruaghin','Atruaghin')]
write('cultural-associations.json',[{'commodity_id':'commodity:'+a,'culture_id':b,'settlement':c,'setting_id':'mystara','source_url':'https://pandius.com/exp_imp.html','author':'John Hare','evidence_kind':'fan-trade-table','status':'association-only-not-a-new-item','price_gp':None} for a,b,c in associations])
print(json.dumps({'bibliography_entries':len(books),'research_sources':len(refs),'reskin_drafts':len(reskins),'complex_item_references':len(complex_refs),'cultural_associations':len(associations)}))
