#!/usr/bin/env python3
"""Publish the pinned 2024 SRD spell fields used by item inspection."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = 'data/v2/wizards-of-the-coast/srd-2024/Spell.json'
REVISION = 'bdcddf2b5f7995c42ac89722d8da563346b6744a'
FIELDS = ('name', 'desc', 'level', 'casting_time', 'reaction_condition', 'range_text', 'duration',
          'concentration', 'shape_type', 'shape_size', 'shape_size_unit', 'saving_throw_ability',
          'damage_roll', 'damage_types', 'material_specified', 'material_cost', 'material_consumed')

rows = json.loads((ROOT / 'catalog/raw/open5e/v2/wizards-of-the-coast/srd-2024/Spell.json').read_text())
output = {'schema_version': 1, 'source': 'https://github.com/open5e/open5e-api/blob/' + REVISION + '/' + FIXTURE,
          'srd': 'https://www.dndbeyond.com/srd', 'license': 'CC BY 4.0',
          'spells': {row['fields']['name'].casefold(): {key: row['fields'].get(key) for key in FIELDS} for row in rows}}
(ROOT / 'catalog/supplements/dnd-2024-spell-reference.json').write_text(
    json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
print(f'{len(rows)} SRD spell references.')
