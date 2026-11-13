#!/usr/bin/env python3
"""Join combat audits and flag common catalog mistakes in alphabetic slices."""
import argparse
import csv
import json
import re
import sqlite3
import string
import sys
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path

from audit_pending_rules import marker_fields

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
COMBAT = {'weapon', 'armor', 'shield', 'ammunition'}
AMMO_NAME = re.compile(r'\b(?:arrows|bolts|bullets|ammunition)\b', re.I)
WEAPON_NAME = re.compile(r"\b(?:dagger|sword|greatsword|longbow|crossbow|spear|halberd)\b", re.I)
ACCESSORY = re.compile(r'\b(?:recipe|blueprint|schematic|case|rack|quiver|mould|mold|stand|strap)\b', re.I)


def read_index(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return {row['id']: row for row in csv.DictReader(stream)}


def first_letter(name):
    return unicodedata.normalize('NFKD', name.lstrip())[0:1].upper()


def common_findings(item, weapon, price, native):
    name, kind = item['name'], item['type']
    findings = []
    if (kind != 'shield' and re.search(r'\bshield\b', name, re.I) and not ACCESSORY.search(name)
            and not re.search(r'\b(?:spell|scroll|emblem)\b', name, re.I)):
        findings.append('classification: check shield')
    if kind != 'ammunition' and AMMO_NAME.search(name) and not ACCESSORY.search(name):
        findings.append('classification: check ammunition')
    if kind not in COMBAT and WEAPON_NAME.search(name) and not ACCESSORY.search(name):
        findings.append('classification: check weapon or equipment component')
    if kind in {'armor', 'shield'} and re.search(r'\b(?:saddle|barding|mojo)\b', name, re.I):
        findings.append('classification: check mount equipment or focus')
    if item['source_id'] == 'diablo-3-reference':
        source_type = item['mechanics'].get('source_type', '').casefold()
        expected_type = {'mojo': 'spellcasting-focus', 'source': 'spellcasting-focus',
                         'phylactery': 'spellcasting-focus', 'quiver': 'container'}.get(source_type)
        if expected_type and kind != expected_type:
            findings.append(f'classification: Diablo III {source_type} belongs under {expected_type}')
    if weapon.get('mastery') == 'Sap' and any(
        'One-handed damage (Barbarian only)' in variant['fields']
        and 'Two-handed damage' in variant['fields'] for variant in native.get('variants', [])
    ):
        findings.append('handedness: compare source two-handed sword to Greatsword')
    price_is_mundane_estimate = price.get('method') in {'category', 'equipment-analogue', 'base-item'}
    magic_evidence = (
        item.get('magic') is True
        or item.get('rarity') in {'uncommon', 'rare', 'very-rare', 'legendary'}
        or re.search(r'(?<!\w)\+[123]\b', name)
        or re.search(r'(?:plus |\+)[123]\b', weapon.get('attack_bonus', ''), re.I)
    )
    if kind in COMBAT - {'ammunition'} and price_is_mundane_estimate and magic_evidence:
        if Decimal(price['base_cost_gp']) < 400:
            findings.append('price: verify magic appraisal below uncommon benchmark')
    return findings


PLACEHOLDER = re.compile(
    r'legacy pending|2024 compatibility or adaptation is pending|'
    r'(?:the )?catalog has a reference for this entry|provisional profile|'
    r'(?:gameplay|combat|item|tabletop) rules (?:are |remain )?pending',
    re.I,
)
NON_ATTACK_EVIDENCE = {'documented-reference', 'reference-object', 'launcher-dependent',
                       'upgrade-dependent', 'verified-2024-adventuring-gear'}


def rule_findings(item, weapon, armor, details, curated):
    findings = []
    if item['type'] not in COMBAT:
        return findings
    evidence = weapon.get('evidence') or armor.get('evidence')
    presentation = item.get('presentation') or {}
    pending = marker_fields(item)
    pending.extend(
        f'presentation.{field}' for field in ('tldr', 'details')
        if PLACEHOLDER.search(presentation.get(field) or '')
    )
    if pending:
        findings.append('placeholder text: ' + ', '.join(pending))
    if evidence == 'improvised-fallback':
        findings.append('provisional rules: verify item identity and attack against source')
    if weapon and evidence not in NON_ATTACK_EVIDENCE:
        missing = [field for field in ('damage', 'range') if not weapon.get(field)]
        if missing:
            findings.append('weapon fields: missing ' + ', '.join(missing))
    role = armor.get('role')
    if role in {'worn armor', 'shield'}:
        ac_field = 'armor_class_bonus' if role == 'shield' else 'armor_class'
        if not armor.get(ac_field):
            findings.append('armor fields: missing ' + ac_field.replace('_', ' '))
    if item.get('magic') is True and (weapon or armor) and evidence in {
        'base-weapon-draft', 'improvised-fallback', 'reference-only',
    }:
        effect_labels = {'Special powers', 'Effects', 'Attack bonus', 'Armor class bonus'}
        has_curated_rule = any(
            entry.get('fields', {}).keys() & effect_labels
            for entry in curated
        )
        if not (armor.get('effects') or armor.get('enhancement_bonus') or weapon.get('attack_bonus')
                or has_curated_rule or details.get('special_powers') in {'source-field', 'draft', '2024-guideline'}):
            findings.append('magic rules: verify enhancement or item-specific effect')
    return findings


def bg3_effect_findings(record, effects, curated, reviewed):
    if any(entry.get('status') == 'source-reported' for entry in curated):
        return []
    titles = {title for variant in record.get('variants', []) for title in variant.get('effects', [])}
    findings = []
    for index, variant in enumerate(record.get('variants', []), 1):
        facts = {**variant.get('facts', {}), **reviewed}
        if variant.get('stats', {}).get('type') == 'Coatings' and not facts.get('Special powers'):
            findings.append(f'BG3 coating: variant {index} needs an explicit playable effect')
    for title in sorted(titles):
        effect = effects.get(title)
        if not effect:
            findings.append(f'BG3 effect: source link only for {title}')
        elif not any(effect.get('facts', {}).values()) and not (
            effect.get('stats', {}).keys() - {'type', 'cost', 'recharge', 'level'}
        ):
            findings.append(f'BG3 effect: no mechanic recorded for {title}')
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='Z', type=str.upper, choices=string.ascii_uppercase)
    parser.add_argument('--end', type=str.upper, choices=string.ascii_uppercase)
    parser.add_argument('--catalog-dir', type=Path, default=CATALOG)
    args = parser.parse_args()
    end = args.end or args.start
    if end > args.start:
        parser.error('--end must be at or before --start in reverse alphabetic order')
    catalog = args.catalog_dir
    reports = catalog / 'reports'
    weapons = read_index(reports / 'weapon-playability.csv')
    armor = read_index(reports / 'armor-playability.csv')
    ammo = read_index(reports / 'ammunition-rule-gaps.csv')
    details = read_index(reports / 'item-detail-audit.csv')
    prices = json.loads((catalog / 'supplements/item-prices.json').read_text())['records']
    native = json.loads((catalog / 'supplements/diablo-2-base-weapon-facts.json').read_text())['records']
    curated = json.loads((catalog / 'supplements/curated-item-details.json').read_text())['records']
    bg3 = json.loads((catalog / 'supplements/bg3-item-rules.json').read_text())
    bg3_armor = json.loads((catalog / 'supplements/bg3-armor-effects.json').read_text())
    bg3_effects = {**bg3['effects'], **bg3_armor['effects']}
    counts = Counter()
    writer = csv.writer(sys.stdout)
    writer.writerow(('letter', 'id', 'name', 'type', 'source_id', 'source_url', 'source_locator',
                     'combat_audit', 'findings'))
    with sqlite3.connect((catalog / 'indexes/items.sqlite3').resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT data_json FROM items ORDER BY name COLLATE NOCASE, id')
        items = [json.loads(row[0]) for row in rows]
        items.sort(key=lambda item: first_letter(item['name']), reverse=True)
        for item in items:
            letter = first_letter(item['name'])
            if not end <= letter <= args.start:
                continue
            item_id, kind = item['id'], item['type']
            weapon, protection = weapons.get(item_id, {}), armor.get(item_id, {})
            findings = common_findings(item, weapon, prices.get(item_id, {}), native.get(item_id, {}))
            findings.extend(rule_findings(item, weapon, protection, details.get(item_id, {}),
                                         curated.get(item_id, [])))
            findings.extend(bg3_effect_findings(bg3['records'].get(item_id, {}), bg3_effects,
                                               curated.get(item_id, []),
                                               bg3_armor['reviewed_item_facts'].get(item_id, {})))
            for report in (weapon, protection):
                findings.extend(report[key] for key in ('schema_errors', 'review_gaps') if report.get(key))
            if item_id in ammo:
                findings.append('ammunition fields: ' + ammo[item_id]['fields_without_structured_rules'])
            if kind in COMBAT:
                counts[letter, 'combat'] += 1
                expected_report = {'weapon': weapon, 'armor': protection, 'shield': protection,
                                   'ammunition': details.get(item_id)}
                if not expected_report[kind]:
                    findings.append('coverage: combat record missing from expected audit')
            provenance = item['provenance']
            writer.writerow((letter, item_id, item['name'], kind, item['source_id'],
                             provenance.get('source_url'), provenance.get('locator'),
                             weapon.get('evidence') or protection.get('evidence') or ('ammunition' if kind == 'ammunition' else ''),
                             ' | '.join(findings)))
            counts[letter, 'total'] += 1
            counts[letter, 'flagged'] += bool(findings)
    for letter in reversed(string.ascii_uppercase):
        if end <= letter <= args.start:
            print(f"{letter}: {counts[letter, 'total']} entries, {counts[letter, 'combat']} combat, "
                  f"{counts[letter, 'flagged']} flagged", file=sys.stderr)


if __name__ == '__main__':
    main()
