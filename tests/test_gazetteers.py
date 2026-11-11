import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from fetch_gazetteer_equipment import npc_gear
class GazetteerResearchTests(unittest.TestCase):
 def raw(self,key):return json.loads((ROOT/'catalog/raw/setting-reference-indexes'/f'{key}.json').read_text())['records']
 def test_npc_equipment_excludes_spells_rewrites_and_sidebars(self):
  text='BECMI Combat Notes: Fighter 5; AC 4 (chain mail, shield +2); #AT 1 (sword +1); Languages: Thyatian.\nSpells Normally Carried: Magic Sword.\nDesign changes for Character\nAdd sword +5 and a ring of protection +5.\nTransports: Cutlass, Sword.'
  self.assertEqual(set(npc_gear(text)),{'chain mail','shield +2','sword +1'})
 def test_special_dagger_does_not_silently_become_an_ordinary_bonus(self):
  text='BECMI Combat Notes: AC 0; #AT 1 (Dagger +2, +3 vs. Spell-Casters); D 1-4.'
  self.assertEqual(npc_gear(text),['dagger +2 (+3 vs. spell-casters)'])
 def test_primary_names_verify_only_the_cited_appearance(self):
  rows=self.raw('gazetteer-publisher-preview-reference');self.assertEqual(len(rows),25)
  for r in rows:
   self.assertTrue(r['original_book_verified']);self.assertEqual(r['verified_fields'],['name','appearance-on-cited-page']);self.assertEqual(len(r['preview_sha256']),64);self.assertEqual(r['regional_role'],'found-in')
  armor=[r for r in rows if r['name']=='Partial Armor'];self.assertEqual(len(armor),1);self.assertEqual(len(armor[0]['component_labels']),13)
 def test_trade_categories_and_arrow_aliases_do_not_generate_variants(self):
  rows=self.raw('gazetteer-trade-reference');self.assertEqual(len(rows),32)
  self.assertTrue(all(r['record_kind']=='trade-category' for r in rows));self.assertTrue(any(r['name']=='Textiles (rope, sacking)' for r in rows))
  rows=self.raw('gazetteer-equipment-reference');names=[r['name'] for r in rows]
  self.assertIn('Arrow, Heavy',names);self.assertNotIn('Arrow, Heavy/Takadi',names)
 def test_npc_references_retain_appearances_without_creating_npc_items(self):
  rows=self.raw('gazetteer-npc-equipment-reference');self.assertGreaterEqual(len(rows),30)
  for r in rows:
   self.assertTrue(r['attested_appearances']);self.assertFalse(r['original_book_verified']);self.assertTrue(r['reported_book_codes']);self.assertEqual(r['regional_role'],'found-in')
  sword=next(r for r in rows if r['name']=='sword');self.assertGreater(len(sword['attested_appearances']),1)
 def test_online_adaptation_keeps_descriptive_names_and_edition_separate(self):
  rows=self.raw('gaz13-online-adaptation-reference');self.assertEqual(len(rows),41)
  for r in rows:
   self.assertFalse(r['original_book_verified']);self.assertIn('1995',r['reported_edition']);self.assertEqual(r['reported_book_codes'],['GAZ13'])
  self.assertTrue(any(r['name']=='Strongmind' for r in rows))
  self.assertTrue(all(r.get('name_normalization_note') for r in rows if r['name'].startswith(('Porphyriel','Xatapechtli'))))
if __name__=='__main__':unittest.main()
