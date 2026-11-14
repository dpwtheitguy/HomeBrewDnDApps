#!/usr/bin/env python3
"""Package the pinned revised SRD items as a separate catalog release."""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from package_catalog import ASSET_DIRECTORIES, ASSET_FILES, ROOT, package
from srd_publisher_items import ingest_publisher_items

SOURCE = 'open5e-srd-2024'
MAGIC_CONSUMABLES = {'potion-of-healing': 'common', 'potions-of-healing': 'varies', 'spell-scroll': 'varies'}
SRD_PDF = 'https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf'
FIXTURES = 'raw/open5e/v2/wizards-of-the-coast/srd-2024'
SADDLES = (
    'A saddle comes with a bit, a bridle, reins, and any other equipment needed to use the saddle. '
    'A Military Saddle gives Advantage on any ability check you make to remain mounted. '
    'An Exotic Saddle is required for riding an aquatic or a flying mount.'
)
GAMING_SET = (
    'Ability: Wisdom\nWeight: —\n'
    'Utilize: Discern whether someone is cheating (DC 10), or win the game (DC 20)\n'
    'Variants: Dice (1 SP), dragonchess (1 GP), playing cards (5 SP), three-dragon ante (1 GP)'
)
ELVEN_CHAIN = (
    'You gain a +1 bonus to Armor Class while you wear this armor. You are considered trained with this armor '
    'even if you lack training with Medium or Heavy armor.'
)
DRUIDIC_FOCUS = (
    'A Druidic Focus takes one of the forms in the Druidic Focuses table and is carved, tied with ribbon, or '
    'painted to channel primal magic. A Druid or Ranger can use such an object as a Spellcasting Focus.'
    '\n\n| Focus | Weight | Cost |\n|---|---|---|\n| Sprig of mistletoe | — | 1 GP |'
    '\n| Wooden staff (also a Quarterstaff) | 4 lb. | 5 GP |\n| Yew wand | 1 lb. | 10 GP |'
)
HOLY_SYMBOL = (
    'A Holy Symbol takes one of the forms in the Holy Symbol table and is bejeweled or painted to channel '
    'divine magic. A Cleric or Paladin can use a Holy Symbol as a Spellcasting Focus.\n\n'
    'The table indicates whether a Holy Symbol needs to be held, worn, or borne on fabric (such as a tabard '
    'or banner) or a Shield.\n\n| Symbol | Weight | Cost |\n|---|---|---|\n'
    '| Amulet (worn or held) | 1 lb. | 5 GP |\n| Emblem (borne on fabric or a Shield) | — | 5 GP |'
    '\n| Reliquary (held) | 2 lb. | 5 GP |'
)
MUSICAL_INSTRUMENT = (
    'Ability: Charisma\nWeight: Varies\nUtilize: Play a known tune (DC 10), or improvise a song (DC 15)\n'
    'Variants: Bagpipes (30 GP, 6 lb.), drum (6 GP, 3 lb.), dulcimer (25 GP, 10 lb.), flute (2 GP, 1 lb.), '
    'horn (3 GP, 2 lb.), lute (35 GP, 2 lb.), lyre (30 GP, 2 lb.), pan flute (12 GP, 2 lb.), '
    'shawm (2 GP, 1 lb.), viol (30 GP, 1 lb.)'
)
DONJON = (
    '**Donjon.** You disappear and become entombed in a state of suspended animation in an extradimensional sphere. '
    'Everything you’re wearing and carrying disappears with you except for Artifacts, which stay behind in the space '
    'you occupied when you disappeared. You remain imprisoned until you are found and removed from the sphere. '
    'You can’t be located by any Divination magic, but a Wish spell can reveal the location of your prison. '
    'You draw no more cards.'
)
TOOL_WEIGHTS = {
    'cartographers-tools': (93, 6), 'cooks-utensils': (93, 8),
    'jewelers-tools': (93, 2), 'weavers-tools': (94, 5),
    'brewers-supplies': (93, 9), 'carpenters-tools': (93, 6),
    'masons-tools': (93, 8), 'tinkers-tools': (94, 10),
    'alchemists-supplies': (93, 8), 'calligraphers-supplies': (93, 5),
    'cobblers-tools': (93, 5), 'glassblowers-tools': (93, 5),
    'leatherworkers-tools': (93, 5), 'painters-supplies': (93, 5),
    'potters-tools': (93, 3), 'smiths-tools': (93, 8),
    'disguise-kit': (94, 3), 'forgery-kit': (94, 5), 'poisoners-kit': (94, 2),
    'thieves-tools': (94, 1), 'woodcarvers-tools': (94, 5),
}
OFFICIAL_CORRECTIONS = {
    'herbalism-kit': (94, 'Ability: Intelligence\nWeight: 3 lb.\nUtilize: Identify a plant (DC 10)\n'
                          'Craft: Antitoxin, Candle, Healer’s Kit, Potion of Healing'),
    **{f'druidic-focus-{kind}': (97, DRUIDIC_FOCUS) for kind in ('sprig-of-mistletoe', 'wooden-staff', 'yew-wand')},
    **{f'holy-symbol-{kind}': (97, HOLY_SYMBOL) for kind in ('amulet', 'emblem', 'reliquary')},
    'navigators-tools': (94, 'Ability: Wisdom\nWeight: 2 lb.\n'
                         'Utilize: Plot a course (DC 10), or determine position by stargazing (DC 15)'),
    **{f'gaming-set-{kind}': (94, GAMING_SET) for kind in ('dice', 'dragonchess', 'playing-cards', 'three-dragon-ante')},
    **{f'elven-chain-{kind}': (220, ELVEN_CHAIN) for kind in ('mail', 'shirt')},
    'antitoxin': (96, 'As a Bonus Action, you can drink a vial of Antitoxin to gain Advantage on saving '
                 'throws to avoid or end the Poisoned condition for 1 hour.'),
    'bottle-glass': (96, 'A Glass Bottle holds up to 1½ pints.'),
    **{f'saddle-{kind}': (100, SADDLES) for kind in ('exotic', 'military', 'riding')},
}
MAP_CASE = 'open5e-srd-2024:srd-2024_case-map-or-scroll'
SUPPLEMENTS = (
    'published-2024-armor-facts', 'published-2024-weapon-facts',
    'core-armor-cross-references', 'core-magic-weapon-families', 'weapon-profiles-2024', 'item-prices',
    'dnd-2024-spell-reference', 'srd-2024-source-blocks',
)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def md5_text(text):
    return hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest()


def stage_catalog(source, target):
    transcriptions = {
        f"{SOURCE}:{row['pk']}": (kind, row['fields']['desc'])
        for kind in ('Item', 'MagicItem')
        for row in json.loads((source / FIXTURES / f'{kind}.json').read_text(encoding='utf-8'))
    }
    equipment_rows = json.loads((source / 'supplements/srd-2024-equipment-rows.json').read_text(encoding='utf-8'))
    for name in ASSET_FILES:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, path)
    for name in ASSET_DIRECTORIES:
        shutil.copytree(source / name, target / name)
    with sqlite3.connect(target / 'indexes/items.sqlite3') as db:
        db.execute("DELETE FROM items WHERE source_id <> ? OR ruleset <> 'dnd-2024'", (SOURCE,))
        for table in ('tags', 'associations', 'item_search', 'resource_items'):
            column = 'id' if table == 'item_search' else 'item_id'
            db.execute(f'DELETE FROM {table} WHERE {column} NOT IN (SELECT id FROM items)')
        db.execute('DELETE FROM resources WHERE id NOT IN (SELECT resource_id FROM resource_items)')
        ids = {row[0] for row in db.execute('SELECT id FROM items')}
        if not ids:
            raise ValueError('No revised SRD items found')
        for item_id, raw in db.execute('SELECT id, data_json FROM items').fetchall():
            item = json.loads(raw)
            kind, raw_text = transcriptions[item_id]
            slug = item_id.removeprefix(SOURCE + ':srd-2024_')
            table_row = equipment_rows.get(slug)
            correction = OFFICIAL_CORRECTIONS.get(slug)
            if table_row and not correction:
                correction = (table_row['page'], table_row['text'])
            if slug.startswith('musical-instrument-'):
                correction = (94, MUSICAL_INSTRUMENT)
            if slug == 'figurine-of-wondrous-power-ebony-fly':
                correction = (222, raw_text.replace('HP** 15 (3d10 + 3)', 'HP** 19 (3d10 + 3)')
                              .replace('Speed** Speed', 'Speed**'))
            if slug == 'mysterious-deck':
                correction = (232, raw_text.replace('**_Euryale._**', DONJON + '\n\n**_Euryale._**', 1))
            if slug.startswith('wand-of-the-war-mage-plus-'):
                correction = (251, raw_text.replace(' (Uncommon +1, Rare +2, Very Rare +3)', ''))
                item['mechanics']['source_fields']['attunement_detail'] = 'Requires Attunement by a Spellcaster'
            if slug == 'staff-of-charming':
                correction = (245, raw_text.replace('Reflect Enchantment.*', 'Reflect Enchantment.'))
            if slug in TOOL_WEIGHTS:
                page, weight = TOOL_WEIGHTS[slug]
                corrected = raw_text.replace('. Utilize: ', f'\nWeight: {weight} lb.\nUtilize: ', 1)
                correction = (page, corrected.replace('. Craft: ', '\nCraft: ', 1))
            if slug == 'robe-of-useful-items' and 'con forms' in raw_text:
                correction = (240, raw_text.replace('con forms', 'conforms'))
            if slug == 'figurine-of-wondrous-power-ivory-goats':
                intro = ('**Ivory Goats (Rare).** These ivory statuettes of goats are always created in sets of three. '
                         'Each goat looks unique and functions differently from the others. Their properties are as follows:')
                corrected, substitutions = re.subn(r'^\*\*_Golden Lions \(Rare\)\._\*\*[^\n]+', intro, raw_text,
                                                   flags=re.MULTILINE)
                if substitutions != 1:
                    raise ValueError('Ivory Goats upstream boundary changed; recheck the official entry')
                correction = (222, corrected)
            item['description'] = correction[1] if correction else raw_text
            if slug == 'figurine-of-wondrous-power-obsidian-stead':
                old_name = item['name']
                name = old_name.replace('Obsidian Stead', 'Obsidian Steed')
                item.update(name=name, name_key=name.casefold())
                db.execute('UPDATE items SET name=?, name_key=? WHERE id=?', (name, name.casefold(), item_id))
                db.execute('UPDATE item_search SET name=? WHERE id=?', (f'{name} {old_name}', item_id))
            text_evidence = {
                'reference': 'Open5e SRD 2024 fixture',
                'fixture': f'{kind}.json',
                'transcription_md5': md5_text(raw_text),
                'description_md5': md5_text(item['description']),
                'canonical_scope': 'published-item-description',
                'official_comparison': 'publisher-checked-correction' if correction else 'unverified',
            }
            if correction:
                text_evidence.update(source_text=raw_text, official_page=correction[0],
                                     official_url=f'{SRD_PDF}#page={correction[0]}')
            item['research_metadata']['srd_text'] = text_evidence
            tags = {tag for tag in item['tags'] if not tag.startswith(('appearance:', 'found-in:'))}
            if slug in MAGIC_CONSUMABLES:
                item.update(magic=True, rarity=MAGIC_CONSUMABLES[slug])
                tags = {tag for tag in tags if not tag.startswith('rarity:')} | {f"rarity:{item['rarity']}"}
                tags.discard('mundane')
                tags.add('magic')
            slaying = re.fullmatch(r'ammunition-of-(.+)-slaying', slug)
            if slaying or re.fullmatch(r'ammunition-plus-(?:one|two|three)', slug):
                item.update(type='ammunition', category='ammunition')
                tags -= {'type:weapon', 'category:weapon'}
                tags |= {'type:ammunition', 'category:ammunition'}
            if slaying:
                target_type = slaying[1].title()
                item['mechanics']['variant_rules'] = {
                    'target_type': target_type,
                    'summary': f'When this ammunition damages a creature of the {target_type} type, the creature '
                               'makes a DC 17 Constitution saving throw. It takes an extra 6d10 Force damage on '
                               'a failure or half as much extra damage on a success. After dealing its extra '
                               'damage, the ammunition becomes nonmagical.',
                }
            if slug.startswith('feather-token-'):
                variant = slug.removeprefix('feather-token-').replace('-', ' ').title()
                sections = dict(re.findall(
                    r'(?:\*\*)?(Anchor|Bird|Fan|Swan Boat|Tree|Whip) \(\w+\)\.(?:\*\*)?\s*'
                    r'(.*?)(?=(?:\*\*)?(?:Anchor|Bird|Fan|Swan Boat|Tree|Whip) \(\w+\)\.|\n\s*\||\Z)',
                    raw_text, re.DOTALL))
                if variant not in sections:
                    raise ValueError(f'Missing Feather Token section for {variant}')
                item['mechanics']['variant_rules'] = {'variant': variant, 'summary': sections[variant].strip()}
            if slug == 'horn-of-valhalla':
                item['rarity'] = 'varies'
                tags = {tag for tag in tags if not tag.startswith('rarity:')} | {'rarity:varies'}
                item['mechanics']['variant_rarities'] = {
                    'Silver': 'Rare', 'Brass': 'Rare', 'Bronze': 'Very Rare', 'Iron': 'Legendary',
                }
            if item_id == MAP_CASE:
                item.update(type='container', category='container')
                tags -= {'type:scroll', 'category:scroll'}
                tags |= {'type:container', 'category:container'}
            if item_id == SOURCE + ':srd-2024_airship':
                item.update(type='flying-vehicle', category='flying-vehicle')
                tags -= {'type:wondrous-item', 'category:wondrous-item'}
                tags |= {'type:flying-vehicle', 'category:flying-vehicle'}
            if item_id == SOURCE + ':srd-2024_ioun-stone':
                item.update(magic=True, rarity='varies', requires_attunement=True)
                tags.discard('mundane')
                tags.update({'magic', 'rarity:varies'})
            item['tags'] = sorted(tags)
            item['associations'] = [
                entry for entry in item.get('associations', [])
                if entry.get('role') != 'appearance' and not entry['entity_id'].startswith(('game:', 'setting:'))
            ]
            db.execute('UPDATE items SET type=?, rarity=?, data_json=? WHERE id=?',
                       (item['type'], item['rarity'], json.dumps(item, ensure_ascii=False), item_id))
            db.execute('DELETE FROM tags WHERE item_id=?', (item_id,))
            db.executemany('INSERT INTO tags VALUES (?,?)', ((item_id, tag) for tag in item['tags']))
            db.execute('UPDATE item_search SET tags=?, description=? WHERE id=?',
                       (' '.join(item['tags']), (item['mechanics'].get('variant_rules') or {}).get('summary')
                        or item.get('description') or '', item_id))
            retained = {entry['entity_id'] for entry in item['associations']}
            for entity, in db.execute('SELECT entity_id FROM associations WHERE item_id=?', (item_id,)).fetchall():
                if entity not in retained:
                    db.execute('DELETE FROM associations WHERE item_id=? AND entity_id=?', (item_id, entity))
        publisher_ids, publisher_prices = ingest_publisher_items(db, source)
        ids.update(publisher_ids)
        entities = {row[0] for row in db.execute('SELECT DISTINCT entity_id FROM associations')}
        db.commit()
        db.execute('VACUUM')
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    sources = json.loads((source / 'sources.json').read_text())
    write(target / 'sources.json', [{**row, 'record_count': len(ids)} for row in sources if row['id'] == SOURCE])
    taxonomy = json.loads((source / 'taxonomy/entities.json').read_text())
    taxonomy['entities'] = [row for row in taxonomy['entities'] if row['id'] in entities]
    write(target / 'taxonomy/entities.json', taxonomy)
    presets = json.loads((source / 'filters/presets.json').read_text())
    if isinstance(presets, dict) and 'presets' in presets:
        presets['presets'] = []
    else:
        presets = []
    write(target / 'filters/presets.json', presets)
    (target / 'supplements').mkdir()
    for name in SUPPLEMENTS:
        path = source / 'supplements' / f'{name}.json'
        data = json.loads(path.read_text())
        if name == 'item-prices':
            data['records'].update(publisher_prices)
        for section in ('records', 'modern', 'public'):
            if section in data:
                data[section] = {key: value for key, value in data[section].items() if key in ids}
        if name == 'item-prices':
            data['records'] = dict(sorted(data['records'].items()))
        if name == 'srd-2024-source-blocks':
            for record in data['records'].values():
                record['md5'] = md5_text(record['text'])
                record['url'] = f"{SRD_PDF}#page={record['start_page']}"
        for key in ('counts', 'decoration_counts'):
            data.pop(key, None)
        write(target / 'supplements' / path.name, data)
    return len(ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        catalog = Path(directory) / 'catalog'
        count = stage_catalog(ROOT / 'catalog', catalog)
        print(f'{count} revised SRD records')
        print(package(args.version, args.output, catalog).resolve())


if __name__ == '__main__':
    main()
