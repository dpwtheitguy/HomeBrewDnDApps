#!/usr/bin/env python3
"""Human-checked names and book references from a credited fan research article."""
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
url='https://pandius.com/strygen4.html'
entries=[
 ('Proto-Zeppelin',['GAZ6'],'region:rockhome','Reported Special Dwarven Task section begins on p.31; not an item-specific verified page.'),
 ('Steam-Powered Dimension Launcher',['GAZ6'],'region:rockhome','Reported section lead p.31; original device details unverified.'),
 ('Tree of Life',['RC','Companion Set'],None,'Fan article reports Rules Cyclopedia pp.145–147 for the group of clan relics.'),
 ('Forge of Power',['RC','Companion Set'],None,'Fan article reports Rules Cyclopedia pp.145–147 for the group of clan relics.'),
 ('Crucible of Blackflame',['RC','Companion Set'],None,'Fan article reports Rules Cyclopedia pp.145–147 for the group of clan relics.'),
 ('Pearl of Power',['GAZ9'],'region:minrothad','Reported water-elf relic; not the SRD spell-slot recovery item merely because names match.'),
 ('Carved Oak',['GAZ9'],'region:minrothad','Reported wood-elf relic; original page unverified.'),
 ('Frond of Life',['PC3'],'region:sea-people','Reported aquatic-elf relic; original page unverified.'),
 ('Elvenstar',['X11'],None,'Reported adventure association; original page unverified.'),
 ('Chamber of the Spheres',['GAZ13'],'region:shadow-elves','The fan author suggests relic-like status; no rarity or classification inherited.'),
 ('Blue Knife',['GAZ10'],'region:broken-lands','Fan-reported book appearance; relic interpretation is not certified.'),
 ('The Shark',['TSR-1037'],'region:alphatia','Fan article reports Player’s Guide to Alphatia p.31; magical submersible name only.'),
 ('Air Ship of Love of Gaity',['TSR-1037'],'region:alphatia','Spelling retained from fan article; reported Player’s Guide to Alphatia p.31, original spelling unverified.'),
]
rows=[]
for name,codes,region,note in entries:
 r={'name':name,'source_type':'unclassified-item','url':url,'evidence_kind':'fan-research-explicit-book-reference','source_author':'Francesco Defferrari','reported_book_codes':codes,'original_book_verified':False,'source_note':note+' Name and reported book labels only; no powers, rarity, prices or construction rules imported.'}
 if region:r['regional_entity_id']=region
 if name=='Chamber of the Spheres':r.update(source_type='construction-component',record_kind='construction-component')
 rows.append(r)
data={'source_id':'mystara-craft-relic-reference','label':'Mystara craft, device and clan-relic references','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Thirteen selected names with explicit reported book associations, checked against the public fan article. Local extraction candidates were reviewed and three wrongly inherited GAZ6 attributions were corrected to Rules Cyclopedia / Companion Set. No original-book audit completed.','records':rows}
(ROOT/'catalog/raw/setting-reference-indexes/mystara-craft-relic-reference.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Mystara craft references:',len(rows))
