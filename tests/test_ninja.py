import json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
sys.path.insert(0,str(ROOT/'scripts'))
from catalog_taxonomy import Taxonomy
from catalog_search import search
from research_packs import classify_reference

class NinjaResearchTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.items={r['id']:r for r in map(json.loads,(ROOT/'catalog/items.jsonl').read_text().splitlines())}
  cls.raw=[json.loads(p.read_text()) for p in (ROOT/'catalog/raw/game-reference-indexes').glob('*.json')]
 def test_reference_identity_and_variant_collapsing(self):
  for source in self.raw:
   identities=[(r['name'].casefold(),r['source_type'].casefold()) for r in source['records']]
   self.assertEqual(len(identities),len(set(identities)),source['source_id'])
  d3=next(r for r in self.raw if r['source_id']=='diablo-3-reference')
  self.assertTrue(any(len(r.get('upstream_ids',[]))>1 for r in d3['records']))
 def test_rowspan_continuations_do_not_become_weapons(self):
  nioh=next(r for r in self.raw if r['source_id']=='nioh-2-reference')
  names={r['name'] for r in nioh['records']}
  self.assertIn('Akechi Chikakage',names)
  for name in ['Tokichiro','Shuten Doji','Otakemaru','The Two Faces of Hospitality']:
   self.assertNotIn(name,names)
 def test_reference_records_do_not_pretend_to_be_tabletop_conversions(self):
  refs=[r for r in self.items.values() if r['ruleset']=='game-reference']
  self.assertGreater(len(refs),3000)
  for r in refs:
   self.assertEqual(r['tabletop_status'],'adaptation-needed')
   self.assertEqual(r['content_status'],'factual-metadata-only')
   self.assertIsNone(r['description']);self.assertIsNone(r['magic'])
   self.assertEqual(r['valuation']['base_values'],[])
   self.assertIsNone(r['access']['class_allowlist'])
 def test_reskins_preserve_base_training_and_do_not_reference_themselves(self):
  rows=[r for r in self.items.values() if r['source_id']=='ninja-2024-drafts']
  self.assertEqual(len(rows),62)
  for r in rows:
   self.assertEqual(r['tabletop_status'],'draft-dm-review-required')
   self.assertEqual(r['mechanics']['automated_effects'],[])
   base=r.get('base_item_id')
   if base:
    self.assertNotEqual(base,r['id']);self.assertIn(base,self.items)
    self.assertEqual(r['access']['proficiency_interactions'],self.items[base]['access']['proficiency_interactions'])
  self.assertFalse(self.items['ninja:katana']['magic'])
  self.assertFalse(self.items['ninja:smoke-egg']['requires_attunement'])
 def test_no_invented_ethnic_or_setting_attribution(self):
  rows=[r for r in self.items.values() if r['source_id']=='ninja-2024-drafts']
  for r in rows:
   self.assertEqual(r['origin_culture_ids'],[])
   self.assertNotIn('rokugan',r['setting_ids'])
   self.assertFalse(r['provenance']['original_publication_verified'])
  tx=Taxonomy(ROOT/'catalog/taxonomy/entities.json')
  self.assertEqual(tx.resolve('PHBR15'),'publication:complete-ninja-handbook')
  self.assertEqual(tx.resolve('ninja'),'topic:ninja-equipment')
  self.assertIn('publication:mark-of-amber',tx.entities)
 def test_ninja_saved_profiles_apply_source_and_theme_filters(self):
  db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3');db.row_factory=sqlite3.Row
  try:
   rows=[json.loads(r['data_json']) for r in search(db,ROOT/'catalog',profile='ninja-2024-drafts',limit=1000)]
   self.assertEqual(len(rows),62)
   self.assertTrue(all(r['source_id']=='ninja-2024-drafts' for r in rows))
   rows=[json.loads(r['data_json']) for r in search(db,ROOT/'catalog',profile='ninja-workbench',limit=1000)]
   self.assertGreater(len(rows),62)
   self.assertTrue(all('theme:ninja' in r['tags'] for r in rows))
   rows=[json.loads(r['data_json']) for r in search(db,ROOT/'catalog',profile='ninja-2024-drafts',sources=['open5e-srd-2024'],limit=2)]
   self.assertTrue(all(r['source_id']=='open5e-srd-2024' for r in rows))
  finally:db.close()
 def test_source_category_classification(self):
  self.assertEqual(classify_reference('weapons'),('weapon','weapon'))
  self.assertEqual(classify_reference('scrolls'),('scroll','scroll'))
  self.assertEqual(classify_reference('katars'),('weapon','dagger'))
  self.assertEqual(classify_reference('boots'),('boots','boots'))

if __name__=='__main__':unittest.main()
