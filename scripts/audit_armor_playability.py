#!/usr/bin/env python3
"""Audit worn armor and shield records without inferring rules for missing entries."""
import argparse
import collections
import csv
import json
import re
import sqlite3
from pathlib import Path

from build_core_armor_cross_references import same_base
from audit_weapon_playability import CATALOG, PRICE_FIELDS, load, price_errors

TYPES = ('armor', 'shield')
FIELDS = (
    'id', 'name', 'source_id', 'ruleset', 'role', 'evidence', 'base_id', 'armor_class',
    'armor_class_bonus', 'enhancement_bonus', 'dexterity', 'training', 'strength_requirement', 'stealth_disadvantage',
    'weight', 'attunement', 'effects', *PRICE_FIELDS, 'schema_errors', 'review_gaps',
)
BG3_ROLES = {
    'Light Armour': 'light armor', 'Medium Armour': 'medium armor',
    'Heavy Armour': 'heavy armor', 'Shields': 'shield',
}
LEGACY_ARMOR_FIELDS = {
    'source_armor_class', 'source_ac', 'source_ac_adjustment', 'source_weight_adjustment',
    'source_armor_type', 'source_protection', 'source_strength_requirement',
}
PUBLISHED_SHIELDS = {
    'srd-2024_animated-shield', 'srd-2024_arrow-catching-shield',
    'srd-2024_shield-of-missile-attraction', 'srd-2024_spellguard-shield',
}


def joined(values):
    return ' / '.join(dict.fromkeys(str(value) for value in values if value not in ('', None)))


def ac_modifier(value):
    return re.fullmatch(r'[+-]?\d+', str(value or '')) is not None


def read_bg3(entry, effects, shield_training, errors, gaps):
    variants = entry.get('variants') or []
    if not variants:
        errors.append('BG3 armor record has no rule variants')
        return {}
    rows = collections.defaultdict(list)
    for number, variant in enumerate(variants, 1):
        stats = variant.get('stats') or {}
        role = BG3_ROLES.get(stats.get('type'))
        if not role:
            gaps.append(f'BG3 variant {number} has no recognized armor or shield category')
        rows['role'].append(role)
        ac = stats.get('armour class')
        bonus = stats.get('armour class bonus')
        value = bonus if role == 'shield' else ac
        if not value:
            gaps.append(f'BG3 variant {number} is missing {"shield AC bonus" if role == "shield" else "armor class"}')
        elif not ac_modifier(value):
            errors.append(f'BG3 variant {number} has malformed AC')
        rows['armor_class'].append(ac)
        rows['armor_class_bonus'].append(bonus)
        training = stats.get('proficiency')
        for effect in variant.get('effects') or []:
            exemption = effects.get(effect, {}).get('facts', {}).get('Training')
            if exemption:
                training = joined(exemption)
        if not training and role == 'shield' and shield_training.get('revision'):
            training = shield_training['label']
        rows['training'].append(training)
        if role and not training:
            gaps.append(f'BG3 variant {number} has no explicit training or exemption field')
        stealth = stats.get('stealth disadvantage')
        rows['stealth_disadvantage'].append(stealth)
        weight = stats.get('weight kg')
        rows['weight'].append(f'{weight} kg' if weight else None)
        for effect in variant.get('effects') or []:
            rows['effects'].append(effect)
            if effect not in effects:
                gaps.append(f'BG3 effect lacks a linked rule record: {effect}')
    return {key: joined(values) for key, values in rows.items()}


def read_armor(armor, *, modern, errors):
    ac = armor.get('ac_base')
    dexterity = armor.get('ac_add_dexmod')
    cap = armor.get('ac_cap_dexmod')
    stealth = armor.get('grants_stealth_disadvantage')
    strength = armor.get('strength_score_required')
    if type(ac) is not int or ac <= 0:
        errors.append('armor relation needs a positive integer AC')
    if type(dexterity) is not bool or (cap is not None and (type(cap) is not int or not dexterity)):
        errors.append('armor relation has an invalid Dexterity rule')
    if type(stealth) is not bool:
        errors.append('armor relation needs a boolean Stealth disadvantage field')
    if strength is not None and (type(strength) is not int or not 1 <= strength <= 30):
        errors.append('armor relation has an invalid Strength threshold')
    if armor.get('name', '').casefold() == 'shield':
        return {'role': 'shield', 'armor_class_bonus': f'+{ac}', 'training': 'Shield'}
    category = 'Light' if dexterity and cap is None else 'Medium' if dexterity else 'Heavy'
    return {
        'role': category.lower() + ' armor' if modern else 'worn armor',
        'armor_class': ac, 'training': category if modern else '',
        'dexterity': f'Dexterity modifier, maximum +{cap}' if dexterity and cap is not None
        else 'Dexterity modifier' if dexterity else 'No Dexterity modifier',
        'strength_requirement': strength if strength is not None else 'None',
        'stealth_disadvantage': 'Yes' if stealth else 'No',
    }


def audit_row(item, indexed, bg3, curated, prices, published, core, modern_families):
    errors, gaps = [], []
    item_id = item['id']
    mechanics = item.get('mechanics') or {}
    reference = mechanics.get('reference_metadata') or {}
    armor = mechanics.get('armor')
    role = 'shield' if item['type'] == 'shield' else 'worn armor'
    if item['provenance'].get('upstream_pk') in PUBLISHED_SHIELDS:
        role = 'shield'
    fields = {'role': role}
    price = prices.get(item_id, {})
    errors.extend(price_errors(price))
    evidence = 'reference-only'
    base_id = item.get('base_item_id')
    if base_id and not indexed.get(base_id, {}).get('mechanics', {}).get('armor'):
        errors.append('base armor ID does not resolve to structured armor')
    if not base_id and (source_base := (mechanics.get('source_fields') or {}).get('armor')):
        source_id = f"{item['source_id']}:{source_base}"
        if source_id in indexed and source_id != item_id:
            base_id = source_id
    mappings = [entry for entry in curated.get(item_id, [])
                if entry.get('profile_kind') in {'published-armor-mapping', 'published-public-armor',
                                                  'adapted-barding', 'adapted-game-armor', 'adapted-source-armor'}]
    encounter = [entry for entry in curated.get(item_id, [])
                 if entry.get('profile_kind') in {'armor-encounter-construct', 'documented-armor-accessory',
                                                  'adapted-protective-garment', 'adapted-protective-implement', 'adapted-partial-armor'}]
    if item['ruleset'] == 'bg3':
        evidence = 'native-bg3'
        fields.update(read_bg3(bg3['records'].get(item_id, {}), bg3['effects'], bg3['shield_training'], errors, gaps))
    elif properties := [entry for entry in curated.get(item_id, [])
                        if entry.get('profile_kind') == 'adapted-armor-property']:
        entry = properties[0]
        details = entry.get('fields', {})
        provenance = item['provenance']
        allowed_hosts = {'One shield'} if item['type'] == 'shield' else {
            'One suit of Light, Medium, or Heavy armor', 'One suit of Plate Armor',
            'One suit of Half Plate or Plate Armor',
        }
        if (len(properties) != 1 or mappings or encounter or entry.get('status') != 'original-draft'
                or entry.get('source') != provenance.get('source_url') or not provenance.get('locator')
                or details.get('Applies to') not in allowed_hosts
                or not all(details.get(key) for key in ('Source locator', 'Special powers', 'Armor class effect',
                                                        'Attunement', 'Conversion notes'))):
            errors.append('armor enchantment needs an applicable host, rules, and source')
        evidence = 'item-specific-armor-property-draft'
        fields = {'role': 'shield enchantment' if item['type'] == 'shield' else 'armor enchantment',
                  'attunement': details.get('Attunement'), 'effects': details.get('Special powers')}
        gaps.append('item-specific armor enchantment draft requires DM review')
    elif encounter:
        entry = encounter[0]
        details = entry.get('fields', {})
        provenance = item['provenance']
        profile = entry['profile_kind']
        partial = profile == 'adapted-partial-armor'
        protective = partial or profile in {'adapted-protective-garment', 'adapted-protective-implement'}
        construct = profile == 'armor-encounter-construct'
        effect_key = 'Creature defenses' if construct else 'Special powers'
        verified = entry.get('source') == provenance.get('source_url') and provenance.get('locator')
        if protective:
            verified = verified or any(ev.get('url') == entry.get('source') and ev.get('locator', {}).get('pdf_page')
                                       for ev in item.get('source_verifications', []))
        if (len(encounter) != 1 or entry.get('status') != ('original-draft' if protective else 'source-reported')
                or not verified
                or not all(details.get(key) for key in ('Source locator', effect_key, 'Use as armor'))):
            errors.append('armor reference needs source and explicit equipment applicability')
        if partial and not all(details.get(key) for key in (
                'Armor class', 'Training', 'Protection points', 'Weight and value', 'Conversion notes')):
            errors.append('partial armor needs a complete coverage and training formula')
        evidence = 'documented-armor-construct' if construct else profile
        role = {'armor-encounter-construct': 'encounter construct', 'documented-armor-accessory': 'armor accessory',
                'adapted-protective-garment': 'protective garment', 'adapted-protective-implement': 'protective implement',
                'adapted-partial-armor': 'partial armor kit'}
        fields = {'role': role[profile], 'effects': details.get(effect_key)}
        if partial:
            fields.update(armor_class=details.get('Armor class'), training=details.get('Training'))
        if protective:
            fields.update(attunement=details.get('Attunement'), weight=details.get('Weight'))
            gaps.append(f'item-specific {role[profile]} draft requires DM review')
    elif mappings:
        variants = []
        base_ids = []
        for mapping in mappings:
            base_id = mapping['related_item']['id']
            target = indexed.get(base_id, {})
            target_armor = target.get('mechanics', {}).get('armor')
            mapped_fields = mapping['fields']
            public = mapping['profile_kind'] == 'published-public-armor'
            game_adaptation = mapping['profile_kind'] == 'adapted-game-armor'
            source_adaptation = mapping['profile_kind'] == 'adapted-source-armor'
            adapted = game_adaptation or source_adaptation or mapping['profile_kind'] == 'adapted-barding'
            provenance = item['provenance']
            source_locator = mapped_fields.get('Source locator')
            reviewed_online_section = (
                provenance.get('evidence', {}).get('kind') == 'tsr-online-adaptation-preserved-on-mirror'
                and bool(source_locator)
                and bool(mapped_fields.get('Original item context'))
            )
            reviewed_book_index = (
                provenance.get('evidence', {}).get('kind') == 'secondary-book-name-index'
                and mapped_fields.get('Original item source', '').startswith('https://')
                and bool(mapped_fields.get('Original item context'))
            )
            original_page = (mapping.get('source') == provenance.get('source_url')
                             and bool(source_locator)
                             and (bool(provenance.get('locator')) or reviewed_online_section or reviewed_book_index))
            verified_source = (item['source_id'] == 'dndbeyond-public-index'
                               and mapping.get('source') == provenance.get('source_url')
                               and target.get('magic') is False) if public else (
                                   provenance.get('original_publication_verified') or original_page)
            if game_adaptation:
                native = [entry for entry in curated[item_id]
                          if entry.get('status') == 'source-reported' and entry.get('source') == mapping.get('source')]
                verified_source = (mapping.get('source') == provenance.get('source_url')
                                   and provenance.get('evidence', {}).get('kind') in {
                                       'official-base-item-table', 'official-unique-name-index'}
                                   and bool(mapped_fields.get('Source locator'))
                                   and len(native) == 1
                                   and bool(native[0]['fields'].get('Defense (game)'))
                                   and bool(target_armor)
                                   and (item['type'] == 'shield') == (target_armor.get('name') == 'Shield'))
            enhancement = re.search(r' \(\+([1-3])\)$', target.get('name', '')) if target.get('magic') else None
            family = modern_families.get(base_id) if mapping['profile_kind'] == 'published-armor-mapping' else None
            bonus = int(enhancement[1]) if enhancement else 0
            if public or source_adaptation:
                bonus = mapping.get('enhancement_bonus', bonus)
            if family:
                bonus = family.get('bonus', 0)
            expected_status = 'original-draft' if adapted else 'published-reference'
            if (mapping['status'] != expected_status or not mapping.get('source')
                    or target.get('source_id') != 'open5e-srd-2024' or not target_armor
                    or not verified_source or type(bonus) is not int or not 0 <= bonus <= 3
                    or (family and (mapped_fields.get('Special powers') != family['effect']
                                    or not mapped_fields.get('2024 counterpart', '').startswith(family['source'] + '#')))
                    or (adapted and not mapped_fields.get('Conversion notes'))
                    or (mapping['profile_kind'] == 'adapted-barding' and not mapping.get('barding'))):
                errors.append('invalid armor mapping or adaptation')
            else:
                if game_adaptation:
                    evidence = 'item-specific-game-armor-draft'
                    gaps.append('item-specific game armor draft requires DM review')
                elif source_adaptation:
                    evidence = 'item-specific-source-armor-draft'
                    gaps.append('item-specific source armor draft requires DM review')
                elif adapted:
                    evidence = 'item-specific-barding-draft'
                    gaps.append('item-specific barding draft requires DM review')
                else:
                    evidence = 'verified-2024-armor-mapping'
                fields = read_armor(target_armor, modern=True, errors=errors)
                if bonus:
                    fields['enhancement_bonus'] = f'+{bonus}'
                if fields['role'] == 'shield':
                    valid_ac = mapped_fields.get('Armor class bonus') == f"+{target_armor['ac_base'] + bonus}"
                else:
                    adjustment = mapping.get('armor_class_adjustment', 0)
                    if type(adjustment) is not int or (adjustment and (
                            not source_adaptation or bonus or not -4 <= adjustment <= -1)):
                        errors.append('invalid armor material AC adjustment')
                        adjustment = 0
                    fields['armor_class'] += adjustment
                    formula = str(fields['armor_class'] + bonus)
                    cap = target_armor['ac_cap_dexmod']
                    override = mapping.get('dexterity_cap_override')
                    if override is not None:
                        if not source_adaptation or type(override) is not int or not 1 <= override <= 5:
                            errors.append('invalid source armor Dexterity cap override')
                        else:
                            cap = override
                            fields['dexterity'] = f'Dexterity modifier, maximum +{cap}'
                    if target_armor['ac_add_dexmod'] or cap:
                        formula += ' + Dex modifier'
                        if cap and not (public and mapping.get('uncapped_dexterity')):
                            formula += f' (max +{cap})'
                    valid_ac = mapped_fields.get('Armor class') == formula
                if not valid_ac:
                    errors.append('mapped armor class disagrees with published equipment')
                if family and family.get('training'):
                    fields['training'] = family['training']
                if mapping.get('mithral') or (family and family.get('mithral')):
                    fields.update(strength_requirement='None', stealth_disadvantage='No')
                if public and mapping.get('uncapped_dexterity'):
                    fields['dexterity'] = 'Full Dexterity modifier'
                if public and mapping.get('stealth_exception'):
                    fields['stealth_disadvantage'] = 'No'
                fields['effects'] = mapped_fields['Special powers']
                if game_adaptation or source_adaptation:
                    fields['weight'] = mapped_fields['Weight']
                    if fields['role'] != 'shield' and mapped_fields['Strength requirement'].rstrip('.') == 'None':
                        fields['strength_requirement'] = 'None'
                    if source_adaptation and fields['role'] != 'shield':
                        fields['stealth_disadvantage'] = mapped_fields['Stealth disadvantage']
                if mapping.get('barding'):
                    weight = mapped_fields.get('Weight', '')
                    if (target_armor.get('name') == 'Shield'
                            or not re.fullmatch(r'[1-9]\d*(?:\.\d+)? lb', weight)):
                        errors.append('barding needs a worn armor base and a positive weight')
                    fields.update(role='barding', weight=weight)
                    if mapped_fields.get('Strength requirement', '').rstrip('.') == 'None':
                        fields['strength_requirement'] = 'None'
                    if mapped_fields.get('Stealth disadvantage') in ('Yes', 'No'):
                        fields['stealth_disadvantage'] = mapped_fields['Stealth disadvantage']
                attuned_item = item if public else target
                fields['attunement'] = 'Required' if attuned_item['requires_attunement'] else 'No'
                if game_adaptation or source_adaptation:
                    fields['attunement'] = mapped_fields['Attunement'].rstrip('.')
                variants.append(fields)
                base_ids.append(base_id)
        if len(variants) > 1:
            fields = {key: joined(row.get(key) for row in variants)
                      for key in dict.fromkeys(key for row in variants for key in row)}
        base_id = joined(base_ids)
    elif item_id in core:
        profile = core[item_id]
        target = indexed.get(profile['target_id'], {})
        target_armor = target.get('mechanics', {}).get('armor')
        if (item['source_id'] != 'open5e-srd-2014' or target.get('source_id') != 'open5e-srd-2024'
                or not target_armor
                or (not same_base(item, target) and not (
                    profile.get('change') and target['id'] in published and item['name'] == target['name']
                ))):
            errors.append('invalid verified armor counterpart')
            gaps.append('verify the published 2024 armor link')
        else:
            evidence = 'verified-2024-armor-counterpart'
            base_id = target['id']
            fields.update(read_armor(target_armor, modern=True, errors=errors))
            if profile['mithral']:
                fields.update(strength_requirement='None', stealth_disadvantage='No')
            if profile.get('training'):
                fields['training'] = profile['training']
            if profile.get('bonus'):
                fields['enhancement_bonus'] = f'+{profile["bonus"]}'
            if profile['effect']:
                fields['effects'] = profile['effect']
    elif item_id in published:
        profile = published[item_id]
        base_id = profile['base_id']
        base = indexed.get(base_id, {})
        base_armor = base.get('mechanics', {}).get('armor')
        if (item['source_id'] != 'open5e-srd-2024' or base.get('source_id') != 'open5e-srd-2024'
                or base.get('magic') is not False or not base_armor or not profile.get('effects')
                or type(profile.get('bonus')) is not int):
            errors.append('invalid published armor base or rules reference')
        else:
            evidence = 'published-2024-reference'
            fields.update(read_armor(base_armor, modern=True, errors=errors))
            if profile['bonus']:
                fields['enhancement_bonus'] = f'+{profile["bonus"]}'
            fields['effects'] = profile['effects']
    elif armor and 'base_ac' in armor and 'ac_base' not in armor:
        evidence = 'third-party-armor-fields'
        category = armor.get('category', '')
        fields['role'] = 'shield' if category == 'Shield' else fields['role']
        fields['training'] = category
        if category != 'Shield':
            fields['armor_class'] = armor['base_ac']
        gaps.append('third-party source format needs AC formula and 2024 rules review')
    elif armor:
        evidence = 'published-2024-structured' if item['source_id'] == 'open5e-srd-2024' else 'native-armor-structured'
        fields.update(read_armor(armor, modern=armor.get('document') in {'srd-2024', 'srd-2014'}, errors=errors))
        if item['ruleset'] != 'dnd-2024':
            gaps.append('2024 item-specific armor rules require review')
        elif item['source_id'] != 'open5e-srd-2024':
            evidence = 'item-specific-draft'
            gaps.append('item-specific armor draft requires DM review')
        if item['source_id'] == 'open5e-srd-2024':
            match = re.search(r' \(\+([123])\)$', item['name'])
            description = item.get('description') or ''
            if match and 'bonus to Armor Class' in description and 'rarity' in description:
                bonus = int(match[1])
                rarities = ('uncommon', 'rare', 'very rare') if fields['role'] == 'shield' else ('rare', 'very rare', 'legendary')
                rarity = rarities[bonus - 1]
                if (item.get('rarity') or '').replace('-', ' ') != rarity:
                    errors.append('published armor enhancement and rarity disagree')
                fields['enhancement_bonus'] = f'+{bonus}'
        family = modern_families.get(item_id)
        if family:
            fields['effects'] = family['effect']
            if family.get('bonus'):
                fields['enhancement_bonus'] = f'+{family["bonus"]}'
            if family.get('training'):
                fields['training'] = family['training']
            if family['mithral']:
                fields.update(strength_requirement='None', stealth_disadvantage='No')
        if item['magic'] and not item.get('description'):
            gaps.append('magic armor is missing its item-specific effects')
    elif base_id and item['ruleset'] == 'dnd-2024':
        base_armor = indexed.get(base_id, {}).get('mechanics', {}).get('armor')
        if base_armor:
            evidence = 'item-specific-draft'
            fields.update(read_armor(base_armor, modern=True, errors=errors))
            gaps.append('item-specific armor draft requires DM review')
        else:
            gaps.append('2024 armor draft needs its referenced base rules')
    elif item['source_id'] == 'open5e-srd-2024' and item.get('description'):
        evidence = 'published-2024-text'
        gaps.append('published rules present; structured base armor or shield relation missing')
    elif LEGACY_ARMOR_FIELDS.intersection(reference):
        evidence = 'legacy-armor-metadata'
        gaps.append('legacy armor facts need an item-specific 2024 profile')
    else:
        gaps.append('armor class or shield bonus and item-specific rules require source review')
    attunement = indexed.get(core.get(item_id, {}).get('target_id'), item).get('requires_attunement')
    if attunement is not None and 'attunement' not in fields:
        fields['attunement'] = 'Required' if attunement else 'No'
    weight = (mechanics.get('source_fields') or {}).get('weight')
    if re.fullmatch(r'\d+(?:\.\d+)?', str(weight)) and float(weight) > 0:
        fields['weight'] = f'{float(weight):g} lb'
    if item.get('description') and item.get('magic') and item['ruleset'] != 'bg3':
        fields.setdefault('effects', 'Source description')
    if curated.get(item_id):
        evidence += ' + curated detail'
    return {
        'id': item_id, 'name': item['name'], 'source_id': item['source_id'],
        'ruleset': item['ruleset'], 'evidence': evidence, 'base_id': base_id,
        **fields, **{key: price.get(key) for key in PRICE_FIELDS},
        'schema_errors': ' | '.join(dict.fromkeys(errors)),
        'review_gaps': ' | '.join(dict.fromkeys(gaps)),
    }


def write_reports(catalog, rows):
    directory = catalog / 'reports'
    with (directory / 'armor-playability.csv').open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    pending = [row for row in rows if row['review_gaps']]
    errors = [row for row in rows if row['schema_errors']]
    evidence = collections.Counter(row['evidence'] for row in rows)
    by_source = collections.Counter(row['source_id'] for row in pending)
    lines = [
        '# Armor and shield playability audit', '',
        f'{len(rows):,} armor and shield records scanned. Structural errors affect {len(errors):,} records. Content review is queued for {len(pending):,} records.',
        '', 'Scope includes records indexed as armor or shield. Helmets, clothing, and other accessories indexed separately are outside this scan. Shield bonuses and worn armor AC occupy separate fields. Native game and legacy evidence remain distinct from 2024 tabletop rules.',
        '', '| Evidence | Records |', '|---|---:|',
        *(f'| {label} | {count:,} |' for label, count in evidence.most_common()),
        '', '| Largest open sources | Records |', '|---|---:|',
        *(f'| {label} | {count:,} |' for label, count in by_source.most_common(15)),
        '', '## Structural errors', '',
        *(f'- `{row["id"]}` — {row["schema_errors"]}' for row in errors[:30]),
        '', 'The [armor playability CSV](armor-playability.csv) includes rule evidence and per-record gaps.',
    ]
    (directory / 'ARMOR-PLAYABILITY.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return len(errors), len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-dir', type=Path, default=CATALOG)
    parser.add_argument('--strict', action='store_true', help='fail on structural errors')
    args = parser.parse_args()
    catalog = args.catalog_dir
    uri = (catalog / 'indexes/items.sqlite3').resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as database:
        items = [json.loads(raw) for (raw,) in database.execute(
            'SELECT data_json FROM items WHERE type IN (?, ?) ORDER BY source_id, name, id', TYPES
        )]
    indexed = {item['id']: item for item in items}
    bg3 = load(catalog, 'bg3-item-rules')
    armor_rules = load(catalog, 'bg3-armor-effects')
    bg3['effects'].update(armor_rules['effects'])
    bg3['shield_training'] = armor_rules['shield_training']
    curated = load(catalog, 'curated-item-details')['records']
    curated.update(load(catalog, 'diablo-2-base-armor-facts')['records'])
    curated.update(load(catalog, 'diablo-2-unique-armor-facts')['records'])
    prices = load(catalog, 'item-prices')['records']
    published = load(catalog, 'published-2024-armor-facts')['records']
    core_path = catalog / 'supplements/core-armor-cross-references.json'
    core = load(catalog, 'core-armor-cross-references') if core_path.is_file() else {}
    curated.update(core.get('public', {}))
    rows = [audit_row(item, indexed, bg3, curated, prices, published, core.get('records', {}), core.get('modern', {})) for item in items]
    errors, pending = write_reports(catalog, rows)
    print(f'{len(rows):,} armor and shield records, {errors:,} structural errors, {pending:,} review gaps.')
    return int(args.strict and bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
