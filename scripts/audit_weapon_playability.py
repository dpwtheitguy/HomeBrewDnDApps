#!/usr/bin/env python3
"""Audit the weapon records and rule supplements used by the Android catalog."""
import argparse
import collections
import csv
import json
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

from audit_pending_rules import key as normalize_name
from build_core_enhancement_cross_references import modern_plain_name, modern_variant_name

from build_core_magic_weapon_families import is_ranged_weapon

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
PROFILE_KINDS = {
    'native-2024', 'source-2024-text', 'native-bg3', 'source-based-2024',
    'draft-2024-base', 'improvised-2024', 'siege-engine', 'launcher',
    'weapon-upgrade', 'reference-object', 'custom-2024-draft', 'documented-reference',
}
BASE_PROFILE_KINDS = {'draft-2024-base', 'source-based-2024'}
DICE = re.compile(r'(?:\d+d\d+|\d+)(?:\s*[+-]\s*\d+)?', re.I)
BG3_RESTRICTIONS = {'npc-only': 'NPC weapon', 'unobtainable': 'Unavailable in normal play'}
PRICE_FIELDS = ('base_cost_gp', 'base_buy_gp', 'base_sell_gp')
FIELDS = (
    'id', 'name', 'source_id', 'ruleset', 'tabletop_status', 'profile', 'evidence',
    'native_evidence', 'damage', 'damage_type', 'range', 'training', 'mastery',
    'attack_bonus', 'activation', 'base_cost_gp', 'base_buy_gp', 'base_sell_gp', 'schema_errors', 'review_gaps',
)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load(catalog, name):
    return read_json(catalog / 'supplements' / (name + '.json'))


def dice(value):
    return isinstance(value, str) and DICE.fullmatch(value.strip()) is not None


def price_errors(price):
    try:
        cost, buy, sell = (Decimal(price[key]) for key in PRICE_FIELDS)
    except (KeyError, InvalidOperation, TypeError):
        return ['missing or malformed base, buy or sell price']
    if not all(value.is_finite() and value > 0 for value in (cost, buy, sell)):
        return ['non-positive or non-finite base, buy or sell price']
    if not buy >= cost >= sell:
        return ['price order must be buy ≥ base ≥ sell']
    return []


def source_fields(weapon, properties):
    melee = not weapon.get('range') and weapon.get('document') == 'srd-2024'
    normal = weapon.get('range')
    long = weapon.get('long_range')
    names = [
        entry['property'] for entry in properties
        if isinstance(entry, dict) and isinstance(entry.get('property'), dict)
    ]
    reach = '10 ft melee' if any(p.get('name') == 'Reach' for p in names) else '5 ft melee'
    return {
        'damage': weapon.get('damage_dice'),
        'damage_type': weapon.get('damage_type'),
        'range': reach if melee else f'{normal}/{long} ft' if normal else '',
        'training': {True: 'Simple', False: 'Martial'}.get(weapon.get('is_simple')),
        'mastery': ', '.join(p['name'] for p in names if p.get('type') == 'Mastery' and p.get('name')),
    }


def structured_2024(weapon, properties, errors):
    if not dice(weapon.get('damage_dice')) or not weapon.get('damage_type'):
        errors.append('2024 weapon needs damage and damage type')
    normal, long = weapon.get('range'), weapon.get('long_range')
    if (type(normal) not in (int, float) or type(long) not in (int, float)
            or not 0 <= normal <= long or bool(normal) != bool(long)):
        errors.append('2024 weapon has invalid normal or long range')
    if type(weapon.get('is_simple')) is not bool:
        errors.append('2024 weapon needs simple or martial classification')
    fields = source_fields(weapon, properties)
    if not fields['mastery']:
        errors.append('2024 weapon is missing a named mastery')
    return fields


def bg3_fields(entry, features, availability, errors, gaps):
    variants = entry.get('variants') or []
    if not variants:
        errors.append('BG3 weapon has no game-rule variants')
        return {}
    restriction = BG3_RESTRICTIONS.get(availability.get('restriction'))
    if availability and not (restriction and availability.get('source') and availability.get('note')):
        errors.append('invalid BG3 availability exception')
        restriction = None
    fields = collections.defaultdict(list)
    for index, variant in enumerate(variants, 1):
        stats = variant.get('stats') or {}
        mode = stats.get('melee or ranged', '')
        game_range = stats.get('range ft') or stats.get('range m') or stats.get('range')
        if not dice(stats.get('damage')) or not stats.get('damage type'):
            gaps.append(f'BG3 variant {index} needs structured damage')
        if mode not in {'melee', 'ranged'} or (mode == 'ranged' and not game_range):
            gaps.append(f'BG3 variant {index} needs attack range')
        if not stats.get('category') and not restriction:
            gaps.append(f'BG3 variant {index} needs training category')
        if variant.get('unparsed_special'):
            gaps.append(f'BG3 variant {index} has an unparsed special effect')
        for titles in (variant.get('features') or {}).values():
            for title in titles:
                if title not in features:
                    gaps.append(f'BG3 feature lacks a structured rule record: {title}')
        for key, value in (
            ('damage', stats.get('damage')), ('damage_type', stats.get('damage type')),
            ('training', stats.get('category') or restriction), ('attack_bonus', stats.get('enchantment')),
            ('range', mode if mode == 'melee' else (
                f"{stats['range ft']} ft" if stats.get('range ft') else
                f"≈{round(float(stats['range m']) * 3.28084)} ft"
                if re.fullmatch(r'\d+(?:\.\d+)?', str(stats.get('range m')))
                else {'normal': '60 ft', 'short': '50 ft'}.get(stats.get('range'))
            )),
        ):
            if value and value not in fields[key]:
                fields[key].append(value)
    return {key: ' / '.join(values) for key, values in fields.items()}


def audit_row(item, all_items, profiles, game, curated, exact, prices, legacy_game, availability, enhancements, plain):
    item_id, name = item['id'], item['name']
    errors, gaps = [], []
    mechanics = item.get('mechanics') or {}
    profile = profiles.get(item_id) or {}
    kind = profile.get('kind', '')
    base_id = profile.get('base_id')
    if kind not in PROFILE_KINDS:
        errors.append('missing or unknown weapon profile kind')
    if kind in BASE_PROFILE_KINDS and not base_id:
        errors.append('base weapon profile has no base ID')
    if base_id:
        base = all_items.get(base_id) or {}
        if (base_id == item_id or base.get('type') != 'weapon' or base.get('magic') is not False
                or base.get('ruleset') != 'dnd-2024' or base.get('source_id') != 'open5e-srd-2024'):
            errors.append('profile base ID must resolve to a different mundane 2024 SRD weapon')
            base = {}
    else:
        base = {}
    properties = mechanics.get('properties') or []
    source_weapon = mechanics.get('weapon') or {}
    evidence = 'unresolved'
    native = 'unstructured'
    fields = {}
    published = [
        entry['fields'] for entry in curated.get(item_id, [])
        if entry.get('status') == 'published-reference' and {'Damage', 'Range', 'Activation'} <= entry.get('fields', {}).keys()
    ]
    custom = [
        entry['fields'] for entry in curated.get(item_id, [])
        if entry.get('status') == 'original-draft' and entry.get('profile_kind') == 'custom-2024-draft'
    ]
    verified = enhancements.get(item_id, {})
    plain_match = plain.get(item_id, {})
    comparison_name = modern_variant_name(name) if verified else modern_plain_name(name) if plain_match else name
    if exact_id := verified.get('target_id') or plain_match.get('target_id') or exact.get(item_id):
        target = all_items.get(exact_id) or {}
        if (target.get('ruleset') != 'dnd-2024' or target.get('type') != 'weapon'
                or target.get('source_id') != 'open5e-srd-2024' or not target.get('description')
                or normalize_name(target.get('name', '')) != normalize_name(comparison_name)):
            errors.append('invalid exact 2024 weapon cross-reference')
            target = {}
    else:
        target = {}
    if source_weapon:
        native = 'source-structured'
        fields = source_fields(source_weapon, properties)
    if item_id in legacy_game:
        native = 'source-game-facts'
    if kind == 'native-bg3':
        if item['ruleset'] != 'bg3':
            errors.append('BG3 profile attached to a different ruleset')
        evidence = 'native-bg3'
        native = 'bg3-structured' if item_id in game['weapons'] else 'unstructured'
        fields = bg3_fields(game['weapons'].get(item_id, {}), game['features'],
                            availability.get(item_id, {}), errors, gaps)
    elif published:
        evidence = ('published-2024-reference' if item['source_id'] == 'open5e-srd-2024'
                    else 'published-2024-attack')
        fields = {
            'damage': published[0]['Damage'], 'range': published[0]['Range'],
            'attack_bonus': published[0].get('Attack bonus'), 'activation': published[0]['Activation'],
            'training': published[0].get('Category'), 'mastery': published[0].get('Mastery'),
        }
        if len(published) > 1 and all(row.get('Base weapon') for row in published):
            for column, label in (('damage', 'Damage'), ('range', 'Range'), ('mastery', 'Mastery')):
                fields[column] = ' / '.join(f"{row['Base weapon']}: {row.get(label, '')}" for row in published)
    elif kind == 'documented-reference':
        evidence = 'documented-reference'
        entries = [entry for entry in curated.get(item_id, [])
                   if entry.get('profile_kind') == kind and entry.get('status') == 'source-reported']
        required = ('Role', 'Tabletop use', 'Combat rules', 'Legacy source')
        provenance = item['provenance']
        source_reviewed = len(entries) == 1 and bool(provenance.get('locator')) and (
            entries[0].get('source') == provenance.get('source_url')
            and entries[0].get('source_locator') == provenance['locator']
        )
        if (len(entries) != 1 or not entries[0].get('source')
                or not all(entries[0].get('fields', {}).get(key) for key in required)
                or not (provenance.get('original_publication_verified') or source_reviewed)):
            errors.append('documented reference needs verified provenance and explicit tabletop use')
            gaps.append('verify the documented reference role')
    elif kind == 'custom-2024-draft':
        evidence = 'item-specific-draft'
        if len(custom) != 1 or not all(custom[0].get(key) for key in ('Damage', 'Range', 'Activation')):
            errors.append('custom 2024 draft needs one curated entry with damage, range and activation')
        else:
            fields = {
                'damage': custom[0]['Damage'], 'range': custom[0]['Range'], 'activation': custom[0]['Activation'],
                'attack_bonus': custom[0].get('Attack bonus'), 'training': custom[0].get('Category'),
                'mastery': custom[0].get('Mastery'),
            }
        gaps.append('item-specific draft requires DM review')
    elif plain_match:
        target_rules = target.get('mechanics') or {}
        if item['source_id'] != 'open5e-srd-2014' or item['magic'] is not False or target.get('magic') is not False:
            errors.append('invalid ordinary 2024 counterpart')
            gaps.append('verify the ordinary 2024 counterpart')
        elif plain_match['role'] == 'adventuring-gear' and name == 'Net':
            effect = next((row['fields'] for row in curated.get(target['id'], [])
                           if row.get('status') == 'published-reference'), {})
            if not all(effect.get(key) for key in ('Damage', 'Range', 'Activation')):
                errors.append('Net counterpart needs its published 2024 rules')
                gaps.append('verify the 2024 Net combat rules')
            else:
                evidence = 'verified-2024-adventuring-gear'
                fields.update(damage=effect['Damage'], range=effect['Range'], activation=effect['Activation'])
        elif plain_match['role'] == 'weapon' and target_rules.get('weapon'):
            evidence = 'verified-2024-ordinary-weapon'
            fields = structured_2024(target_rules['weapon'], target_rules.get('properties') or [], errors)
            fields['activation'] = 'Make an attack with the weapon'
        else:
            errors.append('ordinary 2024 counterpart is missing its weapon rules')
            gaps.append('verify the ordinary 2024 counterpart')
    elif item_id in enhancements:
        verified_base = all_items.get(verified.get('base_id'), {})
        base_mechanics = verified_base.get('mechanics') or {}
        target_mechanics = target.get('mechanics') or {}
        bonus = verified.get('bonus')
        if (item['source_id'] != 'open5e-srd-2014' or target.get('id') != verified.get('target_id')
                or verified_base.get('source_id') != 'open5e-srd-2024' or verified_base.get('magic') is not False
                or not base_mechanics.get('weapon') or target_mechanics.get('weapon') != base_mechanics['weapon']
                or type(bonus) is not int or bonus not in (1, 2, 3) or not name.endswith(f'(+{bonus})')):
            errors.append('invalid verified 2014 to 2024 weapon enhancement')
            gaps.append('verified enhancement needs a matching published variant and base')
        else:
            evidence = ('verified-2024-enhancement-with-base-note' if verified.get('base_note')
                        else 'verified-2024-enhancement')
            fields = structured_2024(base_mechanics['weapon'], base_mechanics.get('properties') or [], errors)
            fields['attack_bonus'] = f'+{bonus} to attack and damage'
            fields['activation'] = 'Apply to attacks made with the weapon'
    elif target:
        evidence = 'published-2024-cross-reference'
        target_mechanics = target.get('mechanics') or {}
        fields = source_fields(target_mechanics.get('weapon') or {}, target_mechanics.get('properties') or [])
        gaps.append('same-name published comparison requires item-specific review')
        if not fields.get('damage'):
            gaps.append('published cross-reference requires reading the rule text')
    elif kind == 'native-2024':
        if not source_weapon:
            errors.append('native 2024 profile has no weapon object')
        fields = structured_2024(source_weapon, properties, errors)
        if item.get('content_status') == 'original-conversion-draft':
            evidence = 'item-specific-draft'
            gaps.append('item-specific draft requires DM review')
        else:
            evidence = 'published-2024-structured'
    elif kind == 'source-2024-text':
        if not item.get('description'):
            errors.append('2024 text profile has no description')
        evidence = 'published-2024-text' if item['source_id'] == 'open5e-srd-2024' else 'item-specific-draft'
        gaps.append('2024 text requires reading the rule text')
    elif kind in BASE_PROFILE_KINDS:
        evidence = 'source-based-2024' if kind == 'source-based-2024' else 'base-weapon-draft'
        base_mechanics = base.get('mechanics') or {}
        if not base_mechanics.get('weapon'):
            errors.append('2024 base weapon has no weapon object')
        else:
            fields = source_fields(base_mechanics['weapon'], base_mechanics.get('properties') or [])
        fields['attack_bonus'] = profile.get('bonus')
        if kind == 'draft-2024-base':
            gaps.append('base-family comparison requires item-specific review')
            if item.get('magic') is True:
                gaps.append('magical item needs verified item-specific 2024 effects')
        elif type(profile.get('bonus')) is not int or not profile.get('source'):
            errors.append('source-based profile needs an integer bonus and a source')
    else:
        evidence = {
            'improvised-2024': 'improvised-fallback', 'launcher': 'launcher-dependent',
            'weapon-upgrade': 'upgrade-dependent', 'reference-object': 'reference-object',
        }.get(kind, 'unresolved')
        gaps.extend({
            'improvised-2024': ['weapon identity or 2024 adaptation unresolved'],
            'launcher': ['verify launcher compatibility and projectile effects'],
            'weapon-upgrade': ['verify eligible base weapons and upgrade mechanics'],
            'reference-object': ['review whether record belongs under weapons'],
            'siege-engine': ['siege attack needs damage, range and activation'],
        }.get(kind, []))
    if (item['source_id'] == 'open5e-srd-2024' and name.startswith(('Defender (', 'Flame Tongue '))
            and source_weapon and is_ranged_weapon(mechanics)):
        evidence = 'source-variant-conflict'
        gaps.append('published magic weapon family permits melee weapons only')
    price = prices.get(item_id) or {}
    errors.extend(price_errors(price))
    if not isinstance(item.get('provenance'), dict) or not item['provenance']:
        errors.append('weapon has no provenance object')
    return {
        'id': item_id, 'name': name, 'source_id': item['source_id'], 'ruleset': item['ruleset'],
        'tabletop_status': item.get('tabletop_status'), 'profile': kind, 'evidence': evidence,
        'native_evidence': native, **fields, **{key: price.get(key) for key in PRICE_FIELDS},
        'schema_errors': ' | '.join(dict.fromkeys(errors)), 'review_gaps': ' | '.join(dict.fromkeys(gaps)),
    }


def audit(catalog):
    database_uri = (catalog / 'indexes/items.sqlite3').resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(database_uri, uri=True) as database:
        items = {item['id']: item for item in map(json.loads, (
            raw for (raw,) in database.execute("SELECT data_json FROM items WHERE type='weapon'")
        ))}
    profiles = load(catalog, 'weapon-profiles-2024')['records']
    game = load(catalog, 'bg3-weapon-rules')
    curated = load(catalog, 'curated-item-details')['records']
    curated.update(load(catalog, 'published-2024-weapon-facts')['records'])
    if (catalog / 'supplements/core-magic-weapon-families.json').is_file():
        curated.update(load(catalog, 'core-magic-weapon-families')['records'])
    exact = load(catalog, 'dnd-2024-item-cross-references')['records']
    prices = load(catalog, 'item-prices')['records']
    legacy_game = load(catalog, 'legacy-game-weapon-facts')['records']
    for game_facts in ('diablo-2-base-weapon-facts', 'diablo-2-unique-weapon-facts'):
        if (catalog / 'supplements' / (game_facts + '.json')).is_file():
            legacy_game.update(load(catalog, game_facts)['records'])
    availability = load(catalog, 'bg3-weapon-availability')['records']
    enhancements = load(catalog, 'core-enhancement-cross-references') if (
        catalog / 'supplements/core-enhancement-cross-references.json').is_file() else {}
    rows = [
        audit_row(item, items, profiles, game, curated, exact, prices, legacy_game, availability, enhancements.get('records', {}), enhancements.get('plain', {}))
        for item in sorted(items.values(), key=lambda item: (item['source_id'], item['name'].casefold(), item['id']))
    ]
    orphaned = sorted(profiles.keys() - items.keys())
    return rows, orphaned


def write_reports(directory, rows, orphaned):
    with (directory / 'weapon-playability.csv').open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    evidence = collections.Counter(row['evidence'] for row in rows)
    source_gaps = collections.Counter(row['source_id'] for row in rows if row['review_gaps'])
    errors = [row for row in rows if row['schema_errors']]
    report = [
        '# Weapon playability audit', '',
        f'{len(rows):,} weapon records scanned. Structural errors affect {len(errors):,} records. '
        f'Content review is queued for {sum(source_gaps.values()):,} records.', '',
        'Scope is catalog records indexed with type weapon. Ammunition indexed separately has its own field audit. '
        'This scan checks weapon fields, profile references, BG3 variant structure, and positive prices. '
        'Full catalog schema validation is a separate check. '
        'Drafts, original game statistics, and base weapon comparisons retain their own evidence labels.',
        '', '## Rules evidence', '', '| Evidence | Records |', '|---|---:|',
        *(f'| {key} | {value:,} |' for key, value in evidence.most_common()),
        '', '## Largest review queues', '', '| Source | Records with a gap |', '|---|---:|',
        *(f'| {key} | {value:,} |' for key, value in source_gaps.most_common(15)),
        '', '## Structural errors', '',
        f'{len(orphaned):,} weapon profiles point to a missing or non-weapon catalog record.', '',
        *(f'- `{row["id"]}` — {row["schema_errors"]}' for row in errors[:30]),
        *(f'- Orphaned profile `{item_id}`' for item_id in orphaned[:30]),
        '', 'The [weapon playability CSV](weapon-playability.csv) contains each record and its evidence fields.',
        'A blank field can mean that the cited rules are prose-only, the field is inapplicable, or the information is unresolved.',
    ]
    (directory / 'WEAPON-PLAYABILITY.md').write_text('\n'.join(report) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-dir', type=Path, default=CATALOG)
    parser.add_argument('--strict', action='store_true', help='fail on structural errors; content-review gaps remain in the reports')
    args = parser.parse_args()
    rows, orphaned = audit(args.catalog_dir)
    write_reports(args.catalog_dir / 'reports', rows, orphaned)
    errors = sum(bool(row['schema_errors']) for row in rows)
    gaps = sum(bool(row['review_gaps']) for row in rows)
    print(f'{len(rows):,} weapons, {errors:,} with structural errors, {len(orphaned):,} orphaned profiles, {gaps:,} with review gaps.')
    return int(args.strict and bool(errors or orphaned))


if __name__ == '__main__':
    raise SystemExit(main())
