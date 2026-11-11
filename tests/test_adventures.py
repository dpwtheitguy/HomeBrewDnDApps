import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from catalog_taxonomy import Taxonomy

class AdventurePackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pack=json.loads((ROOT/'catalog/settings/thunder-rift/adventure-pack.json').read_text())
  cls.items={r['id']:r for r in map(json.loads,(ROOT/'catalog/items.jsonl').read_text().splitlines())}
 def test_source_appearances_reuse_existing_definitions(self):
  for appearance in self.pack['appearances']:
   item=self.items[appearance['item_id']]
   self.assertEqual(item['source_id'],'open5e-srd-2024')
   self.assertTrue(any(a['entity_id']==appearance['entity_id'] and a['role']=='found-in' for a in item['associations']))
  self.assertEqual(len(self.items),sum(json.loads((ROOT/'catalog/reports/counts.json').read_text())['by_source'].values()))
 def test_drafts_keep_provenance_prices_and_limits(self):
  for row in self.pack['drafts']:
   item=self.items[row['id']]
   self.assertEqual(item['tabletop_status'],'draft-dm-review-required')
   self.assertFalse(item['provenance']['original_publication_verified'])
   self.assertEqual(item['valuation']['base_values'][0]['status'],'author-estimate')
   self.assertEqual(item['mechanics']['automated_effects'],[])
   for field in ('tldr','details','creative_use','flavor'):self.assertTrue(item['presentation'][field])
  ring=self.items['thunder-rift:owlbear-ring']
  self.assertIn('no command',ring['description']);self.assertFalse(ring['provenance']['legacy_page_verified'])
  mace=self.items['thunder-rift:mercy-mace']
  self.assertTrue(mace['access']['proficiency_interactions'])
 def test_setting_and_publication_are_distinct(self):
  tx=Taxonomy(ROOT/'catalog/taxonomy/entities.json')
  self.assertEqual(tx.resolve('Zanzars Dungeon'),'publication:zanzer')
  self.assertNotIn('setting:thunder-rift',tx.descendants('setting:mystara'))
  self.assertEqual(self.items['mystara:shield-halav-echo']['origin_culture_ids'],['culture:traladaran'])
  q=json.loads((ROOT/'catalog/settings/thunder-rift/research-queue.json').read_text())
  self.assertTrue({'haunted-tower','dragons-den','night-of-the-vampire','hail-the-heroes'}<={r['id'] for r in q['workstreams']})
  self.assertFalse(any(r['original_book_item_audit_complete'] for r in q['workstreams']))

if __name__=='__main__':unittest.main()
