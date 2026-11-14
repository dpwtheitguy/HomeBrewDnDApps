"""Add SRD 5.2.1 entries missing from the pinned Open5e fixtures."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from item_enrichment import enrich
from item_pricing import price_catalog
from record_context import attach_context


SOURCE = 'open5e-srd-2024'
PREFIX = SOURCE + ':srd-2024_'
FIXTURE = 'raw/wizards-srd-5.2.1/magic-items.json'
PUBLISHER = 'Wizards of the Coast SRD 5.2.1'
CHASSIS = {
    'Energy Bow': ('longbow', 'shortbow'),
    'Quarterstaff of the Acrobat': ('quarterstaff',),
    'Sentinel Shield': ('shield',),
    'Shield of the Cavalier': ('shield',),
    'Thunderous Greatclub': ('greatclub',),
}
ICONS = {
    'Bead of Nourishment': 'food',
    'Cloak of Invisibility': 'cloak',
    'Gloves of Thievery': 'gloves',
    'Hat of Many Spells': 'helmet',
    'Sending Stones': 'gem',
}


def load_base(db, slug):
    row = db.execute('SELECT data_json FROM items WHERE id=?', (PREFIX + slug,)).fetchone()
    if not row:
        raise ValueError(f'Missing publisher item chassis {slug}')
    return json.loads(row[0])


def publisher_records(db, source):
    fixture = json.loads((source / FIXTURE).read_text(encoding='utf-8'))
    icons = json.loads((source / 'images/manifest.json').read_text(encoding='utf-8'))['icons']
    manifest = next(row for row in json.loads((source / 'sources.json').read_text(encoding='utf-8'))
                    if row['id'] == SOURCE)
    pdf = fixture['source_url']
    checksum = fixture['source_sha256']
    records = []
    chassis = {}
    for entry in fixture['records']:
        title = entry['title']
        description = entry['description']
        start_page = entry['start_page']
        url = f'{pdf}#page={start_page}'
        locator = {'book': PUBLISHER, 'section': 'Magic Items A–Z', 'printed_page': start_page,
                   'end_page': entry['end_page'], 'heading': title}
        attunement = entry['attunement']
        kind = entry['type']
        rarity = entry['rarity']
        for base_slug in CHASSIS.get(title, (None,)):
            base = load_base(db, base_slug) if base_slug else None
            name = f'{title} ({base["name"]})' if title == 'Energy Bow' else title
            slug = name.lower().replace(' (', ' ').replace(')', '').replace(' ', '-')
            icon = next(tag.split(':', 1)[1] for tag in base['tags'] if tag.startswith('icon-type:')) if base else ICONS.get(title, kind)
            base_mechanics = base['mechanics'] if base else {}
            fields = {'classification': entry['classification']}
            if isinstance(attunement, str):
                fields['attunement_detail'] = f'Requires attunement {attunement[0].lower()}{attunement[1:]}'
            if base:
                fields['weight'] = base_mechanics['source_fields'].get('weight')
                chassis[base['id']] = base
            tags = {
                'magic', 'ruleset:dnd-2024', f'source:{SOURCE}', f'type:{kind}', f'category:{kind}',
                f'rarity:{rarity}', f'icon-type:{icon}',
            }
            if attunement:
                tags.add('attunement:required')
            if title == 'Energy Bow':
                tags.add('damage:force')
            if title == 'Quarterstaff of the Acrobat':
                tags.add('property:thrown')
            if title == 'Thunderous Greatclub':
                tags.add('damage:thunder')
            if title == 'Shield of the Cavalier':
                tags.add('damage:force')
            item = {
                'id': PREFIX + slug, 'name': name, 'name_key': name.casefold(),
                'source_id': SOURCE, 'ruleset': 'dnd-2024', 'type': kind, 'category': kind,
                'tags': sorted(tags), 'magic': True, 'rarity': rarity, 'requires_attunement': bool(attunement),
                'description': description, 'content_status': 'publisher-verified-transcription',
                'tabletop_status': 'native-source-rules',
                'image': {**icons[icon], 'specific_art': None},
                'mechanics': {
                    'source_fields': fields,
                    'weapon': base_mechanics.get('weapon'), 'armor': base_mechanics.get('armor'),
                    'properties': base_mechanics.get('properties', []),
                    'reference_metadata': {'aliases': [title]} if name != title else {},
                },
                'provenance': {
                    'provider': PUBLISHER, 'source_url': url, 'source_file_sha256': checksum,
                    'locator': locator, 'original_publication_verified': True,
                    'verification_scope': 'Publisher magic-item entry, transcribed with PDF layout normalized.',
                    'verified_fields': ['name', 'classification', 'description', 'rarity', 'attunement'],
                },
                'associations': [], 'setting_ids': [], 'origin_region_ids': [], 'origin_culture_ids': [],
                'family_id': 'family:' + title.lower().replace(' ', '-'),
                'base_item_id': base['id'] if base else None, 'taxonomy_status': 'unattributed',
                'resource_ids': [],
            }
            enrich(item)
            if isinstance(attunement, str):
                item['access']['attunement_conditions'] = {
                    'status': 'source-derived', 'all_of': [{'predicate': attunement}], 'rule_refs': [url],
                }
            attach_context(item, manifest, source.parent)
            item['research_metadata']['srd_text'] = {
                'reference': PUBLISHER, 'canonical_scope': 'published-item-description',
                'official_comparison': 'publisher-direct', 'official_page': start_page,
                'official_url': url, 'publisher_pdf_sha256': checksum,
                'description_md5': hashlib.md5(description.encode('utf-8'), usedforsecurity=False).hexdigest(),
            }
            records.append(item)
    return records, list(chassis.values())


def ingest_publisher_items(db, source):
    """Add item rows, tags and FTS entries. Return IDs and their estimated prices."""
    items, chassis = publisher_records(db, source)
    prices = price_catalog(items + chassis)['records']
    for item in items:
        item_id = item['id']
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?)', (
            item_id, item['name'], item['name_key'], SOURCE, item['ruleset'], item['type'],
            item['rarity'], item['image']['path'], json.dumps(item, ensure_ascii=False),
        ))
        db.executemany('INSERT INTO tags VALUES(?,?)', ((item_id, tag) for tag in item['tags']))
        aliases = item['mechanics']['reference_metadata'].get('aliases', [])
        db.execute('INSERT INTO item_search VALUES(?,?,?,?)', (
            item_id, ' '.join([item['name'], *aliases]), ' '.join(item['tags']), item['description'],
        ))
    ids = {item['id'] for item in items}
    return ids, {item_id: prices[item_id] for item_id in ids}
