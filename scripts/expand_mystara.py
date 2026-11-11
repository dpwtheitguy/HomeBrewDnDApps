#!/usr/bin/env python3
"""Second evidence pass: region-specific draft mechanics and research references."""
import json
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'catalog/settings/mystara'
def save(name,data):
 p=OUT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.yaml').write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False))
refs=[
 {'id':'sword-karameikos','title':'Sword of Karameikos','url':'https://www.pandius.com/swrdkara.html','author':'Marco Fossati','kind':'fan-original-item'},
 {'id':'school-staff','title':'Staff of the Great School of Magic','url':'https://www.pandius.com/gsomstff.html','author':'Marco Fossati; separate additions by Rodger Burns','kind':'fan-original-item'},
 {'id':'school-robes','title':'Robe of the Great School’s (Grand) Master','url':'https://www.pandius.com/mstrrobe.html','author':'Marco Fossati','kind':'fan-original-items'},
 {'id':'dm-survival-review','title':'Dungeon Master Survival Kit review','url':'https://www.pandius.com/dmsrvlkt.html','author':'David Keyser','kind':'secondary-review-of-official-source'},
 {'id':'karameikan-chronology','title':'A Karameikan Chronology','url':'https://www.pandius.com/karachrn.html','author':'See article credits','kind':'mixed-official-and-fan-timeline'}]
for r in refs:r.update(setting_id='mystara',license_status='No blanket reuse license verified. Names, source facts and original adaptation text only.')
refs.extend([
 {'id':'gaz9-options','title':'Player Character Options from GAZ9 The Minrothad Guilds','url':'https://www.pandius.com/gz9pcopt.html','author':'Håvard','kind':'fan-source-index','setting_id':'mystara','license_status':'Names, facts and original conversion choices only.'},
 {'id':'atruaghin-equipment','title':'Weapons and Equipment of the Atruaghin Clans','url':'https://www.pandius.com/atruitem.html','author':'Håvard','kind':'mixed-source-index-and-fan-proposals','setting_id':'mystara','license_status':'Original book not checked. Distinguish reported items from author-created additions.'}
])
save('additional-research-sources.json',refs)
reskins=[]
for name,base,region,ref,book,note in [
 ('Dainrouw Club','club','minrothad','gaz9-options','GAZ9','Uses the 2024 Club. Legacy accuracy bonus is omitted; no ancestry or guild proficiency is granted.'),
 ('Augurist Hammer','warhammer','minrothad','gaz9-options','GAZ9','Uses the 2024 Warhammer as an editorial mapping. Critical hits do not automatically destroy another item.'),
 ('Verdier Bow','longbow','minrothad','gaz9-options','GAZ9','Uses the 2024 Longbow as an editorial mapping. No automatic +2 bonus for guild membership.'),
 ('Whale Tooth Knife','dagger','atruaghin-turtle','atruaghin-equipment','GAZ14','Uses the 2024 Dagger; material and cultural appearance do not add attack bonuses.'),
 ('Scallop-bladed Short Sword','shortsword','atruaghin-tiger','atruaghin-equipment','GAZ14','Uses the 2024 Shortsword. Legacy +1 damage is omitted.'),
 ('Tiger Javelin','javelin','atruaghin-tiger','atruaghin-equipment','GAZ14','Uses the 2024 Javelin. Legacy damage bonus is omitted.'),
 ('Xitchen Blowgun','blowgun','atruaghin-tiger','atruaghin-equipment','GAZ14','Uses the 2024 Blowgun. No extra automatic damage on dart removal.'),
 ('Elk Clan Tomahawk','handaxe','atruaghin-elk','atruaghin-equipment','GAZ14','Uses the 2024 Handaxe. Clan association does not grant proficiency.'),
 ('Eagle Lance','spear','atruaghin','atruaghin-equipment','GAZ14','Uses the 2024 Spear. Source calls its users Horse Clan; this is not silently equated with Children of the Buffalo.')]:
 reskins.append({'name':name,'base_item_pk':'srd-2024_'+base,'culture_ids':[region],'evidence_ref':ref,'reported_book':book,'source_page_verified':False,'conversion_kind':'2024-base-item-reskin','conversion_status':'draft-needs-setting-and-play-review','conversion_note':note,'lore_status':'fan-reported-setting-association; original book not checked'})
save('additional-reskins.json',reskins)
drafts=[
 {'name':'Sword of Karameikos','ref':'sword-karameikos','icon':'sword','rarity':'rare','cost':'4015','type':'weapon','attunement':True,'culture_ids':['karameikos'],
  'tldr':'A ceremonial +1 longsword that can demand truthful answers.',
  'details':'Use the 2024 Longsword rules, with +1 to attack and damage rolls. Requires attunement. Once per Long Rest, as a Magic action, cast Zone of Truth (save DC 13) without components or a spell slot. All normal spell limits apply; a creature can remain silent.',
  'change':'Replaces rumored unlimited truth detection and exceptional slaying powers with one defined spell. Sovereign-only wielding is folklore in the source, not an enforced prerequisite here.',
  'creative':'Hold a negotiated hearing. The spell cannot force an answer or prove that silence is guilt.',
  'flavor':'An oath weighs more than the gold in its hilt.'},
 {'name':'Staff of the Great School of Magic','ref':'school-staff','icon':'staff','rarity':'rare','cost':'4000','type':'staff','attunement':True,'attunement_requirement':'spellcaster','culture_ids':['glantri'],
  'tldr':'A six-charge teaching staff for force, fire, and flight.',
  'details':'Requires attunement by a spellcaster. The staff has 6 charges and regains 1d6 expended charges at dawn, to a maximum of 6. As a Magic action, expend charges to cast Magic Missile (1 charge, level 1), Burning Hands (1 charge, save DC 15), or Fly (3 charges). No spell slot or components are required. Fly requires your Concentration as normal.',
  'change':'Omits legacy wish, teleportation, crafting and regional recharge rules. This original 2024 draft is not a reproduction of the source’s full power list.',
  'creative':'Choose flight for exploration or conserve charges for combat. Casting Fly may end another Concentration spell.',
  'flavor':'Lessons learned in Glantri rarely remain on the page.'},
 {'name':'Robe of the Great School’s Master','ref':'school-robes','icon':'clothing','rarity':'uncommon','cost':'400','type':'clothing','attunement':True,'attunement_requirement':'spellcaster','culture_ids':['glantri'],
  'tldr':'An academic robe with an alternate AC formula and magical sight.',
  'details':'Requires attunement by a spellcaster. While wearing this robe and no armor or shield, you can use AC 13 + your Dexterity modifier instead of another AC formula. Once per Long Rest, cast Detect Magic without components or a spell slot, using its normal casting time and Concentration.',
  'change':'Replaces descending AC and doubled prepared spell capacity with a bounded defensive formula and one utility casting.',
  'creative':'Inspect an unfamiliar magical object without consuming a prepared spell. Detection does not identify every property or curse.',
  'flavor':'A scholar’s rank is stitched inside, where only its bearer can read it.'},
 {'name':'Robe of the Great School’s Grand Master','ref':'school-robes','icon':'clothing','rarity':'very rare','cost':'40000','type':'clothing','attunement':True,'attunement_requirement':'spellcaster','culture_ids':['glantri'],
  'tldr':'Senior scholarly vestments with stronger protection and limited divination.',
  'details':'Requires attunement by a spellcaster. While wearing this robe and no armor or shield, you can use AC 15 + your Dexterity modifier instead of another AC formula. Once per Long Rest each, cast Detect Magic or Identify without components or spell slots, using normal casting times. Detect Magic requires Concentration.',
  'change':'No doubled spell slots, secret remote surveillance, automatic Radiance training, or bonus to every saving throw.',
  'creative':'Appraise a recovered object before a dangerous experiment. Identify does not reveal every curse.',
  'flavor':'The chair changes hands. The work remains unfinished.'}
]
for d in drafts: d['cultural_identity_ids']=['culture:karameikan'] if d['ref']=='sword-karameikos' else ['culture:glantrian']
save('additional-drafts.json',drafts)
# Review-derived identities are retained separately from playable conversions.
extra=[('Sword of Halav','weapon','karameikos'),('Torcs of Dengar','wondrous-item','rockhome'),('Staff of the Infernal Arcana','staff','karameikos'),("Kahlark’s Ebon Cloak",'cloak','glantri'),('Viper','weapon','glantri'),('Diadem of the Sun','wondrous-item','karameikos'),("Ixion’s Wrath",'weapon','known-world'),('Radiant Eye','wondrous-item','broken-lands'),('Deck of the Spheres','artifact','known-world'),("Comet’s Edge",'weapon','karameikos')]
save('additional-complex-references.json',[{'name':a,'type':b,'region_id':'region:'+c,'setting_id':'mystara','status':'secondary-source-name-confirmed-mechanics-not-converted','source_url':refs[3 if a!="Comet’s Edge" else 4]['url'],'note':'Do not conflate a review-reported official item with similarly named fan creations. Exact original page/card not checked.'} for a,b,c in extra])
print('Added four original draft conversions and ten review-derived research identities.')
