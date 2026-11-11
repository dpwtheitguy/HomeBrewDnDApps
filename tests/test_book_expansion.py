import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from fetch_book_reference_expansion import sections
from lxml import html
class BookExpansionTests(unittest.TestCase):
 def test_explicit_source_credit_does_not_bleed_into_next_item(self):
  t=html.fromstring('<div id="main"><h3>First</h3><p>Source: Arms and Equipment Guide</p><h3>Second</h3><p>A mention of Arms and Equipment Guide in prose.</p><h2>End</h2></div>')
  rows=list(sections(t));self.assertEqual(rows[0][1],['Arms and Equipment Guide']);self.assertEqual(rows[1][1],[])
 def test_local_candidates_received_source_attribution_review(self):
  d=json.loads((ROOT/'catalog/raw/setting-reference-indexes/mystara-craft-relic-reference.json').read_text());rows={r['name']:r for r in d['records']}
  for name in ['Tree of Life','Forge of Power','Crucible of Blackflame']:
   self.assertNotIn('GAZ6',rows[name]['reported_book_codes']);self.assertIn('RC',rows[name]['reported_book_codes'])
  self.assertEqual(rows['Proto-Zeppelin']['reported_book_codes'],['GAZ6'])
 def test_fan_creations_never_claim_gazetteer_origin(self):
  d=json.loads((ROOT/'catalog/raw/setting-reference-indexes/mystara-fan-names-reference.json').read_text())
  self.assertGreaterEqual(sum(r['source_type']=='unclassified-item' for r in d['records']),34)
  for r in d['records']:
   self.assertTrue(r['source_author']);self.assertFalse(r['original_book_verified']);self.assertNotIn('reported_book_codes',r);self.assertIn(r['evidence_kind'],{'named-fan-created-item','described-fan-created-item','named-fan-compendium-reference'})
  self.assertTrue(any(r.get('regional_entity_id')=='region:ierendi' for r in d['records']))
if __name__=='__main__':unittest.main()
