import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from catalog_taxonomy import Taxonomy

class WorldbuildingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.items={r['id']:r for r in map(json.loads,(ROOT/'catalog/items.jsonl').read_text().splitlines())}
 def test_construction_has_distinct_budget_and_no_merchant_arbitrage(self):
  structures=[r for r in self.items.values() if r['source_id']=='worldbuilding-2024-drafts' and r.get('record_kind')=='structure']
  self.assertEqual(len(structures),48)
  self.assertEqual({r['structure']['scale'] for r in structures},{'camp','fort','castle','village','city','dungeon'})
  for r in structures:
   self.assertIsNone(r['valuation']['reference_quote'])
   self.assertEqual(r['valuation']['preferred_policy_id'],'construction-budget-v1')
   self.assertIn('land',r['structure']['construction']['cost_excludes'])
   self.assertIn('ongoing-staff',r['structure']['construction']['cost_excludes'])
   self.assertGreater(r['structure']['footprint']['width_ft'],0)
   self.assertIsNone(r['structure']['defenses']['hit_points'])
 def test_game_components_are_unconverted_and_not_portable_items(self):
  rows=[r for r in self.items.values() if r['source_id']=='valheim-construction-reference']
  self.assertGreater(len(rows),100)
  for r in rows:
   self.assertEqual(r['record_kind'],'construction-component')
   self.assertEqual(r['ruleset'],'game-reference')
   self.assertIsNone(r['description']);self.assertEqual(r['valuation']['base_values'],[])
 def test_five_clans_and_removal_of_false_clan(self):
  tx=Taxonomy(ROOT/'catalog/taxonomy/entities.json')
  self.assertNotIn('region:atruaghin-buffalo',tx.entities)
  for clan in ['bear','horse','elk','turtle','tiger']:
   self.assertIn('region:atruaghin-'+clan,tx.entities)
   self.assertIn('culture:atruaghin-'+clan,tx.entities)
  shield=self.items['mystara:buffalo-hide-shield']
  self.assertEqual(shield['origin_region_ids'],['region:atruaghin'])
  self.assertIn('culture:atruaghin-horse',self.items['mystara:eagle-lance']['origin_culture_ids'])
 def test_game_inspiration_is_explicitly_new_fiction(self):
  for iid in ['plateau-trail-bola','highland-runner-s-sandals','river-companions-line']:
   r=self.items['mystara-frontiers:'+iid]
   self.assertFalse(r['provenance']['original_publication_verified'])
   self.assertTrue(r['provenance']['adaptation_note'])
   self.assertEqual(r['access']['class_allowlist'],None)
 def test_skyship_proposals_do_not_claim_canonical_vehicle_stats(self):
  ships=[r for r in self.items.values() if r.get('record_kind')=='vehicle']
  self.assertEqual(len(ships),2)
  for r in ships:
   self.assertEqual(r['vehicle']['status'],'original-design-needs-vehicle-rules-review')
   self.assertIsNone(r['vehicle']['hit_points'])
   self.assertGreater(r['vehicle']['crew_minimum'],0)
   self.assertFalse(r['provenance']['original_publication_verified'])

if __name__=='__main__':unittest.main()
