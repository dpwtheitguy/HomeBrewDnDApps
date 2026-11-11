import hashlib,json,sys,unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from record_context import attach_context

class RecordContextTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.items={i['id']:i for i in map(json.loads,(ROOT/'catalog/items.jsonl').read_text().splitlines())}
 def test_every_catalog_record_has_sources_and_explicit_changes(self):
  for item in self.items.values():
   m=item['research_metadata'];self.assertEqual(m['source_manifest_id'],item['source_id'])
   self.assertTrue(m['source_refs'],item['id']);self.assertTrue(m['change_log'])
   for ref in m['source_refs']:
    url=urlsplit(ref['url'])
    if url.scheme in ('http','https'):
     self.assertTrue(url.netloc)
     continue
    self.assertFalse(url.scheme or url.netloc)
    path=(ROOT/'catalog/raw'/unquote(url.path)).resolve()
    self.assertTrue(path.is_relative_to(ROOT/'pdfs') and path.is_file(),ref['url'])
    if url.fragment:
     self.assertEqual(url.fragment,'page='+str(item['provenance']['locator']['pdf_page']))
   self.assertEqual(len(m['record_content_sha256']),64)
   self.assertTrue(all(isinstance(c['changes_gameplay'],bool) for c in m['change_log']))
 def test_pinned_source_fixture_is_traceable_and_raw(self):
  row=self.items['open5e-srd-2024:srd-2024_dagger']
  refs=[r for r in row['research_metadata']['source_refs'] if r['kind']=='source-fixture']
  self.assertEqual(len(refs),1)
  ref=refs[0];path=ROOT/ref['local_file']
  self.assertEqual(ref['file_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
  self.assertIn(row['provenance']['repository_commit'],ref['url'])
 def test_draft_delta_is_not_replaced_by_a_generic_claim(self):
  r=self.items['ninja:mist-step-mantle']
  changes=r['research_metadata']['change_log']
  self.assertTrue(any(c['kind']=='rules-adaptation' and c['description']==r['conversion']['changes'] for c in changes))
  self.assertTrue(any(c['kind']=='price-estimate' for c in changes))
 def test_metadata_reference_does_not_claim_a_rules_conversion(self):
  r=next(r for r in self.items.values() if r['source_id']=='diablo-4-reference')
  changes=r['research_metadata']['change_log']
  self.assertTrue(any(c['kind']=='metadata-projection' for c in changes))
  self.assertFalse(any(c['kind']=='rules-adaptation' for c in changes))
  self.assertFalse(r['research_metadata']['original_publication_verified'])
 def test_editorial_correction_retains_its_actual_history(self):
  r=self.items['mystara:buffalo-hide-shield']
  self.assertIn('2026-11-07-atruaghin-clan-correction',r['research_metadata']['editorial_event_ids'])
  self.assertTrue(any(c['kind']=='editorial-correction' for c in r['research_metadata']['change_log']))
 def test_fingerprint_can_detect_modified_record_content(self):
  r=json.loads(json.dumps(self.items['ninja:katana']));m=r.pop('research_metadata')
  raw=json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
  self.assertEqual(hashlib.sha256(raw).hexdigest(),m['record_content_sha256'])
  r['name']='Changed name'
  self.assertNotEqual(hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),m['record_content_sha256'])

if __name__=='__main__':unittest.main()
