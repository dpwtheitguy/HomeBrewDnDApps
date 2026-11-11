import json,sqlite3,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from fetch_bg3 import extract,split_top
from build_catalog import classify

class ParserTests(unittest.TestCase):
    def test_template_whitespace_nested_values_and_variant_preservation(self):
        text='''{{WeaponPage
| type = Daggers
| damage = 1d4
| uid = FIRST
| quote = DO NOT COPY
| icon = Dagger.png
| name = [[Dagger|A dagger]]
| notes = {{Feature|a|b}}
}}
{{Weapon page | type = Daggers | uid = SECOND }}'''
        rows=extract(text)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['facts']['name'],'[[Dagger|A dagger]]')
        self.assertEqual(rows[1]['facts']['uid'],'SECOND')
        self.assertNotIn('quote',rows[0]['facts']);self.assertNotIn('notes',rows[0]['facts'])
    def test_comment_templates_not_imported(self):
        self.assertEqual(extract('<!-- {{WeaponPage | uid = fake }} -->'),[])
    def test_specific_type_over_incidental_name(self):
        self.assertEqual(classify('Ring Mail','armor')[1],'heavy-armor')
        self.assertEqual(classify('Dagger of Poison','weapon')[1],'dagger')
        self.assertEqual(classify('Ring of Shielding','ring')[1],'ring')

class BuiltCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items=[json.loads(x) for x in (ROOT/'catalog/items.jsonl').read_text().splitlines()]
        cls.stats=json.loads((ROOT/'catalog/reports/counts.json').read_text())
    def test_counts_sources_ids_and_images(self):
        self.assertEqual(len(self.items),self.stats['source_records'])
        self.assertEqual(len({i['id'] for i in self.items}),len(self.items))
        self.assertEqual(sum(self.stats['by_source'].values()),len(self.items))
        self.assertGreater(self.stats['by_source']['bg3-wiki'],4000)
        for item in self.items:
            self.assertTrue((ROOT/'catalog'/item['image']['path']).is_file(),item['id'])
            self.assertEqual(item['image']['kind'],'generic-type-icon')
            self.assertTrue(item['image']['author'])
            self.assertIsNone(item['image']['specific_art'])
    def test_bg3_is_metadata_and_not_tabletop_mechanics(self):
        for i in self.items:
            if i['ruleset']!='bg3': continue
            self.assertIsNone(i['description']);self.assertIsNone(i['magic'])
            self.assertEqual(i['tabletop_status'],'adaptation-needed')
            for t in i['mechanics']['bg3_template_variants']:
                self.assertNotIn('quote',t['facts']);self.assertNotIn('description',t['facts'])
    def test_edition_separation_and_search(self):
        db=sqlite3.connect(ROOT/'catalog/indexes/items.sqlite3')
        self.assertEqual(db.execute('SELECT count(*) FROM items').fetchone()[0],len(self.items))
        editions={x[0] for x in db.execute("SELECT ruleset FROM items WHERE lower(name)='dagger'")}
        self.assertTrue({'bg3','dnd-2014','dnd-2024'}<=editions)
        self.assertGreater(db.execute("SELECT count(*) FROM item_search WHERE item_search MATCH 'dagger'").fetchone()[0],3)
        self.assertGreater(db.execute("SELECT count(*) FROM tags WHERE tag='property:finesse'").fetchone()[0],0)
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok'); db.close()
    def test_pack_roundtrip(self):
        import yaml
        loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
        for path in (ROOT/'catalog/normalized').rglob('*.json'):
            self.assertEqual(json.loads(path.read_text()), yaml.load(path.with_suffix('.yaml').read_text(), Loader=loader))
    def test_svg_is_well_formed(self):
        for path in (ROOT/'catalog/images/types').glob('*.svg'): ET.parse(path)

if __name__=='__main__': unittest.main()
