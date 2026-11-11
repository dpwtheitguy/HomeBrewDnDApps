import hashlib,json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shared'))
from catalog_search import search
class LocalPdfFactsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3');cls.db.row_factory=sqlite3.Row
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def item(self,iid):return json.loads(self.db.execute('select data_json from items where id=?',(iid,)).fetchone()[0])
 def test_verified_source_range_does_not_become_a_modern_merchant_price(self):
  r=self.item('gazetteer-equipment-reference:8bc1af6f81c3f285');f=r['mechanics']['verified_legacy_facts']
  self.assertEqual((f['minimum_gp'],f['maximum_gp']),(200,300));self.assertFalse(f['modern_charisma_quote']);self.assertFalse(r['valuation']['base_values']);self.assertIsNone(r['valuation']['reference_quote'])
  refs=[s for s in r['research_metadata']['source_refs'] if s['kind']=='user-provided-original-page'];self.assertTrue(refs)
  ref=refs[0];self.assertEqual(ref['locator'],{'pdf_page':59,'printed_page':58})
  path=ROOT/ref['local_file']
  if path.exists():self.assertEqual(ref['file_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
 def test_alias_search_finds_original_name_without_duplicate_definition(self):
  rows=search(self.db,ROOT/'catalog',query='fire starter',limit=100)
  self.assertTrue(any(r['id']=='gazetteer-equipment-reference:8bc1af6f81c3f285' for r in rows))
 def test_yataghan_mapping_follows_checked_original_glossary(self):
  r=self.item('mystara:yataghan');self.assertEqual(r['base_item_id'],'open5e-srd-2024:srd-2024_scimitar');self.assertTrue(r['research_metadata']['original_publication_verified']);self.assertIn('glossary',r['conversion']['conversion_note'].lower())
 def test_legacy_construction_costs_are_not_retail_prices(self):
  rows=[json.loads(r[0]) for r in self.db.execute("select data_json from items where source_id='gaz8-name-reference'")]
  checked=[r for r in rows if r['mechanics'].get('verified_legacy_facts',{}).get('price_kind')=='construction-cost'];self.assertEqual(len(checked),5)
  for r in checked:self.assertFalse(r['valuation']['base_values']);self.assertFalse(r['mechanics']['verified_legacy_facts']['market_price'])
if __name__=='__main__':unittest.main()
