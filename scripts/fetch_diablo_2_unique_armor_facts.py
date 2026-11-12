#!/usr/bin/env python3
"""Import exact unique armor rows and add reviewed, item-specific tabletop effects."""
import json
import re
import sqlite3

from fetch_diablo_2_base_armor_facts import BASES, CATALOG, adaptation
from fetch_diablo_2_unique_weapon_facts import stat_lines
from fetch_ninja_references import clean, fetch

TABLE = re.compile(r'https://classic\.battle\.net/diablo2exp/items/(?:normal|exceptional|elite)/u(?:armor|shields|necro|paladin)\.shtml')
FACTS = {
    'defense': 'Defense (game)', 'required level': 'Required level',
    'required strength': 'Minimum Strength', 'durability': 'Durability',
    'chance to block': 'Block (game)', 'paladin smite damage': 'Paladin Smite damage (game)',
}
# Each conversion preserves one or more distinctive source effects within bounded 2024 rules.
EFFECTS = {
    'Greyform': ('Rare', 'While wearing this armor, choose Cold or Fire when you finish a Long Rest. '
                 'You have Resistance to the chosen damage type until your next Long Rest. Once per Short '
                 'or Long Rest, when you hit a creature with a melee weapon attack, regain 1d6 Hit Points.'),
    'Hawkmail': ('Rare', 'While wearing this armor, you have Resistance to Cold damage and your Speed '
                 'increases by 5 feet. Ice and snow do not count as Difficult Terrain for you.'),
    'Venom Ward': ('Rare', 'While wearing this armor, you have Resistance to Poison damage and Advantage '
                   'on saves to avoid or end the Poisoned condition. As a Bonus Action you can make the '
                   'armor shed Dim Light in a 10-foot radius or extinguish that light.'),
    'Sparking Mail': ('Rare', 'While wearing this armor, you have Resistance to Lightning damage. When a '
                      'creature within 5 feet hits you with a melee attack, you can take a Reaction to deal '
                      '1d8 Lightning damage to it. You can take this Reaction twice per Long Rest.'),
    'Iceblink': ('Rare', 'While wearing this armor, you have Resistance to Cold damage. Once per Long Rest, '
                 'when you hit a Large or smaller creature with a melee weapon attack, you can force it to '
                 'make a DC 15 Constitution saving throw. On a failure, its Speed is 0 until the start of your next turn.'),
    'Swordback Hold': ('Uncommon', 'While wielding this shield, when a creature within 5 feet hits you with '
                       'a melee attack, you can use a Reaction to deal 1d6 Piercing damage to it with the spikes. '
                       'You can take this Reaction twice per Long Rest.'),
    'Blackoak Shield': ('Rare', 'While wielding this shield, you have Resistance to Cold damage. Once per '
                        'Long Rest, when a creature within 5 feet hits you with a melee attack, use a Reaction '
                        'to force it to make a DC 15 Strength saving throw. On a failure, subtract 1d4 from its '
                        'weapon damage rolls until the end of its next turn, to a minimum of 0 damage.'),
    'Stormshield': ('Very Rare', 'While wielding this shield, you have Resistance to Cold and Lightning damage. '
                    'When a creature within 5 feet hits you with a melee attack that deals Bludgeoning, Piercing, '
                    'or Slashing damage, you can use a Reaction to reduce that damage by 2d8 and deal 1d8 '
                    'Lightning damage to the attacker. You can take this Reaction twice per Long Rest.'),
}


NATIVE_SIGNATURES = {
    'Greyform': '5% life steal on hit, 20% Cold and Fire resistance.',
    'Hawkmail': '10% faster movement, +15% Cold resistance and maximum Cold resistance, freeze immunity.',
    'Venom Ward': '+90% Poison resistance, +15% maximum Poison resistance, half poison duration, +2 light radius.',
    'Sparking Mail': '+30% Lightning resistance, 10–14 Lightning returned to attackers, 1–20 added Lightning damage.',
    'Iceblink': 'Attacks can freeze the target. +30% Cold resistance.',
    'Swordback Hold': '50% chance to inflict Open Wounds and 10 damage returned to attackers.',
    'Blackoak Shield': 'Cold absorption scales with character level. 4% chance to cast level 5 Weaken when struck.',
    'Stormshield': '35% damage reduction, +60% Cold resistance, +25% Lightning resistance, 10 Lightning returned to attackers.',
}


def table_rows(url):
    rows = {}
    for row in fetch(url).xpath('//tr[td[img or .//img]][count(td)=2]'):
        left, right = row.xpath('./td')
        names = left.xpath('.//b')
        if len(names) != 1 or right.xpath('.//table'):
            continue
        name = clean(names[0].text_content())
        fields = {}
        for line in stat_lines(right):
            key, _, value = line.partition(':')
            if key.casefold() in FACTS and value.strip():
                fields[FACTS[key.casefold()]] = value.strip()
            elif key.casefold() == 'indestructible':
                fields['Durability'] = 'Indestructible'
        if 'Defense (game)' not in fields:
            continue
        if name.casefold() in rows:
            raise ValueError(f'Duplicate armor row: {name}')
        label = clean(left.text_content())
        fields['Native base item'] = label.removeprefix(name).strip()
        rows[name.casefold()] = fields
    return rows


def main():
    index = CATALOG / 'indexes/items.sqlite3'
    with sqlite3.connect(index.resolve().as_uri() + '?mode=ro', uri=True) as database:
        items = [json.loads(raw) for (raw,) in database.execute(
            """SELECT data_json FROM items WHERE type IN ('armor', 'shield')
            AND source_id IN ('diablo-2-reference', 'open5e-srd-2024') ORDER BY id""")]
    bases = {item['id']: item for item in items if item['source_id'] == 'open5e-srd-2024'}
    pages, records = {}, {}
    adapted = set()
    for item in items:
        provenance = item['provenance']
        if (item['source_id'] != 'diablo-2-reference'
                or provenance.get('evidence', {}).get('kind') != 'official-unique-name-index'):
            continue
        url, name = provenance['source_url'], item['name']
        if not TABLE.fullmatch(url):
            raise ValueError(f'Unexpected armor table: {url}')
        if url not in pages:
            pages[url] = table_rows(url)
        facts = pages[url][name.casefold()]
        locator = f'Blizzard Arreat Summit, {name} row.'
        entries = [{'label': 'Diablo II · Unique game statistics', 'status': 'source-reported', 'source': url,
                    'fields': {**facts, 'Source locator': locator}}]
        if name in EFFECTS:
            entries[0]['fields']['Signature effects (game)'] = NATIVE_SIGNATURES[name]
            rarity, effect = EFFECTS[name]
            group = 'shields' if item['type'] == 'shield' else 'armor'
            slug = 'shield' if group == 'shields' else BASES[facts['Native base item']]
            base = bases['open5e-srd-2024:srd-2024_' + slug]
            fields = adaptation(base, item['type'], group, locator)
            fields.update({'Rarity': rarity, 'Attunement': 'Required.', 'Special powers': effect,
                           'Conversion notes': f"Uses the 2024 {base['name']} profile. Translates selected "
                           "signature effects into 2024 rules with the listed triggers and limits."})
            entries.append({'label': 'D&D 2024 unique armor adaptation', 'status': 'original-draft', 'source': url,
                            'profile_kind': 'adapted-game-armor',
                            'rules_source': 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment#Armor',
                            'related_item': {'id': base['id'], 'label': f"Open 2024 {base['name']}"},
                            'fields': fields})
            adapted.add(name)
        records[item['id']] = entries
    if not records or adapted != EFFECTS.keys():
        raise ValueError(f'Armor import incomplete, missing drafts: {EFFECTS.keys() - adapted}')
    path = CATALOG / 'supplements/diablo-2-unique-armor-facts.json'
    path.write_text(json.dumps({'schema_version': 1, 'records': records}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Imported {len(records)} unique armor records from {len(pages)} tables, with {len(adapted)} playable conversions.')


if __name__ == '__main__':
    main()
