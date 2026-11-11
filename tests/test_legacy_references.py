import json,sqlite3,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class LegacyReferenceTests(unittest.TestCase):
 def test_4e_names_do_not_contain_the_mirror_level_label(self):
  total=0
  for name in ['adventurers-vault-1-reference','adventurers-vault-2-reference']:
   data=json.loads((ROOT/'catalog/raw/setting-reference-indexes'/f'{name}.json').read_text())
   total+=len(data['records'])
   for row in data['records']:
    self.assertNotRegex(row['name'],r'Level\s+\d')
    self.assertIn('Published in Adventurer',row['published_in'])
    if row['evidence_kind']=='publication-page-reference':
     self.assertTrue(row['original_book_verified'])
     self.assertIn('name',row['verified_fields'])
     self.assertGreater(row['locator']['printed_page'],0)
     self.assertRegex(row['pdf_sha256'],r'^[a-f0-9]{64}$')
    else:
     self.assertFalse(row['original_book_verified'])
  self.assertGreater(total,800)
 def test_vault_records_and_aliases_reach_sqlite(self):
  with sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3') as db:
   for volume in (1,2):
    source=f'adventurers-vault-{volume}-reference'
    raw=json.loads((ROOT/'catalog/raw/setting-reference-indexes'/f'{source}.json').read_text())['records']
    items=[json.loads(payload) for (payload,) in db.execute(
     'SELECT data_json FROM items WHERE source_id=?',(source,))]
    indexed={item['name']:item for item in items}
    self.assertEqual(len(indexed),len(items))
    self.assertCountEqual(indexed.keys(),[row['name'] for row in raw])
    for row in raw:
     if row['source_type']=='item-set':
      self.assertEqual(indexed[row['name']]['type'],'item-set',row['name'])
     for alias in row.get('aliases',[]):
      matches=db.execute(
       'SELECT items.name FROM item_search JOIN items ON items.id=item_search.id '
       'WHERE item_search MATCH ? AND items.source_id=?',
       ('"'+alias.replace('"','""')+'"',source)).fetchall()
      self.assertIn((row['name'],),matches)
     if row['evidence_kind']!='publication-page-reference':
      continue
     provenance=indexed[row['name']]['provenance']
     self.assertEqual(provenance['source_url'],row['url'])
     self.assertEqual(provenance['locator'],row['locator'])
     self.assertEqual(provenance['source_file_sha256'],row['pdf_sha256'])
   matches=db.execute(
    'SELECT items.name FROM item_search JOIN items ON items.id=item_search.id '
    'WHERE item_search MATCH ? AND items.source_id=?',
    ('"Shield of Sliver Light"','adventurers-vault-2-reference')).fetchall()
   self.assertEqual(matches,[('Shield of Silver Light',)])
 def test_reprint_values_retain_transcription_evidence(self):
  source='dmg-1e-reference'
  raw=json.loads((ROOT/'catalog/raw/setting-reference-indexes'/f'{source}.json').read_text())['records']
  corrected=[row for row in raw if 'source_value_reconciliation' in row]
  self.assertGreaterEqual(len(corrected),5)
  with sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3') as db:
   for row in corrected:
    with self.subTest(name=row['name']):
     result=db.execute(
      'SELECT data_json FROM items WHERE source_id=? AND name=?',
      (source,row['name'])).fetchone()
     self.assertIsNotNone(result, row['name'])
     metadata=json.loads(result[0])['mechanics']['reference_metadata']
     evidence=row['source_value_reconciliation']
     field=evidence.get('field','source_sale_gp')
     self.assertEqual(metadata[field],row[field])
     self.assertEqual(metadata['source_value_reconciliation'],evidence)
   stone=db.execute(
    'SELECT items.name,item_search.name,items.data_json FROM items '
    'JOIN item_search ON item_search.id=items.id WHERE items.source_id=? AND items.name=?',
    (source,'Stone of Controlling Earth Elementals')).fetchone()
   self.assertIsNotNone(stone)
   name,search_text,payload=stone
   metadata=json.loads(payload)['mechanics']['reference_metadata']
   self.assertEqual(metadata['source_xp_award'],'1,500')
   self.assertIn('Stone of Controlling Earth',metadata['aliases'])
   self.assertEqual(search_text,name+' Stone of Controlling Earth')

 def test_old_edition_names_are_not_automatically_modern_rules(self):
  db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3')
  rows=[json.loads(r[0]) for r in db.execute("SELECT data_json FROM items WHERE ruleset IN ('dnd-3e','dnd-4e')")];db.close()
  self.assertTrue(rows)
  for row in rows:
   self.assertIsNone(row['description']);self.assertEqual(row['tabletop_status'],'adaptation-needed')
   self.assertFalse(any(c['kind']=='rules-adaptation' for c in row['research_metadata']['change_log']))
 def test_mystara_artifact_candidates_do_not_all_become_artifacts(self):
  db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3')
  rows=[json.loads(r[0]) for r in db.execute("SELECT data_json FROM items WHERE source_id='mystara-artifact-name-reference'")];db.close()
  self.assertEqual(len(rows),100)
  for row in rows:self.assertIsNone(row['rarity']);self.assertIsNone(row['magic'])
  self.assertTrue(any('GAZ5' in row['mechanics']['reference_metadata']['reported_book_codes'] for row in rows))

 def test_ballista_engine_and_ammunition_use_linked_siege_rules(self):
  engine='mystara-fan-names-reference:3ffbb53cafbb75be'
  bolt='mystara-fan-names-reference:86a0c93771c65462'
  supplements=ROOT/'catalog/supplements'
  details=json.loads((supplements/'curated-item-details.json').read_text())['records']
  profiles=json.loads((supplements/'weapon-profiles-2024.json').read_text())['records']
  self.assertEqual(profiles[engine]['kind'],'siege-engine')
  for item,related in [(engine,bolt),(bolt,engine)]:
   rules=next(entry for entry in details[item] if entry['status']=='published-reference')
   self.assertEqual(rules['related_item']['id'],related)
   self.assertIn('3d10 Piercing',rules['fields']['Damage'])
   self.assertIn('480 ft',rules['fields']['Range'])
  with sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3') as db:
   rows=db.execute(
    "SELECT id,type FROM items WHERE source_id='conan-exiles-reference' "
    "AND (name LIKE '% Ballista Bolt' OR name LIKE '% Ballista Ball')"
   ).fetchall()
  self.assertEqual(len(rows),6)
  for item,kind in rows:
   self.assertEqual(kind,'ammunition')
   self.assertNotIn(item,profiles)
   self.assertIn('Crafting',details[item][0]['fields'])

if __name__=='__main__':unittest.main()
