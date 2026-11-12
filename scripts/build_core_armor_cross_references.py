#!/usr/bin/env python3
"""Link verified legacy SRD armor families to their playable 2024 counterparts."""
import collections
import json
import re
import sqlite3
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
LEGACY = 'open5e-srd-2014'
CURRENT = 'open5e-srd-2024'
MAGIC = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z'
EQUIPMENT = 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment#Armor'
FAMILIES = {
    'Adamantine Armor': (
        'any critical hit against you becomes a normal hit',
        'Critical hits against you become normal hits while worn.',
    ),
    'Armor of Resistance': (
        'resistance to one type of damage while you wear this armor',
        'While worn, resist the damage type chosen or rolled by the DM.',
    ),
    'Mithral Armor': (
        'stealth',
        'Removes the base armor’s Strength minimum and Stealth disadvantage. It can be worn under normal clothes in the 2024 rules.',
    ),
}
REVIEWED_VARIANTS = {
    'Animated Shield': 'The 2024 activation uses a Bonus Action without a command word.',
    'Armor of Invulnerability': 'The 2024 resistance and temporary immunity cover Bludgeoning, Piercing, and Slashing damage.',
    'Arrow-Catching Shield': 'The 2024 bonus and interception apply to ranged attack rolls.',
    'Dragon Scale Mail': 'The 2024 saving throw advantage applies to dragon breath weapons. Locating a dragon uses a Magic action.',
    'Glamoured Studded Leather': 'The 2024 appearance change uses a Bonus Action without a command word.',
    'Shield of Missile Attraction': 'The 2024 curse redirects attacks made with Ranged weapons.',
    'Spellguard Shield': 'The 2024 protection applies to saves against spells and other magical effects, and to incoming spell attack rolls.',
}
REVIEWED_STRUCTURED = {
    'Dwarven Plate': (2, 'Use a Reaction to reduce forced movement along the ground by up to 10 ft.', ''),
    'Elven Chain Mail': (1, 'The wearer is treated as trained with this armor.', 'Wearer counts as trained'),
    'Elven Chain Shirt': (1, 'The wearer is treated as trained with this armor.', 'Wearer counts as trained'),
    'Plate Armor of Etherealness': (0, 'Once per dawn, use a Magic action and the command word for Etherealness. Removing the armor or repeating the command word as a Magic action ends the effect.', ''),
}
CURSED_FAMILIES = (
    ('Armor of Vulnerability (', 'while cursed, you have vulnerability', 0,
     'While worn, resist one DM-selected type among Bludgeoning, Piercing, and Slashing. Attunement curses you with vulnerability to the other two. Identify or attunement reveals the curse. Remove Curse or similar magic ends it; doffing alone leaves it in effect.'),
    ('Demon ', 'clawed gauntlets', 1,
     'While worn, you know Abyssal. Your Unarmed Strikes can deal 1d8 Slashing in place of their normal damage and gain +1 to attack and damage. After donning, Remove Curse or similar magic is needed to doff the armor. While wearing it, you have Disadvantage on attacks against demons and saves against their spells and special abilities.'),
)
STRUCTURED_LEGACY = {
    'Armor of Vulnerability': ('Armor of Vulnerability (Plate Armor)', 'Plate Armor matches this legacy entry. The 2024 item is also available on other Light, Medium, or Heavy bases.'),
    'Demon Armor': ('Demon Plate Armor', 'Plate Armor matches this legacy entry. The 2024 gauntlets modify Unarmed Strikes.'),
    'Dwarven Plate': ('Dwarven Plate', ''),
    'Elven Chain': ('Elven Chain Shirt', 'The Chain Shirt is the matching base for this 2014 entry. The 2024 rules also publish a separate Chain Mail variant.'),
    'Plate Armor of Etherealness': ('Plate Armor of Etherealness', 'The 2024 entry uses the Etherealness spell duration and activates with a Magic action.'),
}
ARMOR_FIELDS = ('ac_base', 'ac_add_dexmod', 'ac_cap_dexmod',
                'grants_stealth_disadvantage', 'strength_score_required')


def key(name):
    name = re.sub(r'[^a-z0-9]+', ' ', name.casefold()).strip()
    return re.sub(r'\b(padded|leather|studded leather|hide|half plate|plate|splint) armor\b', r'\1', name)


def same_base(left, right):
    a = left['mechanics'].get('armor') or {}
    b = right['mechanics'].get('armor') or {}
    if a and b:
        return (key(a['name']) == key(b['name'])
                and all(a[field] == b[field] for field in ARMOR_FIELDS))
    return (not a and left['name'] == right['name'] == 'Shield' and b.get('ac_base') == 2
            and 'increases your Armor Class by 2' in left['description'])


LEGACY_ARMOR_ENHANCEMENTS = {'dndbeyond:5377': 1, 'dndbeyond:5378': 2, 'dndbeyond:5379': 3}

PUBLIC_ARMOR_RULES = {
    **dict.fromkeys(LEGACY_ARMOR_ENHANCEMENTS, MAGIC + '#Armor12or3'),
    'dndbeyond:5370': MAGIC + '#AdamantineArmor',
    'dndbeyond:5371': MAGIC + '#ArmorofResistance',
    'dndbeyond:5376': MAGIC + '#ArmorofVulnerability',
    'dndbeyond:5381': MAGIC + '#MithralArmor',
    'dndbeyond:9228349': 'https://roll20.net/compendium/dnd5e/Templates%3AArmor%20of%20Gleaming?expansion=33359',
    'dndbeyond:9228382': 'https://roll20.net/compendium/dnd5e/Templates%3ACast-Off%20Armor?expansion=33359',
    'dndbeyond:9228451': MAGIC + '#DemonArmor',
    'dndbeyond:9228541': 'https://roll20.net/compendium/dnd5e/Templates%3AEnspelled%20Armor?expansion=33359',
    'dndbeyond:9228837': 'https://roll20.net/compendium/dnd5e/Templates%3AMariner%27s%20Armor?expansion=33359',
}

METAL_ARMOR_FAMILIES = {'Adamantine Armor', 'Mithral Armor'}

PUBLIC_ARMOR = {
    **{
        item_id: (
            f'Armor, +{bonus}', f"{item_id.split(':')[1]}-armor-{bonus}",
            bonus, False, ('Rare', 'Very Rare', 'Legendary')[bonus - 1],
            {'Special powers': f'While wearing the armor, add +{bonus} to the base suit’s Armor Class.'},
        )
        for item_id, bonus in LEGACY_ARMOR_ENHANCEMENTS.items()
    },
    'dndbeyond:5370': (
        'Adamantine Armor', '5370-adamantine-armor', 0, False, 'Uncommon', {
            'Special powers': 'While wearing the armor, a Critical Hit against you becomes a normal hit.',
        },
    ),
    'dndbeyond:5371': (
        'Armor of Resistance', '5371-armor-of-resistance', 0, True, 'Rare', {
            'Special powers': 'While wearing the armor, resist the damage type selected for this suit.',
            'Damage type': 'Choose or roll d10: 1 Acid, 2 Cold, 3 Fire, 4 Force, 5 Lightning, 6 Necrotic, 7 Poison, 8 Psychic, 9 Radiant, 10 Thunder.',
        },
    ),
    'dndbeyond:5376': (
        'Armor of Vulnerability', '5376-armor-of-vulnerability', 0, True, 'Rare', {
            'Special powers': 'While wearing the armor, resist one damage type chosen by the DM: Bludgeoning, Piercing, or Slashing.',
            'Curse': 'Identify or attunement reveals the curse. Attuning gives you Vulnerability to the other two types. Taking off the armor leaves the curse in effect. Remove Curse or similar magic ends it.',
        },
    ),
    'dndbeyond:5381': (
        'Mithral Armor', '5381-mithral-armor', 0, False, 'Uncommon', {
            'Special powers': 'The armor can be worn under ordinary clothes. Mithral removes the base suit’s Strength requirement and Stealth disadvantage.',
        },
    ),
    'dndbeyond:9228349': (
        'Armor of Gleaming', '9228349-armor-of-gleaming', 0, False, 'Common', {
            'Special powers': 'The armor never gets dirty. Use the base suit’s normal AC, training, and donning rules.',
        },
    ),
    'dndbeyond:9228382': (
        'Cast-Off Armor', '9228382-cast-off-armor', 0, False, 'Common', {
            'Special powers': 'While wearing the armor, take a Magic action to doff it. Use the base suit’s normal donning time.',
        },
    ),
    'dndbeyond:9228451': (
        'Demon Armor', '9228451-demon-armor', 1, True, 'Very Rare', {
            'Special powers': 'While worn, you know Abyssal. The clawed gauntlets let your Unarmed Strikes deal 1d8 Slashing and grant +1 to their attack and damage rolls.',
            'Curse': 'You cannot doff the armor until affected by Remove Curse or similar magic. While wearing it, you have Disadvantage on attacks against demons and on saves against their spells and abilities.',
        },
    ),
    'dndbeyond:9228837': (
        "Mariner's Armor", '9228837-mariners-armor', 0, False, 'Uncommon', {
            'Special powers': 'While worn, gain a Swim Speed equal to your Speed. If you start your turn underwater at 0 HP, immediately regain 1d4 HP. The healing recharges at dawn.',
        },
    ),
    'dndbeyond:9228541': (
        'Enspelled Armor', '9228541-enspelled-armor', 0, True, 'Varies by spell level', {
            'Special powers': 'Choose one Abjuration or Illusion spell from cantrip through level 8 when the armor is created. While wearing the armor, spend 1 charge to cast the bound spell. Use that spell’s casting time, range, and Concentration rules.',
            'Charges': '6 charges. Regain 1d6 spent charges at dawn.',
            'Rarity, save DC, spell attack': 'Cantrip or 1: Uncommon, DC 13, +5. 2: Rare, DC 13, +5. 3: Rare, DC 15, +7. 4: Very Rare, DC 15, +7. 5: Very Rare, DC 17, +9. 6: Legendary, DC 17, +9. 7–8: Legendary, DC 18, +10.',
        },
    ),
}


def public_armor_variants(items):
    bases = [item for item in items if item['source_id'] == CURRENT and item['magic'] is False
             and item['mechanics'].get('armor') and item['mechanics']['armor']['name'] != 'Shield']
    records = {}
    for item in items:
        if item['source_id'] != 'dndbeyond-public-index' or item['id'] not in PUBLIC_ARMOR:
            continue
        name, page, bonus, attune, rarity, effects = PUBLIC_ARMOR[item['id']]
        source = 'https://www.dndbeyond.com/magic-items/' + page
        if (item['name'] != name or item['provenance'].get('source_url') != source
                or item['requires_attunement'] is not attune):
            raise ValueError(f'Public armor identity mismatch: {item["id"]}')
        variants = []
        for base in bases:
            armor = base['mechanics']['armor']
            cap = armor['ac_cap_dexmod']
            if name in METAL_ARMOR_FAMILIES and (
                armor['name'] == 'Hide Armor' or (armor['ac_add_dexmod'] and cap is None)
            ):
                continue
            mithral = name == 'Mithral Armor'
            formula = str(armor['ac_base'] + bonus)
            if armor['ac_add_dexmod']:
                formula += ' + Dex modifier'
                if cap is not None:
                    formula += f' (max +{cap})'
            training = ('Medium armor' if cap is not None else 'Light armor'
                        if armor['ac_add_dexmod'] else 'Heavy armor')
            fields = {
                'Armor class': formula, 'Training': training,
                'Strength requirement': 'None' if mithral else str(armor['strength_score_required'] or 'None'),
                'Stealth disadvantage': 'Yes' if armor['grants_stealth_disadvantage'] and not mithral else 'No',
                'Weight': f"{float(base['mechanics']['source_fields']['weight']):g} lb",
                'Attunement': 'Required' if attune else 'None', 'Rarity': rarity, **effects,
            }
            label = 'Verified 2024 armor counterpart' if item['id'] in {
                'dndbeyond:5370', 'dndbeyond:5371', 'dndbeyond:5376', 'dndbeyond:5381',
            } or item['id'] in LEGACY_ARMOR_ENHANCEMENTS else 'Verified 2024 armor rules'
            variants.append({
                'label': label + ' · ' + armor['name'], 'status': 'published-reference',
                'profile_kind': 'published-public-armor', 'source': source, 'enhancement_bonus': bonus,
                'rules_source': PUBLIC_ARMOR_RULES[item['id']], 'mithral': mithral,
                'fields': fields, 'related_item': {'id': base['id'], 'label': 'Open 2024 base equipment'},
            })
        records[item['id']] = variants
    return records


LEGACY_ARMOR_COUNTERPARTS = {
    'dndbeyond:4574': ('dndbeyond:9228350', MAGIC + '#ArmorofInvulnerability'),
    'dndbeyond:4619': ('dndbeyond:9228451', MAGIC + '#DemonArmor'),
    'dndbeyond:5380': ('dndbeyond:9228477', MAGIC + '#DragonScaleMail'),
    'dndbeyond:4626': ('dndbeyond:9228527', MAGIC + '#DwarvenPlate'),
    'dndbeyond:5350': ('dndbeyond:9228530', MAGIC + '#EfreetiChain'),
    'dndbeyond:4631': ('dndbeyond:9228539', MAGIC + '#ElvenChain'),
    'dndbeyond:5507': ('dndbeyond:9228837', PUBLIC_ARMOR_RULES['dndbeyond:9228837']),
    'dndbeyond:4698': ('dndbeyond:9228928', MAGIC + '#PlateArmorofEtherealness'),
}


def indexed_legacy_counterparts(items, modern_profiles):
    indexed = {item['id']: item for item in items}
    records = {}
    for legacy_id, (modern_id, rules_source) in LEGACY_ARMOR_COUNTERPARTS.items():
        if legacy_id not in indexed:
            continue
        legacy = indexed[legacy_id]
        modern = indexed[modern_id]
        slug = legacy['name'].lower().replace("'", '').replace(' ', '-')
        source = f"https://www.dndbeyond.com/magic-items/{legacy_id.split(':')[1]}-{slug}"
        if (legacy['name'] != modern['name'] or legacy['requires_attunement'] != modern['requires_attunement']
                or legacy['provenance'].get('source_url') != source):
            raise ValueError(f'Legacy armor identity mismatch: {legacy_id}')
        records[legacy_id] = [
            {**entry, 'source': source, 'rules_source': rules_source,
             'label': entry['label'].replace('Verified 2024 armor rules', 'Verified 2024 armor counterpart')}
            for entry in modern_profiles[modern_id]
        ]
    return records


def build(catalog):
    database = (catalog / 'indexes/items.sqlite3').resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        items = [json.loads(raw) for (raw,) in db.execute(
            "SELECT data_json FROM items WHERE type IN ('armor', 'shield') AND source_id IN (?, ?, ?) ORDER BY id",
            (LEGACY, CURRENT, 'dndbeyond-public-index'))]
    modern = collections.defaultdict(list)
    for item in items:
        if item['source_id'] == CURRENT:
            modern[key(item['name'])].append(item)
    published = json.loads((catalog / 'supplements/published-2024-armor-facts.json').read_text())
    armor_facts = published['records']
    current_families = {}
    for item in items:
        family = item['name'].partition(' (')[0]
        if item['source_id'] == CURRENT and item['name'] in REVIEWED_STRUCTURED and item['mechanics'].get('armor'):
            bonus, effect, training = REVIEWED_STRUCTURED[item['name']]
            current_families[item['id']] = {'source': MAGIC, 'bonus': bonus, 'effect': effect,
                                            'training': training, 'mithral': False}
        if item['source_id'] == CURRENT and item['mechanics'].get('armor') and item['requires_attunement'] is True:
            for prefix, phrase, bonus, effect in CURSED_FAMILIES:
                if item['name'].startswith(prefix) and phrase in (item.get('description') or '').casefold():
                    current_families[item['id']] = {'source': MAGIC, 'bonus': bonus,
                                                    'effect': effect, 'mithral': False}
        if item['source_id'] == CURRENT and family in FAMILIES and item['mechanics'].get('armor'):
            phrase, effect = FAMILIES[family]
            if phrase in (item.get('description') or '').casefold():
                current_families[item['id']] = {'source': MAGIC, 'effect': effect, 'mithral': family == 'Mithral Armor'}
    records = {}
    for item in items:
        if item['source_id'] != LEGACY:
            continue
        family = item['name'].partition(' (')[0]
        structured = STRUCTURED_LEGACY.get(item['name'])
        matches = modern[key(structured[0] if structured else item['name'])]
        if len(matches) != 1:
            continue
        target = matches[0]
        if (item['name'] in REVIEWED_VARIANTS and item['name'] == target['name']
                and target['id'] in armor_facts and item['description'] and target['description']):
            records[item['id']] = {
                'target_id': target['id'], 'source': published['source'],
                'change': REVIEWED_VARIANTS[item['name']], 'mithral': False,
                'effect': armor_facts[target['id']]['effects'], 'bonus': armor_facts[target['id']]['bonus'],
            }
            continue
        if (item['magic'] != target['magic'] or item['requires_attunement'] != target['requires_attunement']
                or not same_base(item, target)):
            continue
        if structured and target['id'] in current_families:
            records[item['id']] = {
                'target_id': target['id'], **current_families[target['id']], 'change': structured[1],
            }
            continue
        effect = ''
        if item['magic']:
            if family not in FAMILIES or item['rarity'] != target['rarity']:
                continue
            phrase, effect = FAMILIES[family]
            if not all(phrase in (row['description'] or '').casefold() for row in (item, target)):
                continue
        records[item['id']] = {
            'target_id': target['id'], 'source': MAGIC if effect else EQUIPMENT,
            'effect': effect, 'mithral': family == 'Mithral Armor',
        }
    public = public_armor_variants(items)
    curated = json.loads((catalog / 'supplements/curated-item-details.json').read_text())['records']
    public.update(indexed_legacy_counterparts(items, {**curated, **public}))
    return {'schema_version': 1, 'records': records, 'modern': current_families, 'public': public}


if __name__ == '__main__':
    output = build(CATALOG)
    (CATALOG / 'supplements/core-armor-cross-references.json').write_text(
        json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f"Verified {len(output['records'])} legacy armor records against published 2024 counterparts.")
