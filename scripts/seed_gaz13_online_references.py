#!/usr/bin/env python3
"""Selected factual names in the 1995 TSR online adaptation; no powers/text export."""
import json,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1];url='https://heroes.mystara.net/selenica/others/shadow/gaz13_dm.html';text=clean(fetch(url).text_content())
# Each explicit bonus below is an attested individual example, never an expanded range.
entries=[
 ('Strongmind','weapon','Strongmind',None),('Blackbolt','weapon','Blackbolt',None),
 ('Chain Mail +5','armor',r'chain mail \+5',None),('Shield +4','shield',r'shield \+4',None),('Ring +2','ring',r'ring \+2',None),
 ('Cloak of Protection +3','cloak',r'cloak of protection \+3',None),('Ring of Protection +5','ring',r'ring of protection \+5',None),('Staff of Fire','staff',r'staff of fire',None),('Wand of Fear','wand',r'wand of fear',None),
 ('Porphyriel’s Mace +3','weapon',r'carries a mace \+3','Descriptive catalog label for Porphyriel’s unnamed mace; not a canonical proper name.'),
 ('Porphyriel’s Magical Bracelet','wondrous-item',r'a magical bracelet','Descriptive catalog label for Porphyriel’s unnamed bracelet; not a canonical proper name.'),
 ('Ring of Protection +3','ring',r'ring of protection \+3',None),('Ring of Regeneration','ring',r'ring of regeneration',None),
 ('Staff of Dispelling','staff',r'staves of dispelling and healing','Expanded coordinated plural item mention to a singular searchable name; no rules copied.'),
 ('Staff of Healing','staff',r'staff of healing|staves of dispelling and healing',None),
 ('Chain Mail +3','armor',r'chain mail \+3',None),('Ring +1','ring',r'ring \+1',None),('Displacer Cloak','cloak',r'displacer cloak',None),('Gauntlets of Ogre Power','gloves',r'gauntlets of ogre power',None),
 ('Two-Handed Sword +2 of Slicing','weapon',r'two-handed sword \+2 which has the magical power of slicing','Descriptive combination of an explicitly attested weapon and its stated ability; powers omitted.'),
 ('Crossbow +3','weapon',r'crossbow \+3',None),('Staff of Commanding','staff',r'Staff of Commanding',None),('Short Sword +1','weapon',r'short sword \+1',None),
 ('Leather Armour +3','armor',r'leather armour \+3',None),('Light Crossbow +1','weapon',r'light crossbow \+1',None),('Crossbow Bolts +3','ammunition',r'crossbow bolts \+3',None),
 ('Chain Mail +1','armor',r'chain mail \+1',None),('Boots of Speed','boots',r'boots of speed',None),('Ring of Invisibility','ring',r'ring of invisibility',None),('Wand of Paralysation','wand',r'wand of paralysation',None),
 ('Ring of Protection +4','ring',r'ring of protection \+4',None),('Staff +3','staff',r'staff \+3',None),('Ring of Spell Turning','ring',r'ring of spell turning',None),('War Hammer +1','weapon',r'war hammer \+1',None),
 ('Rod of Parrying +5','rod',r'rod of parrying \(\+5\)',None),('Ancient Azcan Snake Staff','staff',r'ancient Azcan snake staff','Descriptor retained from the online adaptation; not a new canonical proper name.'),('Ring of Mind Barrier','ring',r'ring of mind barrier',None),('Wand of Illusion','wand',r'wand of illusion',None),('Flying Carpet','unclassified-item',r'flying carpet',None),
 ('Rings of Comprehending Languages','ring',r'rings of comprehending languages',None),
 ('Xatapechtli’s Magical Cloak','cloak',r"Xatapechtli's magical cloak",'Descriptive catalog label for the unnamed cloak; ancient Azcan design is source lore, not modern cultural authenticity or an automatic proficiency.'),
]
rows=[]
for name,kind,pattern,note in entries:
 assert re.search(pattern,text,re.I),name
 row={'name':name,'source_type':kind,'url':url,'evidence_kind':'tsr-online-adaptation-preserved-on-mirror','source_author':'Carl Sargent and Gary Thomas; online version updated by Roger E. Moore (1995)','reported_book_codes':['GAZ13'],'reported_edition':'1995 TSR online adaptation of BECMI GAZ13; not checked against the complete printed book','regional_entity_id':'region:shadow-elves','regional_role':'found-in','regional_status':'online-adaptation-equipment-presence','original_book_verified':False,'source_note':'Selected attested name only. No source rules, rarity, legacy bonus mechanics, price or prose imported. Online update differences from the printed Gazetteer remain explicit.'}
 if note:row['name_normalization_note']=note
 rows.append(row)
data={'source_id':'gaz13-online-adaptation-reference','label':'GAZ13 1995 TSR online-adaptation equipment references','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'41 selected equipment name references from the credited 1995 TSR online adaptation. Not an inventory of every object in its text and not a full original-book audit. Named enchantment examples retained without expanding ranges. Descriptive labels for unnamed unique equipment are flagged.','records':rows}
assert len(rows)==41
(ROOT/'catalog/raw/setting-reference-indexes/gaz13-online-adaptation-reference.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print('GAZ13 online adaptation:',len(rows))
# Keep additional Gazetteer materials as names with the source-column codes only.
u='https://pandius.com/mmtlmnrl.html';rows=[]
for tr in fetch(u).xpath('//tr'):
 cells=tr.xpath('./td')
 if len(cells)<4:continue
 name=clean(cells[0].text_content());credit=clean(cells[-1].text_content());codes=sorted(set('GAZ'+str(int(v)) for v in re.findall(r'\bGaz\s*(\d+)\b',credit,re.I)))
 if not codes:continue
 rows.append({'name':name,'source_type':'material','url':u,'evidence_kind':'fan-material-index-explicit-source-column','source_author':'Håvard','reported_book_codes':codes,'reported_locator':credit,'original_book_verified':False,'source_note':'Material name and source-column labels only. Fan speculation, purported health effects, lore and material powers were not imported.'})
d={'source_id':'gazetteer-material-reference','label':'Gazetteer metals and mineral source references','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':u,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Selected material names whose source column explicitly names a Gazetteer; no presumed material mechanics or original-page verification.','records':rows}
(ROOT/'catalog/raw/setting-reference-indexes/gazetteer-material-reference.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('Gazetteer material references:',len(rows))
