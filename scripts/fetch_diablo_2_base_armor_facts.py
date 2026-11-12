#!/usr/bin/env python3
"""Import Arreat Summit armor and shield facts and link playable 2024 profiles."""
import json
import re
import sqlite3
from pathlib import Path

from fetch_ninja_references import clean, fetch

CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
TABLE = re.compile(r'https://classic\.battle\.net/diablo2exp/items/(normal|exceptional|elite)/(armor|shields|paladinshields|shrunkenheads)\.shtml')
RULES = 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment#Armor'
LABELS = {
    'min/max defense': 'Defense (game)', 'min strength': 'Minimum Strength',
    'level requirement': 'Required level', 'durability': 'Durability',
    '% block': 'Block (game)', 'sockets': 'Max sockets', 'type': 'Weight class (game)',
    'paladin smite damage': 'Paladin Smite damage (game)', 'quality level': 'Quality level',
}
# Analogues by construction, across the three versions of each body armor style.
ARMOR_FAMILIES = {
    'padded-armor': ('Quilted Armor', 'Ghost Armor', 'Dusk Shroud'),
    'leather-armor': ('Leather Armor', 'Serpentskin Armor', 'Wyrmhide'),
    'hide-armor': ('Hard Leather Armor', 'Demonhide Armor', 'Scarab Husk'),
    'studded-leather-armor': ('Studded Leather', 'Trellised Armor', 'Wire Fleece'),
    'ring-mail': ('Ring Mail', 'Linked Mail', 'Diamond Mail'),
    'scale-mail': ('Scale Mail', 'Tigulated Mail', 'Loricated Mail'),
    'breastplate': ('Breast Plate', 'Cuirass', 'Great Hauberk'),
    'chain-mail': ('Chain Mail', 'Mesh Armor', 'Boneweave'),
    'splint-armor': ('Splint Mail', 'Russet Armor', 'Balrog Skin'),
    'half-plate-armor': ('Light Plate', 'Mage Plate', 'Archon Plate',
                         'Field Plate', 'Sharktooth Armor', 'Kraken Shell'),
    'plate-armor': ('Plate Mail', 'Templar Coat', 'Hellforge Plate', 'Gothic Plate', 'Embossed Plate',
                    'Lacquered Plate', 'Full Plate Mail', 'Chaos Armor', 'Shadow Plate',
                    'Ancient Armor', 'Ornate Plate', 'Sacred Armor'),
}
BASES = {name: base for base, names in ARMOR_FAMILIES.items() for name in names}


def table_rows(tree):
    items = {}
    for table in tree.xpath('//table'):
        headers = []
        for row in table.xpath('./tr|./tbody/tr|./thead/tr'):
            cells = row.xpath('./td|./th')
            values = [clean(cell.text_content()) for cell in cells]
            if 'Min/Max Defense' in values:
                headers = [LABELS.get(value.casefold()) for value in values]
                continue
            if not headers or len(values) != len(headers) or not cells[0].xpath('./img'):
                continue
            names = cells[0].xpath('.//b')
            if len(names) != 1:
                continue
            name = clean(names[0].text_content())
            fields = {label: value for label, value in zip(headers, values) if label and value}
            if not re.fullmatch(r'\d+\s*[-–]\s*\d+|\d+', fields['Defense (game)']) or name in items:
                raise ValueError(f'Invalid or duplicate defense row for {name}')
            items[name] = fields
    return items


def adaptation(base, item_type, group, locator):
    armor = base['mechanics']['armor']
    fields = {'Source locator': locator, 'Attunement': 'None.'}
    if item_type == 'shield':
        fields.update({'Armor class bonus': '+2', 'Training': 'Shield', 'Weight': '6 lb',
                       'Equip': 'Take the Utilize action to don or doff. Wield in one hand.'})
        note = {
            'paladinshields': 'Keep the heraldic design. The video game limits this family to Paladins; this conversion uses normal Shield training.',
            'shrunkenheads': 'Use a ritual trophy mounted on a rigid shield backing. The game’s Necromancer restriction and random skill bonuses stay in the native rules.',
            'shields': 'Use the standard Shield profile for this shield shape.',
        }[group]
    else:
        dexterity = armor['ac_add_dexmod']
        cap = armor['ac_cap_dexmod']
        ac = str(armor['ac_base'])
        if dexterity:
            ac += ' + Dex modifier'
            if cap is not None:
                ac += f' (max +{cap})'
        training = 'Heavy' if not dexterity else 'Medium' if cap is not None else 'Light'
        strength = armor['strength_score_required']
        fields.update({
            'Armor class': ac, 'Training': training,
            'Strength requirement': f'{strength}. Below this score, reduce Speed by 10 feet.' if strength else 'None.',
            'Stealth disadvantage': 'Yes' if armor['grants_stealth_disadvantage'] else 'No.',
            'Weight': f"{float(base['mechanics']['source_fields']['weight']):g} lb",
        })
        note = f"Uses {base['name']} as the analogue for this body armor style."
    fields['Special powers'] = 'None for the unenchanted base item.'
    fields['Conversion notes'] = note + ' Native Defense, block, sockets and item tiers have no direct tabletop bonus.'
    return fields


def main():
    with sqlite3.connect((CATALOG / 'indexes/items.sqlite3').resolve().as_uri() + '?mode=ro', uri=True) as db:
        records = [json.loads(raw) for (raw,) in db.execute(
            """SELECT data_json FROM items WHERE type IN ('armor', 'shield')
            AND source_id IN ('diablo-2-reference', 'open5e-srd-2024') ORDER BY id""")]
    bases = {item['id']: item for item in records if item['source_id'] == 'open5e-srd-2024'}
    pages, output = {}, {}
    for item in records:
        provenance = item['provenance']
        if (item['source_id'] != 'diablo-2-reference'
                or provenance.get('evidence', {}).get('kind') != 'official-base-item-table'):
            continue
        url = provenance['source_url']
        tier, group = TABLE.fullmatch(url).groups()
        if tier != item['mechanics']['reference_metadata']['tier']:
            raise ValueError(f"Source tier disagrees for {item['id']}")
        if url not in pages:
            pages[url] = table_rows(fetch(url))
        fields = pages[url][item['name']]
        locator = f"Blizzard Arreat Summit, {tier} {group} table, {item['name']} row."
        base = bases['open5e-srd-2024:srd-2024_' + (BASES[item['name']] if group == 'armor' else 'shield')]
        if group == 'paladinshields':
            restriction = 'Paladin only. A variable automatic modifier can appear on the item.'
        elif group == 'shrunkenheads':
            restriction = 'Necromancer only. Can roll specific Necromancer skill bonuses and an automatic modifier.'
        else:
            restriction = 'No class restriction in this base table.'
        output[item['id']] = [
            {'label': 'Diablo II · Game statistics', 'status': 'source-reported', 'source': url,
             'fields': {**fields, 'Class rules (game)': restriction, 'Source locator': locator}},
            {'label': 'D&D 2024 armor adaptation', 'status': 'original-draft', 'source': url,
             'profile_kind': 'adapted-game-armor', 'rules_source': RULES,
             'related_item': {'id': base['id'], 'label': f"Open 2024 {base['name']}"},
             'fields': adaptation(base, item['type'], group, locator)},
        ]
    if not output:
        raise SystemExit('No Diablo II base armor records found')
    path = CATALOG / 'supplements/diablo-2-base-armor-facts.json'
    path.write_text(json.dumps({'schema_version': 1, 'records': output}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Imported and mapped {len(output)} base armors and shields from {len(pages)} Arreat Summit tables.')


if __name__ == '__main__':
    main()
