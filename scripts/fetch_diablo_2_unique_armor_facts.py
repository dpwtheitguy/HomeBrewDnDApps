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
    "Ormus' Robes": ('Very Rare',
        'After each Long Rest choose Cold, Fire, or Lightning. Once on each of your turns when a '
        'spell you cast deals the chosen damage, add 1d6 of that type to one target. Use this '
        'benefit three times per Long Rest.'),
    "The Gladiator's Bane": ('Very Rare',
        'While wearing the armor, you have Advantage on saves to avoid or end being Poisoned. When '
        'you take damage from a spell or weapon attack, use a Reaction to reduce it by 2d6. Use this '
        'Reaction three times per Long Rest.'),
    "Arkaine's Valor": ('Very Rare',
        'When you finish a Long Rest wearing the armor, gain Temporary Hit Points equal to twice '
        'your Proficiency Bonus plus your Constitution modifier, minimum 1. Once per Long Rest, '
        'reroll a failed Strength, Dexterity, or Constitution save and use the new roll.'),
    'Leviathan': ('Very Rare',
        'The armor is immune to damage while worn. While wearing it, you count as one size larger '
        'for carrying, pushing, dragging, and lifting. Once per Short or Long Rest, use a Reaction '
        'when you take Bludgeoning, Piercing, or Slashing damage to reduce it by 2d8.'),
    'Steel Carapace': ('Very Rare',
        'You have Resistance to Cold damage. Twice per Long Rest when a creature within 5 feet hits '
        'you with a melee attack, use a Reaction to deal 2d6 Psychic damage to it. After a Long Rest '
        'the armor repairs its own ordinary wear.'),
    "Templar's Might": ('Very Rare',
        'While wearing the armor, you have Half Cover against ranged weapon attacks. Once per Long '
        'Rest as a Bonus Action, choose yourself and up to two allies within 10 feet. Each chosen '
        'creature gains 10 Temporary Hit Points.'),
    "Tyrael's Might": ('Legendary',
        'This Plate has no Strength requirement and grants +10 feet of Speed. While wearing it, the '
        'first time each turn you hit a Fiend with a weapon, deal an extra 1d8 Radiant damage. A '
        'creature you kill with such a hit cannot be raised as Undead for 24 hours.'),
    'Spike Thorn': ('Rare',
        'When a creature within 5 feet hits you with a melee attack while you wield the shield, use '
        'a Reaction to reduce its damage by 1d8 and deal the same amount of Piercing damage to the '
        'attacker. Use twice per Long Rest.'),
    "Medusa's Gaze": ('Very Rare',
        'You have Cold Resistance while wielding the shield. Twice per Long Rest, when hit by a '
        'creature you can see within 30 feet, use a Reaction. It must succeed on a DC 16 '
        'Constitution save or have its Speed halved and lose Reactions until the end of its next '
        'turn.'),
    "Head Hunter's Glory": ('Very Rare',
        'Choose Fire or Poison Resistance after a Long Rest. While wielding the shield, once per '
        'Short or Long Rest when you reduce a hostile creature to 0 Hit Points with a weapon attack, '
        'gain 2d6 Temporary Hit Points.'),
    'Spirit Ward': ('Very Rare',
        'Once per Long Rest when you take Acid, Cold, Fire, Lightning, or Poison damage while '
        'wielding this shield, use a Reaction to gain Resistance to the triggering type against that '
        'damage and until the end of your next turn.'),
    'The Spirit Shroud': ('Rare',
        'You have Advantage on saves against being Paralyzed. Once per Long Rest as a Bonus Action, '
        'regain 2d6 Hit Points while wearing the armor.'),
    'Skin of the Vipermagi': ('Rare',
        'While wearing the armor, once per Long Rest when a spell deals damage to you, use a '
        "Reaction to halve that spell's damage to you. You also have Advantage on the first "
        'Constitution save to maintain Concentration you make after each Short or Long Rest.'),
    'Skin of the Flayed One': ('Rare',
        'After a Long Rest the armor repairs its ordinary wear. Once per Short or Long Rest, when a '
        'melee weapon hit reduces a hostile creature to 0 Hit Points, regain Hit Points equal to 1d8 '
        'plus your Proficiency Bonus.'),
    'Iron Pelt': ('Rare',
        'While wearing the armor, once per Short or Long Rest when a source deals damage to you, use '
        'a Reaction to reduce it by 1d8 plus your Proficiency Bonus.'),
    'Crow Caw': ('Rare',
        'Once per Short or Long Rest when you hit a creature with a Slashing weapon attack, it takes '
        'an extra 1d6 Slashing. It then takes 1d6 Slashing at the start of its next turn unless it '
        'has regained Hit Points since the hit.'),
    'Spirit Forge': ('Rare',
        'While wearing the armor, use a Bonus Action to kindle or extinguish Bright Light in a '
        '10-foot radius and Dim Light for another 10 feet. Once on each of your turns, add 1d6 Fire '
        'damage to one melee weapon hit, up to three times per Long Rest.'),
    "Duriel's Shell": ('Very Rare',
        'While wearing the armor, you have Cold Resistance and Advantage on saves against effects '
        'that would reduce your Speed. When you finish a Long Rest wearing it, gain 10 Temporary Hit '
        'Points.'),
    'Shaftstop': ('Rare',
        'While wearing the armor, when a ranged weapon attack hits you, use a Reaction to reduce its '
        'damage by 2d8. Use this Reaction twice per Long Rest.'),
    "Skullder's Ire": ('Rare',
        'After a Long Rest the armor repairs its ordinary wear. Once per Long Rest while wearing it, '
        'cast Detect Magic without Material components, using its normal casting time and '
        'Concentration.'),
    "Que-Hegan's Wisdom": ('Rare',
        'Once per Long Rest when you reduce a hostile creature to 0 Hit Points with a spell, gain '
        '1d6 Temporary Hit Points and recover an expended level 1 spell slot.'),
    'Toothrow': ('Rare',
        'You have Fire Resistance while wearing the armor. Once per Short or Long Rest when a '
        'creature within 5 feet hits you with a melee attack, use a Reaction to deal 2d6 Piercing '
        'damage to it.'),
    'Guardian Angel': ('Very Rare',
        'As a Bonus Action once per Long Rest, emanate Bright Light in a 10-foot radius for 1 '
        'minute. You and allies in that light have Advantage on saves against being Frightened by '
        'Fiends.'),
    "Atma's Wail": ('Rare',
        'Once per Long Rest, when you fail a Dexterity saving throw, use a Reaction to reroll it. If '
        'the new roll succeeds, you also regain 1d8 Hit Points. Use the new roll.'),
    'Black Hades': ('Rare',
        'While wearing the armor, once on each of your turns when you hit a Fiend with a weapon, '
        "deal an extra 1d6 damage of the weapon's type. It has three decorative settings for gems."),
    'Corpsemourn': ('Very Rare',
        'You have Cold Resistance. Once per Long Rest as a Magic action, choose a corpse of a Small '
        'or larger creature you can see within 30 feet. It erupts. Other creatures within 10 feet of '
        'it make a DC 16 Dexterity save, taking 4d6 Fire damage on failure or half as much on '
        'success.'),
    'Visceratuant': ('Rare',
        'Once per Short or Long Rest when a creature within 5 feet misses you with a melee attack '
        'while you wield the shield, use a Reaction to deal 1d8 Lightning damage to it.'),
    "Moser's Blessed Circle": ('Rare',
        'After a Long Rest choose Acid, Cold, Fire, Lightning, or Poison. While wielding this shield '
        'you have Resistance to the chosen type. The two visible sockets are decorative in this '
        'profile.'),
    'Stormchaser': ('Rare',
        'You have Lightning Resistance while wielding the shield. Once per Long Rest, when hit by a '
        'Large or smaller creature within 5 feet, use a Reaction to force it to make a DC 15 '
        'Strength save or be pushed 10 feet directly away.'),
    "Tiamat's Rebuke": ('Very Rare',
        'Three times per Long Rest, when hit by a creature within 5 feet while you wield the shield, '
        'use a Reaction to deal 2d6 Cold, Fire, or Lightning damage to it, choosing the type each '
        'time.'),
    'Lance Guard': ('Rare',
        'While wielding the shield, once per Short or Long Rest when you take damage from a weapon '
        'attack, use a Reaction to gain 1d8 Temporary Hit Points after resolving the damage.'),
    "Gerke's Sanctuary": ('Very Rare',
        'While wielding the shield, when you take damage, use a Reaction to reduce the damage by '
        '2d8. Use this Reaction three times per Long Rest.'),
    'Lidless Wall': ('Rare',
        'While wielding this shield, once per Long Rest when your spell reduces a hostile creature '
        'to 0 Hit Points, recover an expended level 1 spell slot.'),
    "Radament's Sphere": ('Rare',
        'You have Poison Resistance while wielding the shield. Once per Long Rest, take a Magic '
        'action to release a 10-foot Emanation. Each other creature in it makes a DC 15 Constitution '
        'save, taking 3d6 Poison damage on failure or half on success.'),
    "Blinkbat's Form": ('Uncommon',
        'While wearing the armor your Speed increases by 5 feet. Once per Short or Long Rest when a '
        'ranged weapon attack targets you, use a Reaction to impose Disadvantage on the attack '
        'before it is rolled.'),
    'The Centurion': ('Uncommon',
        'Once per Long Rest as a Bonus Action, regain 1d8 Hit Points while wearing the armor.'),
    'Twitchthroe': ('Rare',
        'While wearing the armor, once per Long Rest when you take the Attack action, you can make '
        'one additional weapon attack as a Bonus Action on that turn.'),
    'Darkglow': ('Rare',
        'After a Long Rest choose Cold, Fire, Lightning, or Poison. While wearing the armor, you '
        'have Resistance to that type. As a Bonus Action you can kindle or extinguish Dim Light in a '
        '10-foot radius.'),
    'Heavenly Garb': ('Rare',
        'Once on each of your turns when you hit an Undead with a weapon, you can deal an extra 1d6 '
        'Radiant damage, up to three times per Long Rest.'),
    'Rockfleece': ('Rare',
        'While wearing the armor, once per Short or Long Rest when you take Bludgeoning, Piercing, '
        'or Slashing damage, use a Reaction to reduce that damage by 2d6.'),
    'Boneflesh': ('Rare',
        'Once per Short or Long Rest when you hit a living creature with a melee weapon attack, deal '
        'an extra 1d6 Necrotic damage and regain Hit Points equal to the Necrotic damage dealt.'),
    'Rattlecage': ('Rare',
        'Once per Short or Long Rest on a melee weapon hit, force the target to make a DC 15 Wisdom '
        'save. On a failure it is Frightened of you until the end of your next turn.'),
    'Goldskin': ('Rare',
        'After a Long Rest choose Acid, Cold, Fire, Lightning, or Poison. You have Resistance to '
        'that type while wearing this gilded plate. As a Bonus Action, kindle or extinguish Bright '
        'Light within 10 feet and Dim Light for another 10 feet.'),
    'Silks of the Victor': ('Rare',
        'Once per Long Rest when you reduce a hostile creature to 0 Hit Points with a weapon attack, '
        'recover an expended level 1 spell slot.'),
    'Pelta Lunata': ('Uncommon',
        'While wielding the shield, when a melee attack hits you, use a Reaction to add 2 to your AC '
        'against that attack, potentially turning it into a miss. Use once per Short or Long Rest.'),
    'Umbral Disk': ('Rare',
        'Once per Long Rest when you hit a creature within 5 feet while wielding the shield, it must '
        'succeed on a DC 15 Constitution save or be Blinded until the end of its next turn.'),
    'Stormguild': ('Rare',
        'You have Lightning Resistance while wielding the shield. Once per Short or Long Rest when a '
        'creature within 5 feet hits you with a melee attack, use a Reaction to deal 1d6 Lightning '
        'damage to it.'),
    'Steelclash': ('Rare',
        'Once per Long Rest when you take Acid, Cold, Fire, Lightning, or Poison damage while '
        'wielding the shield, use a Reaction to halve that damage. The shield sheds Dim Light in a '
        '10-foot radius while wielded.'),
    'Bverrit Keep': ('Uncommon',
        'You have Resistance to Fire damage while wielding this shield.'),
    'Wall of the Eyeless': ('Rare',
        'You have Poison Resistance while wielding the shield. Once per Long Rest when you reduce a '
        'hostile creature to 0 Hit Points with a spell, gain Temporary Hit Points equal to your '
        'Proficiency Bonus plus your spellcasting ability modifier, minimum 1.'),
    'The Ward': ('Rare',
        'After a Long Rest choose Acid, Cold, Fire, Lightning, or Poison. You have Resistance to the '
        'chosen damage type while wielding the shield.'),
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
            if name in NATIVE_SIGNATURES:
                entries[0]['fields']['Signature effects (game)'] = NATIVE_SIGNATURES[name]
            rarity, effect = EFFECTS[name]
            group = 'shields' if item['type'] == 'shield' else 'armor'
            slug = 'shield' if group == 'shields' else BASES[facts['Native base item']]
            base = bases['open5e-srd-2024:srd-2024_' + slug]
            fields = adaptation(base, item['type'], group, locator)
            use = 'wield the shield' if group == 'shields' else 'wear the armor'
            fields.update({'Rarity': rarity, 'Attunement': 'Required.',
                           'Special powers': f'While attuned, you must {use} to use these powers. {effect}',
                           'Conversion notes': f"Uses the 2024 {base['name']} profile. Translates selected "
                           "signature effects into 2024 rules with the listed triggers and limits."})
            if name == "Tyrael's Might":
                fields['Strength requirement'] = 'None.'
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
