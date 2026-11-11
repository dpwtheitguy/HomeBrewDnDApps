import json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
from catalog_search import search

class ResourceCoverageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3');cls.db.row_factory=sqlite3.Row
  cls.resources={r['id']:r for r in json.loads((ROOT/'catalog/reports/resource-coverage.json').read_text())['resources']}
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def test_all_named_requests_have_a_ledger_entry(self):
  required={'setting-mystara','known-world','mystara-gazetteers','mystara-boxed-sets','setting-planescape','setting-ravenloft','curse-of-strahd','setting-forgotten-realms','return-temple','zanzer','goblins-lair','dragons-den','haunted-tower','night-of-the-vampire','hail-the-heroes','mark-of-amber','champions-mystara','culture-thyatian','culture-alphatian','complete-ninja-handbook','oriental-adventures-3e','hero-builder-3e','arms-equipment-3e','arms-equipment-4e','arms-equipment-5e','tomb-annihilation','rime-frostmaiden','worldbuilding'}
  required|={'baldurs-gate-'+str(n) for n in range(1,4)}|{'diablo-'+str(n) for n in range(1,5)}|{'mystara-gaz'+str(n) for n in range(1,15)}
  self.assertFalse(required-self.resources.keys())
 def test_series_have_real_children_and_never_certify_audit_from_counts(self):
  self.assertEqual(len(self.resources['mystara-gazetteers']['child_resource_ids']),14)
  for r in self.resources.values():
   self.assertNotEqual(r['original_item_audit_status'],'complete')
   for child in r['child_resource_ids']:self.assertIn(child,self.resources)
  self.assertEqual(self.resources['hero-builder-3e']['direct_or_inspired_records'],0)
 def test_links_reference_actual_items_and_report_context_separately(self):
  self.assertEqual(self.db.execute('SELECT count(*) FROM resources').fetchone()[0],len(self.resources))
  self.assertEqual(self.db.execute('SELECT count(*) FROM resource_items ri LEFT JOIN items i ON i.id=ri.item_id WHERE i.id IS NULL').fetchone()[0],0)
  kara=self.resources['karameikos-box'];self.assertGreater(kara['context_only_records'],0)
 def test_resource_filter_is_independent_of_setting_and_safe(self):
  rows=[json.loads(r['data_json']) for r in search(self.db,ROOT/'catalog',resources=['PHBR15'],limit=1000)]
  self.assertTrue(rows)
  self.assertTrue(all('complete-ninja-handbook' in r['resource_ids'] for r in rows))
  self.assertFalse(search(self.db,ROOT/'catalog',resources=['PHBR15'],settings=['Ravenloft']))
  with self.assertRaises(ValueError):search(self.db,ROOT/'catalog',resources=["x' OR 1=1 --"])
 def test_per_record_resource_links_and_context_metadata_agree(self):
  for r in self.db.execute('SELECT data_json FROM items'):
   item=json.loads(r[0]);self.assertEqual(item['resource_ids'],item['research_metadata']['resource_ids'])
   self.assertTrue(set(item['resource_ids'])<=self.resources.keys())

if __name__=='__main__':unittest.main()
