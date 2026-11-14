#!/usr/bin/env python3
"""Compare every Armory release record with the Android database and its indexes."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile


def read_database(path):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchall()[0][0] != 'ok':
            raise ValueError(f'SQLite integrity failure: {path}')
        fk_errors = [tuple(row) for row in db.execute('PRAGMA foreign_key_check')]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        queries = {
            'items': 'SELECT * FROM items', 'tags': 'SELECT item_id,tag FROM tags',
            'item_search': 'SELECT id,name,tags,description FROM item_search',
            'item_cards': 'SELECT * FROM item_cards', 'item_prices': 'SELECT * FROM item_prices',
            'item_proficiencies': 'SELECT * FROM item_proficiencies',
        }
        return {name: [dict(r) for r in db.execute(sql)] for name, sql in queries.items()
                if name in tables}, fk_errors


def group(rows, key):
    result = {}
    for row in rows:
        result.setdefault(row[key], []).append(row)
    return result


def audit(archive, apk):
    with tempfile.TemporaryDirectory() as directory, ZipFile(archive) as bundle, ZipFile(apk) as app:
        release = json.loads(bundle.read('manifest.json'))
        apk_manifest = json.loads(app.read('assets/manifest.json'))
        if apk_manifest['content_version'] != release['content_version']:
            raise ValueError('APK and release versions differ')
        db_name = release['database']
        package_bytes = bundle.read(db_name)
        with app.open('assets/database.zip') as compressed, ZipFile(compressed) as packed_db:
            apk_bytes = packed_db.read(db_name)
        for manifest, payload in ((release, package_bytes), (apk_manifest, apk_bytes)):
            if hashlib.sha256(payload).hexdigest() != manifest['files'][db_name]['sha256']:
                raise ValueError('Manifest database digest mismatch')
        root = Path(directory)
        (root / 'release.db').write_bytes(package_bytes)
        (root / 'apk.db').write_bytes(apk_bytes)
        catalog, catalog_fk = read_database(root / 'release.db')
        android, android_fk = read_database(root / 'apk.db')
        sources = {r['id']: r['record_count'] for r in json.loads(bundle.read('catalog/sources.json'))}
        prices = json.loads(bundle.read('catalog/supplements/item-prices.json'))['records']
        supplements = {}
        for name in bundle.namelist():
            if name.startswith('catalog/supplements/') and name.endswith('.json'):
                filename = Path(name).name
                content = bundle.read(name)
                if filename != 'item-prices.json' and app.read('assets/web/' + filename) != content:
                    raise ValueError(f'APK supplement differs: {filename}')
                supplements[filename] = json.loads(content)

    rows = {row['id']: row for row in catalog['items']}
    ids = set(rows)
    indexed = {
        name: group(data, 'item_id' if name in ('tags', 'item_prices', 'item_proficiencies') else 'id')
        for name, data in android.items()
    }
    original_search = group(catalog['item_search'], 'id')
    global_issues = []
    if catalog_fk or android_fk:
        global_issues.append({'foreign_key_errors': [catalog_fk, android_fk]})
    if dict(Counter(row['source_id'] for row in rows.values())) != sources:
        global_issues.append('Source counts do not match the manifest')
    for name in ('items', 'item_search', 'item_cards', 'item_prices'):
        if set(indexed[name]) != ids:
            global_issues.append(f'{name} has missing or extra stable IDs')
    for name in ('tags', 'item_proficiencies'):
        if set(indexed[name]) - ids:
            global_issues.append(f'{name} has orphan item IDs')
    for name, supplement in supplements.items():
        for section in ('records', 'modern', 'public'):
            if set(supplement.get(section, {})) - ids:
                global_issues.append(f'{name}:{section} has orphan supplement keys')
    checks = []
    for item_id, row in rows.items():
        item = json.loads(row['data_json'])
        issues = []
        for field in ('id', 'name', 'name_key', 'source_id', 'ruleset', 'type', 'rarity'):
            if item.get(field) != row[field]:
                issues.append(f'SQL/JSON mismatch: {field}')
        if item['image']['path'] != row['image_path']:
            issues.append('SQL/JSON image mismatch')
        base = item.get('base_item_id')
        if base and base not in ids:
            issues.append(f'Missing base item: {base}')
        if {r['tag'] for r in indexed['tags'].get(item_id, [])} != set(item['tags']):
            issues.append('APK tags differ from payload')
        for index in ('items', 'item_search', 'item_cards', 'item_prices'):
            if len(indexed[index].get(item_id, [])) != 1:
                issues.append(f'Expected one {index} row')
        if not issues:
            if indexed['items'][item_id][0] != row:
                issues.append('APK item differs from release')
            if indexed['item_search'][item_id] != original_search.get(item_id):
                issues.append('APK search row differs from release')
            card = indexed['item_cards'][item_id][0]
            if any(card[k] != row[k] for k in row if k != 'data_json'):
                issues.append('Android card projection differs from release')
            price = prices.get(item_id)
            apk_price = json.loads(indexed['item_prices'][item_id][0]['price_json'])
            if not price or any(apk_price.get(k) != v for k, v in price.items()):
                issues.append('Android price differs from release')
            elif any(Decimal(price[key]) <= 0 for key in ('base_cost_gp', 'base_buy_gp', 'base_sell_gp')):
                issues.append('Missing positive price')
        if row['source_id'] == 'bg3-wiki':
            details = supplements.get('curated-item-details.json', {}).get('records', {}).get(item_id, [])
            metadata = item.get('research_metadata', {})
            source_refs = metadata.get('source_refs', [])
            payload = {key: value for key, value in item.items() if key != 'research_metadata'}
            record_hash = hashlib.sha256(json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')
            ).encode('utf-8')).hexdigest()
            if metadata.get('record_content_sha256') != record_hash:
                issues.append('BG3 record digest mismatch')
            if len(details) != 1 or not source_refs or details[0]['source'] != source_refs[0]['url']:
                issues.append('BG3 rules panel or pinned primary source mismatch')
            if item['rarity'] and '*' in item['rarity']:
                issues.append('Source annotation in rarity')
        result = {'id': item_id, 'name': row['name'], 'issues': issues}
        if row['source_id'] == 'bg3-wiki':
            result['pinned_links'] = [ref['url'] for ref in source_refs]
        checks.append(result)
    return {'release': release['content_version'], 'sources': sources,
            'global_issues': global_issues, 'records': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('apk', type=Path)
    args = parser.parse_args()
    report = audit(args.archive, args.apk)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(report['global_issues'] or any(r['issues'] for r in report['records']))


if __name__ == '__main__':
    raise SystemExit(main())
