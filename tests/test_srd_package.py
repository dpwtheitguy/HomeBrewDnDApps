"""Check rule dependencies and item classifications in a staged SRD import."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_srd_catalog import FIXTURES, SOURCE, md5_text, stage_catalog


class SrdPackageTests(unittest.TestCase):
    def test_reimport_preserves_armor_rules_and_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            stage_catalog(ROOT / 'catalog', target)
            with sqlite3.connect(target / 'indexes/items.sqlite3') as db:
                self.assertEqual(db.execute('SELECT DISTINCT source_id FROM items').fetchall(), [(SOURCE,)])
                for slug in ('potion-of-healing', 'potions-of-healing', 'spell-scroll', 'case-map-or-scroll'):
                    item_id = f'{SOURCE}:srd-2024_{slug}'
                    kind, raw = db.execute('SELECT type, data_json FROM items WHERE id=?', (item_id,)).fetchone()
                    item = json.loads(raw)
                    if slug == 'case-map-or-scroll':
                        self.assertEqual(kind, 'container')
                        self.assertNotIn('type:scroll', item['tags'])
                    else:
                        self.assertIs(item['magic'], True)
                        self.assertIn('magic', item['tags'])
                        self.assertNotIn('mundane', item['tags'])
                def record(slug):
                    (raw,) = db.execute('SELECT data_json FROM items WHERE id=?',
                                        (f'{SOURCE}:srd-2024_{slug}',)).fetchone()
                    return json.loads(raw)

                self.assertEqual(record('airship')['type'], 'flying-vehicle')
                self.assertIn('1½ pints', record('bottle-glass')['description'])
                self.assertIs(record('ioun-stone')['requires_attunement'], True)
                self.assertIs(record('ioun-stone')['magic'], True)
                pinned = {
                    f"{SOURCE}:{row['pk']}": row['fields']['desc']
                    for kind in ('Item', 'MagicItem')
                    for row in json.loads((ROOT / 'catalog' / FIXTURES / f'{kind}.json').read_text())
                }
                for item_id, raw in db.execute('SELECT id, data_json FROM items'):
                    item = json.loads(raw)
                    evidence = item['research_metadata']['srd_text']
                    if item_id in pinned:
                        self.assertEqual(evidence.get('source_text', item['description']), pinned[item_id])
                        self.assertEqual(evidence['transcription_md5'], md5_text(pinned[item_id]))
                    else:
                        self.assertEqual(evidence['official_comparison'], 'publisher-direct')
                        self.assertGreater(evidence['official_page'], 0)
                        self.assertEqual(len(evidence['publisher_pdf_sha256']), 64)
                    self.assertEqual(evidence['description_md5'], md5_text(item['description']))
                navigator = record('navigators-tools')
                self.assertIn('Plot a course (DC 10)', navigator['description'])
                self.assertIn('stargazing (DC 15)', navigator['description'])
                self.assertEqual(navigator['research_metadata']['srd_text']['official_page'], 94)
                self.assertIn('Ability: Wisdom', record('gaming-set-dragonchess')['description'])
            armor = json.loads((target / 'supplements/core-armor-cross-references.json').read_text())
            self.assertEqual(armor['modern'][f'{SOURCE}:srd-2024_dwarven-plate']['bonus'], 2)
            half_plate = armor['modern'][f'{SOURCE}:srd-2024_dwarven-half-plate']
            self.assertEqual(half_plate['bonus'], 2)
            self.assertIn('Reaction', half_plate['effect'])
            self.assertIs(armor['modern'][f'{SOURCE}:srd-2024_mithral-armor-chain-mail']['mithral'], True)
            self.assertTrue(all(key.startswith(f'{SOURCE}:') for section in ('records', 'modern', 'public')
                                for key in armor[section]))
