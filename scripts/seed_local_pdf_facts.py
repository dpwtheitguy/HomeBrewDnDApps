#!/usr/bin/env python3
"""Selected facts visually checked on user-provided pages; no PDF prose or art export."""
import hashlib,json,re,time
import yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'catalog';inventory=json.loads((C/'research/local-pdf-inventory.json').read_text());files={Path(r['file']).name:r for r in inventory['pdfs']}
books={
 'GAZ1':('Grand Duchy of Karameikos.pdf','https://www.dmsguild.com/product/16974','Aaron Allston','region:karameikos'),
 'GAZ2':('tsr09194 - D&D 2E - Gazetteer - GAZ02   Emirates of Ylaruam.pdf','https://www.dmsguild.com/product/16975','Ken Rolston','region:ylaruam'),
 'GAZ4':('Kingdom of Ierendi.pdf','https://www.dmsguild.com/product/16977','Anne Gray McCready','region:ierendi'),
 'GAZ8':('The Five Shires.pdf','https://www.dmsguild.com/product/16980','Ed Greenwood','region:five-shires'),
 'GAZ9':('tsr09236 - D&D 2E - Gazetteer - GAZ09   The Minrothad Guilds.pdf','https://www.dmsguild.com/product/16981','Deborah Christian and Kim Eastland','region:minrothad'),
 'GAZ11':('Republic of Darokin.pdf','https://www.dmsguild.com/product/16982','Scott Haring','region:darokin'),
}
# Resolve publisher links from the already inspected bibliography rather than trusting guessed IDs.
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent));from fetch_ninja_references import fetch,clean
for a in fetch('https://pandius.com/dthrurpg.html').xpath('//a[@href]'):
 m=re.match(r'(GAZ\d+)\b',clean(a.text_content()))
 if m and m[1] in books:
  name,_,author,region=books[m[1]];books[m[1]]=(name,a.get('href').split('?')[0],author,region)
def evidence(code,pdf_page,printed,fields,**extra):
 name,url,author,region=books[code];r=files[name]
 return {'book_code':code,'url':url,'author':author,'local_file':r['file'],'file_sha256':r['sha256'],'locator':{'pdf_page':pdf_page,'printed_page':printed},'verified_fields':fields,'verification_scope':'Only the listed fields on the cited original-book page were visually verified. This is not full-book audit completion or a 2024 rules/balance review.',**extra}
patches=[]
def patch(source_id,name,ev,**changes):
 patches.append({'source_id':source_id,'name':name,'evidence':ev,**changes})
for name in ['bracers of defense ac 2','dagger +2 (+3 vs. spell-casters)','scroll of protection from magic','ring of regeneration','drums of panic']:
 patch('gazetteer-npc-equipment-reference',name,evidence('GAZ1',60,59,['name','Bargle-equipment-appearance']),note='Original GAZ1 equipment page verified. Secondary NPC header credit p.58 is retained separately; equipment is on printed p.59.')
patch('gazetteer-equipment-reference','Fire Crystal, Ierendi',evidence('GAZ4',59,58,['source-label','legacy-polished-market-range','nonmagical-optical-nature']),aliases=['Fire starter','Ierendi fire starter'],legacy_facts={'source_label':'fire starters','price_kind':'polished-market-range','minimum_gp':200,'maximum_gp':300,'economy':'D&D BECMI GAZ4','guaranteed_player_sale_price':False,'modern_charisma_quote':False,'physical_nature':'Natural magnifying crystal; optical ignition, not an asserted magical flame power.'},note='Original page gives polished fire starters a 200–300 gp market range. The secondary equipment index reports 200–500 gp; retain that discrepancy without treating it as the verified value.')
for name,cost,pdf_page,printed in [('Armor of Blackflame',200000,44,19),('Cloak of Blackflame',100000,44,19),('Blacksling',90000,45,20),('Sword of Blackflame',275000,45,20),('Dagger of Blackflame',175000,45,20)]:
 patch('gaz8-name-reference',name,evidence('GAZ8',pdf_page,printed,['name','legacy-construction-cost']),legacy_facts={'price_kind':'construction-cost','amount_gp':cost,'economy':'D&D BECMI GAZ8','market_price':False,'modern_charisma_quote':False},note='Verified legacy crafting/construction expenditure. This is not a market price, 2024 value or guaranteed merchant quote.')
patch('mystara-craft-relic-reference','Pearl of Power',evidence('GAZ9',76,42,['name','water-elf-relic-appearance']),note='Verified the Minrothad clan relic. Do not merge it with the SRD spell-slot recovery item merely because the names match.')
patch('gazetteer-equipment-reference','Dagger, Kouglar',evidence('GAZ2',37,36,['name','curved-dagger-classification']),aliases=['Kouglar'],note='Verified in the original glossary as a curved dagger; no special bonus inferred.')
patch('mystara-draft-conversions','Yataghan',evidence('GAZ2',37,36,['name','scimitar-classification']),note='The original glossary calls it a large double-edged scimitar. The 2024 draft now uses the Scimitar base profile; no separate Large-size rule is inferred from the adjective.')
(C/'settings/mystara/local-pdf-verifications.json').write_text(json.dumps({'scope':'Selected human-checked page facts. Existing records are enriched instead of duplicated.','patches':patches},ensure_ascii=False,indent=2)+'\n')
rows=[]
def add(name,kind,code,pdf_page,printed,**extra):
 ev=evidence(code,pdf_page,printed,['object-name-or-explicit-object-mention']);filename,url,author,region=books[code]
 row={'name':name,'source_type':kind,'url':url,'provider':'User-provided original source PDF','evidence_kind':'visually-checked-user-provided-original-page','source_author':author,'reported_book_codes':[code],'reported_edition':'D&D BECMI original Gazetteer','regional_entity_id':region,'regional_role':'found-in','regional_status':'original-page-appearance','original_book_verified':True,'local_pdf':ev['local_file'],'pdf_sha256':ev['file_sha256'],'locator':ev['locator'],'verified_fields':ev['verified_fields'],'verification_scope':ev['verification_scope'],'source_note':'Selected factual name/object appearance only; no source prose, art, legacy powers, modern price or proficiency added.',**extra};rows.append(row)
for name,kind in [('Chechia','clothing'),('Nahmeh','book'),('Qahwa','food')]:add(name,kind,'GAZ2',37,36)
for name,kind in [('Fletcher Down Pillow','furnishing'),('Fletcher Down Mattress','furnishing'),('Fletcher Island Wine','food'),('Grapes','food'),('Citrus','food'),('Olives','food')]:
 add(name,kind,'GAZ4',59,58,**({'record_kind':'furnishing-reference'} if kind=='furnishing' else {}),name_normalization_note='Singular or geographically qualified catalog label for an explicitly mentioned good, not an invented canonical brand or unique magic item.')
for name,kind in [('Potion of Water Movement','potion'),('Ring of Water Walking','ring'),('Staff of Air and Water','staff'),('Pearl of Power Fragment','material')]:
 add(name,kind,'GAZ9',76,42,**({'source_availability':'The original text says this staff cannot be bought; no merchant price inferred.'} if name=='Staff of Air and Water' else {}),name_normalization_note='Pearl fragment label identifies the crafting material described in the relic-crafts section.' if 'Fragment' in name else 'Source item name retained; legacy powers require a separate 2024 adaptation.')
for name,kind in [('Amulet of Protection from Crystal Ball and ESP','amulet'),('Ring of Protection +1','ring')]:add(name,kind,'GAZ11',60,59)
d={'source_id':'gazetteer-local-pdf-reference','label':'Gazetteer user-provided original-page item facts','source_name':'Gazetteer original-page facts from user PDFs','entity_id':'topic:mystara-frontiers','setting_id':'mystara','ruleset':'dnd-edition-unverified','source_url':'https://pandius.com/prodlist.html','retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'coverage':'Fifteen selected original-page equipment/cultural-good references. PDF/printed pages and file hashes retained. Existing names are verified via separate patches, not added again as duplicate items. Source PDFs, prose and artwork excluded from export.','records':rows}
assert len(rows)==15
(C/'raw/setting-reference-indexes/gazetteer-local-pdf-reference.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
# Refine an existing editorial mapping from the inspected original glossary.
p=C/'settings/mystara/conversion-inputs.json';inputs=json.loads(p.read_text());r=next(r for r in inputs if r['name']=='Yataghan');r['base_item_pk']='srd-2024_scimitar';r['source_page_verified']=True;r['lore_status']='Original glossary name and weapon type checked; other lore remains unverified.';r['conversion_note']='Uses the 2024 Scimitar profile, following the original GAZ2 glossary on printed p.36 (user PDF p.37). Replaces the earlier fan-index Shortsword mapping. Legacy special bonuses and size-based rules are omitted; “large” in the glossary is not treated as a creature-size restriction.';p.write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
p.with_suffix('.yaml').write_text(yaml.safe_dump(inputs,allow_unicode=True,sort_keys=False))
print('Local original-page records:',len(rows),'existing-record verifications:',len(patches))
