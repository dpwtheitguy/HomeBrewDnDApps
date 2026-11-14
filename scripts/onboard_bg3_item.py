#!/usr/bin/env python3
"""Verify pinned BG3 wiki evidence and package reviewed items with the SRD."""
import argparse
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path
from warnings import warn

from fetch_bg3 import extract_templates, request
from package_catalog import ROOT, package
from package_srd_catalog import stage_catalog, write

SOURCE = 'bg3-wiki'
TOY_SOURCE = 'curse-of-strahd-reference'
RARITIES = {'common', 'uncommon', 'rare', 'very rare', 'legendary', 'story'}
CITED_SHARED_RULES = {
    'Lacerate': ('Bleeding', ('Ghasts', 'Ghouls')),
    'Rush Attack': ('Rush Attack', ('creature or object',)),
}


CACHE = ROOT / '.cache/bg3-revisions'


def normalized_rarity(raw):
    if raw is None:
        return None
    # A wiki editor's bulleted note can be included in a template field.
    label = re.split(r'\s+\*', raw, maxsplit=1)[0].strip().casefold()
    if label not in RARITIES:
        raise ValueError(f'Unrecognized BG3 rarity {raw!r}')
    return label


def verify_rule_assertions(review, assertions):
    for label, patterns in assertions.items():
        text = (review['summary'] if label == 'Summary'
                else review['fields'].get(label, ''))
        for pattern in patterns:
            if not re.search(pattern, text, re.IGNORECASE):
                raise ValueError(f"{review['title']}: {label} does not satisfy {pattern!r}")


def verify_camp_supplies(title, fields, raw):
    supply_text = next((value for label, value in fields.items()
                        if label.casefold() == 'camp supplies'), None)
    if supply_text is None:
        return
    templates = extract_templates(raw, {'miscitempage'}, {'camp supplies'}.__contains__)
    quantities = {entry['facts'].get('camp supplies') for entry in templates}
    if len(quantities) != 1:
        return
    quantity = next(iter(quantities))
    if not quantity or not quantity.isdecimal():
        return
    displayed = re.search(r'^\s*(\d+)\b|\b(\d+)\s+(?:Camp\s+)?Suppl(?:y|ies)\b',
                          supply_text, re.IGNORECASE)
    if not displayed or int(displayed.group(1) or displayed.group(2)) != int(quantity):
        raise ValueError(f'{title}: Camp supplies differs from the pinned item')


def verify_batch_inventory(batch, reviews):
    letters = batch.get('letters') or [batch['prefix']]
    if any(not re.fullmatch(r'[a-zA-Z]', letter) for letter in letters):
        raise ValueError('Batch letters must be individual letters')
    prefixes = tuple(letter.casefold() for letter in letters)
    imported = {review['item_id'] for review in reviews
                if review['title'].casefold().startswith(prefixes)}
    recorded = set()
    included = {}
    for row in batch['candidates']:
        item_id = row['id']
        if (item_id in recorded or row['status'] not in {'imported', 'excluded', 'out-of-scope'} or
                not row['reason'].strip()):
            raise ValueError(f'Invalid batch disposition for {item_id}')
        if row['status'] == 'out-of-scope' and row['title'].casefold().startswith(prefixes):
            raise ValueError(f'Out-of-scope title is within the batch letters for {item_id}')
        recorded.add(item_id)
        if row['status'] == 'imported':
            included[item_id] = (row['title'], row['revision'])
    if imported != included.keys():
        raise ValueError(f'Batch and selected reviews differ: {sorted(imported ^ included.keys())}')
    for review in reviews:
        item_id = review['item_id']
        if item_id in included and included[item_id] != (review['title'], review['sources'][0]['revision']):
            raise ValueError(f'Batch title or primary revision differs for {item_id}')


def pinned_pages(revisions):
    CACHE.mkdir(parents=True, exist_ok=True)
    pages = []
    missing = []
    for key in revisions:
        path = CACHE / f'{key}.json'
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            raw = record['revisions'][0]['slots']['main']['content']
            if (record['revisions'][0]['revid'] != key or
                    hashlib.sha256(raw.encode('utf-8')).hexdigest() != record.pop('sha256', None)):
                raise ValueError(f'Cached wiki revision failed integrity validation: {key}')
            pages.append(record)
        else:
            missing.append(key)
    for start in range(0, len(missing), 25):
        result = request({'action': 'query', 'prop': 'revisions', 'rvprop': 'ids|content',
                          'rvslots': 'main', 'revids': '|'.join(map(str, missing[start:start + 25]))})
        for page in result['query']['pages']:
            for revision in page.get('revisions', []):
                record = {'pageid': page['pageid'], 'title': page['title'], 'revisions': [revision]}
                raw = revision['slots']['main']['content']
                payload = {**record, 'sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest()}
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=CACHE, delete=False) as tmp:
                    json.dump(payload, tmp, ensure_ascii=False)
                Path(tmp.name).replace(CACHE / f"{revision['revid']}.json")
                pages.append(record)
    return pages


def verify_sources(review):
    revisions = {source['revision']: source for source in review['sources']}
    if (len(revisions) != len(review['sources']) or
            sum(s['role'] == 'Item and recipe' for s in revisions.values()) != 1 or
            review['sources'][0]['role'] != 'Item and recipe'):
        raise ValueError(f"{review['title']}: pin one item revision first and list unique dependency revisions")
    for label, (source_title, clauses) in CITED_SHARED_RULES.items():
        if label in review['fields']:
            if not any(source['title'] == source_title for source in revisions.values()):
                raise ValueError(f"{review['title']}: pin {source_title} for {label}")
            verify_rule_assertions(review, {label: clauses})
    evidence = {}
    for page in pinned_pages(revisions):
        for revision in page.get('revisions', []):
            key = revision['revid']
            source = revisions[key]
            raw = revision['slots']['main']['content']
            if page['title'] != source['title'] or any(marker not in raw for marker in source['markers']):
                raise ValueError(f'Pinned evidence did not match review for revision {key}')
            if source['role'] == 'Item and recipe' and review['item_id'] != f"{SOURCE}:{page['pageid']}":
                raise ValueError('The pinned item revision belongs to a different catalog ID')
            if source['role'] == 'Item and recipe':
                fields = review['fields']
                verify_camp_supplies(review['title'], fields, raw)
                omitted_art = review.get('omit_art_reference')
                if omitted_art and omitted_art.removeprefix('File:') not in raw:
                    raise ValueError(f'{review["title"]}: artwork exclusion must identify a pinned file')
                if '{{unobtainable' in raw.casefold():
                    if 'unobtainable' not in fields.get('Availability', '').casefold() or 'vendors' in fields.get('Crafting', '').casefold():
                        warn(f'{review["title"]}: document unobtainable status and remove generic vendor claims', stacklevel=2)
                if '{{SAI|Throw}}' in raw and 'Replaces effects of other elixirs when applied this way' in raw:
                    if 'replac' not in fields.get('Throw', '').casefold():
                        warn(f'{review["title"]}: document elixir replacement in the Throw row', stacklevel=2)
                if '{{SAI|Throw}}' in raw and '{{Range|ranged}}' in raw:
                    if '60 ft' not in fields.get('Throw', ''):
                        raise ValueError(f'{review["title"]}: document the 60 ft throw range in the Throw row')
                if '{{DamageText|' in raw and '|Healing}}' in raw and 'Remove {{Cond|Burning}}' in raw:
                    if '{{SAI|Throw}}' in raw and 'Burning' not in fields.get('Throw', ''):
                        raise ValueError(f'{review["title"]}: review Burning removal in the healing splash')
            evidence[key] = {
                'kind': 'bg3-wiki-pinned-revision', 'label': source['role'],
                'url': f'https://bg3.wiki/w/index.php?oldid={key}', 'revision_id': key,
                'wikitext_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            }
    if evidence.keys() != revisions.keys():
        raise ValueError('Wiki did not return every reviewed revision')
    return [evidence[key] for key in revisions]


def add_item(source_db, target_db, review, evidence):
    item_id = review['item_id']
    row = source_db.execute('SELECT * FROM items WHERE id=? AND source_id=? AND ruleset=?',
                            (item_id, SOURCE, 'bg3')).fetchone()
    if row is None:
        raise ValueError(f'Existing BG3 index record required for {item_id}')
    item = json.loads(row[-1])
    if item['name'] != review['title']:
        if (review.get('use_wiki_title') is not True or
                review['title'] != review['sources'][0]['title']):
            raise ValueError(f'{item_id}: reviewed title {review["title"]!r} differs from indexed title {item["name"]!r}')
        item.update(name=review['title'], name_key=review['title'].casefold())
    item.update(description=review['summary'], content_status='reviewed-bg3-rules',
                tabletop_status='native-bg3-rules', magic='magic' in item['tags'])
    omitted_art = review.get('omit_art_reference')
    if omitted_art:
        references = item['image']['bg3_art_references']
        remaining_art = [ref for ref in references if ref['file_title'] != omitted_art]
        if not remaining_art or len(remaining_art) == len(references):
            raise ValueError(f'{item_id}: artwork exclusion must leave an indexed reference')
        item['image']['bg3_art_references'] = remaining_art
    if review.get('omit_conflicting_versatile_damage'):
        variants = item['mechanics']['bg3_template_variants']
        if not any(row['facts'].get('handedness') == 'one-handed' and
                   row['facts'].get('versatile damage') for row in variants):
            raise ValueError(f'{item_id}: no contradictory one-handed and versatile damage fields')
        for variant in variants:
            facts = variant['facts']
            if facts.get('handedness') == 'one-handed':
                facts.pop('versatile damage', None)
    item['rarity'] = normalized_rarity(item['rarity'])
    tags = {tag for tag in item['tags'] if not tag.startswith(('tabletop:', 'rarity:'))}
    tags.add('tabletop:native-bg3-rules')
    if item['rarity']:
        tags.add('rarity:' + item['rarity'].replace(' ', '-'))
    item['tags'] = sorted(tags)
    item.update(associations=[], resource_ids=[], setting_ids=[], origin_region_ids=[], origin_culture_ids=[])
    metadata = item['research_metadata']
    metadata.update(source_refs=evidence, resource_ids=[], verification_status='reviewed-bg3-rules',
                    change_log=[{'id': 'bg3-onboarding-v1', 'kind': 'source-review',
                                 'description': review['changes'], 'changes_gameplay': False}])
    item['provenance']['source_url'] = evidence[0]['url']
    item['provenance']['permanent_url'] = evidence[0]['url']
    if item['provenance'].get('revision_id') != evidence[0]['revision_id']:
        item['provenance'].pop('revision_timestamp', None)
    item['provenance']['revision_id'] = evidence[0]['revision_id']
    metadata['record_content_sha256'] = hashlib.sha256(
        json.dumps({k: v for k, v in item.items() if k != 'research_metadata'},
                   sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    target_db.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)',
                      (item_id, item['name'], item['name_key'], *row[3:6], item['rarity'],
                       row[7], json.dumps(item, ensure_ascii=False)))
    target_db.executemany('INSERT INTO tags VALUES (?,?)', ((item_id, tag) for tag in item['tags']))
    target_db.execute('INSERT INTO item_search VALUES (?,?,?,?)',
                      (item_id, item['name'], ' '.join(item['tags']), item['description']))


def add_blinsky_stock(source_db, target_db, prices):
    toys = []
    for row in source_db.execute('SELECT * FROM items WHERE source_id=? ORDER BY id', (TOY_SOURCE,)):
        item = json.loads(row[-1])
        locator = item['provenance'].get('locator') or {}
        if locator.get('area') == 'N7' and prices.get(row[0], {}).get('method') == 'source-retail':
            toys.append(row)
    if len(toys) != 6:
        raise ValueError(f'Expected six priced Blinsky toys, found {len(toys)}')
    for row in toys:
        item_id = row[0]
        target_db.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?)', row)
        target_db.execute('INSERT INTO item_search VALUES (?,?,?,?)', source_db.execute(
            'SELECT id,name,tags,description FROM item_search WHERE id=?', (item_id,)).fetchone())
        for table, count in (('tags', 2), ('associations', 4), ('resource_items', 4)):
            if table == 'resource_items':
                target_db.executemany('INSERT OR IGNORE INTO resources VALUES (?,?,?,?,?)', source_db.execute(
                    'SELECT resources.* FROM resources JOIN resource_items ON resources.id=resource_id WHERE item_id=?',
                    (item_id,)))
            target_db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" * count)})',
                                  source_db.execute(f'SELECT * FROM {table} WHERE item_id=?', (item_id,)))
    return [row[0] for row in toys]


def add_supplements(source, target, reviews, evidence, toy_ids, source_prices):
    sources_path = target / 'sources.json'
    sources = json.loads(sources_path.read_text())
    counts = {SOURCE: (len(reviews), 'Reviewed native BG3 items.'),
              TOY_SOURCE: (len(toy_ids), 'Six priced toys from Blinsky’s shop in Vallaki.')}
    for row in json.loads((source / 'sources.json').read_text()):
        if row['id'] in counts:
            count, coverage = counts[row['id']]
            sources.append({**row, 'record_count': count, 'coverage': coverage})
    write(sources_path, sources)
    taxonomy_path = target / 'taxonomy/entities.json'
    taxonomy = json.loads(taxonomy_path.read_text())
    original = json.loads((source / 'taxonomy/entities.json').read_text())
    known = {row['id'] for row in taxonomy['entities']}
    with sqlite3.connect(target / 'indexes/items.sqlite3') as db:
        used = {entity for (entity,) in db.execute('SELECT DISTINCT entity_id FROM associations')}
    taxonomy['entities'].extend(row for row in original['entities'] if row['id'] in used - known)
    write(taxonomy_path, taxonomy)
    supplements = target / 'supplements'
    pricing_path = supplements / 'item-prices.json'
    pricing = json.loads(pricing_path.read_text())
    pricing['records'].update({item_id: source_prices[item_id] for item_id in toy_ids})
    rules = {}
    for review, refs in zip(reviews, evidence, strict=True):
        item_id = review['item_id']
        pricing['records'][item_id] = source_prices[item_id]
        rules[item_id] = [{'label': 'Baldur’s Gate 3 rules', 'status': 'reviewed-bg3-rules',
                           'source': refs[0]['url'], 'fields': review['fields']}]
    pricing['records'] = dict(sorted(pricing['records'].items()))
    write(pricing_path, pricing)
    write(supplements / 'curated-item-details.json', {'schema_version': 1, 'records': rules})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path, nargs='+')
    parser.add_argument('--version', required=True)
    parser.add_argument('--batch-inventory', type=Path)
    args = parser.parse_args()
    reviews = [json.loads(path.read_text(encoding='utf-8')) for path in args.review]
    if len({review['item_id'] for review in reviews}) != len(reviews):
        parser.error('Duplicate BG3 review item IDs')
    if args.batch_inventory:
        verify_batch_inventory(json.loads(args.batch_inventory.read_text(encoding='utf-8')), reviews)
    assertions = json.loads((ROOT / 'scripts/bg3_rule_assertions.json').read_text())
    for review in reviews:
        verify_rule_assertions(review, assertions.get(review['item_id'], {}))
    pinned_pages(sorted({ref['revision'] for review in reviews for ref in review['sources']}))
    evidence = [verify_sources(review) for review in reviews]
    with tempfile.TemporaryDirectory() as temp:
        source = ROOT / 'catalog'
        target = Path(temp) / 'catalog'
        count = stage_catalog(source, target)
        source_prices = json.loads((source / 'supplements/item-prices.json').read_text())['records']
        with (sqlite3.connect(source / 'indexes/items.sqlite3') as source_db,
              sqlite3.connect(target / 'indexes/items.sqlite3') as target_db):
            for review, refs in zip(reviews, evidence, strict=True):
                add_item(source_db, target_db, review, refs)
            toy_ids = add_blinsky_stock(source_db, target_db, source_prices)
            if target_db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise ValueError('SQLite integrity check failed')
        add_supplements(source, target, reviews, evidence, toy_ids, source_prices)
        print(f'{count} SRD records, {len(reviews)} reviewed BG3 records, and {len(toy_ids)} Blinsky toys')
        print(package(args.version, ROOT / 'outputs', target))


if __name__ == '__main__':
    main()
