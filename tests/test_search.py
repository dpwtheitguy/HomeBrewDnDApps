import json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shared'))
from catalog_taxonomy import Taxonomy
from catalog_search import search

class CatalogSearchTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tx=Taxonomy(ROOT/'catalog/taxonomy/entities.json')
  cls.db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3');cls.db.row_factory=sqlite3.Row
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def query(self,**kwargs):return [json.loads(r['data_json']) for r in search(self.db,ROOT/'catalog',limit=1000,**kwargs)]
 def test_aliases_and_different_worlds(self):
  self.assertEqual(self.tx.resolve('The Known World'),'region:known-world')
  self.assertEqual(self.tx.resolve('Karameikos'),'region:karameikos')
  self.assertEqual(self.tx.resolve('Karameikan'),'culture:karameikan')
  self.assertNotEqual(self.tx.resolve('Thayan'),self.tx.resolve('Thyatian'))
  self.assertEqual(self.tx.resolve('Red Wizards'),'faction:red-wizards-of-thay')
  self.assertNotIn('region:thay',self.tx.descendants('setting:mystara'))
 def test_region_filter_and_unknown_data(self):
  rows=self.query(regions=['Karameikos'])
  self.assertTrue(any(i['name']=='Sword of Karameikos' for i in rows))
  self.assertTrue(all(any(a['entity_id']=='region:karameikos' and a['role'] in ('origin','cultural-association','found-in') for a in i['associations']) for i in rows))
  found=self.query(regions=['Karameikos'],relationship='found-in')
  self.assertTrue(found)
  self.assertTrue(any('region:karameikos' not in i['origin_region_ids'] for i in found))
  self.assertFalse(self.query(cultures=['Thayan'])) # Vocabulary alone does not invent items.
  self.assertGreater(len(self.query(regions=['Karameikos'],include_unattributed=True)),len(rows))
 def test_saved_profiles_and_overrides(self):
  rows=self.query(profile='mystara-workbench')
  self.assertGreaterEqual(len(rows),88)
  self.assertTrue(all('mystara' in r['setting_ids'] for r in rows))
  overridden=self.query(profile='mystara-workbench',settings=['Forgotten Realms'])
  self.assertTrue(overridden);self.assertTrue(all('forgotten-realms' in r['setting_ids'] for r in overridden))
  strict=self.query(profile='tabletop-2024')
  self.assertTrue(strict);self.assertFalse(any(r['content_status'] in ('original-conversion-draft','factual-metadata-only') for r in strict))
 def test_or_within_and_between_facets(self):
  a=self.query(regions=['Karameikos']);b=self.query(regions=['Glantri'])
  combined=self.query(regions=['Karameikos','Glantri'])
  self.assertEqual({r['id'] for r in combined},{r['id'] for r in a+b})
  self.assertFalse(self.query(settings=['Mystara'],regions=['Thay']))
 def test_prefix_text_and_parameterization(self):
  rows=self.query(query='dag',rulesets=['dnd-2024'],sort='relevance')
  self.assertTrue(any(r['name']=='Dagger' for r in rows))
  self.assertFalse(self.query(query='" OR 1=1 --'))
  self.assertFalse(self.query(tags=["magic' OR 1=1 --"]))
 def test_rarity_boolean_and_value_facets(self):
  rows=self.query(rulesets=['dnd-2024'],rarities=['uncommon'],magic='yes',attunement='yes')
  self.assertTrue(rows);self.assertTrue(all(r['magic'] and r['requires_attunement'] for r in rows))
  with self.assertRaises(ValueError):self.query(min_value=1)
  with self.assertRaises(ValueError):self.query(min_value=50,max_value=10,value_economy='dnd-2024')
  priced=self.query(min_value=1,max_value=20,value_economy='dnd-2024',sort='value')
  self.assertTrue(priced)
  for row in priced:self.assertTrue(1<=float(row['valuation']['base_values'][0]['amount_gp'])<=20)
 def test_required_association_fields_and_no_orphans(self):
  rows=self.db.execute('SELECT data_json FROM items').fetchall()
  for row in rows:
   item=json.loads(row[0]);self.assertIn('associations',item);self.assertTrue(item['family_id'])
   for a in item['associations']:self.assertIn(a['entity_id'],self.tx.entities)
  for eid,row in self.tx.entities.items():
   for parent in row['parent_ids']:self.assertIn(parent,self.tx.entities)
 def test_queue_progress_preserved_and_not_certified_complete(self):
  q=json.loads((ROOT/'catalog/research/queue.json').read_text())
  self.assertGreater(len(q['tasks']),1000)
  self.assertTrue(any(x['status']=='source-leads-found' for x in q['tasks']))
  self.assertTrue(any(x['status']=='unsearched' for x in q['tasks']))
  self.assertFalse(any(x['status']=='reviewed' for x in q['tasks']))

if __name__=='__main__':unittest.main()
