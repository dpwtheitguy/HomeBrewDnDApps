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

BOOK_OF_MANY_THINGS = 'https://www.dndbeyond.com/sources/dnd/tbomt'
PUBLIC_ARMOR_RULES = {
    **dict.fromkeys((
        'dndbeyond:7526578', 'dndbeyond:7526586', 'dndbeyond:7526597', 'dndbeyond:7526611',
        'dndbeyond:7526627', 'dndbeyond:7526630', 'dndbeyond:7526632', 'dndbeyond:7526655',
        'dndbeyond:7526675', 'dndbeyond:7526716', 'dndbeyond:7526744', 'dndbeyond:7526761',
        'dndbeyond:7526781',
    ), BOOK_OF_MANY_THINGS),
    **dict.fromkeys(LEGACY_ARMOR_ENHANCEMENTS, MAGIC + '#Armor12or3'),
    'dndbeyond:5370': MAGIC + '#AdamantineArmor',
    'dndbeyond:5371': MAGIC + '#ArmorofResistance',
    'dndbeyond:5376': MAGIC + '#ArmorofVulnerability',
    'dndbeyond:5381': MAGIC + '#MithralArmor',
    'dndbeyond:9228349': 'https://roll20.net/compendium/dnd5e/Templates%3AArmor%20of%20Gleaming?expansion=33359',
    'dndbeyond:9228382': 'https://roll20.net/compendium/dnd5e/Templates%3ACast-Off%20Armor?expansion=33359',
    'dndbeyond:36837': 'https://roll20.net/compendium/dnd5e/Templates%3ASmoldering%20Armor?expansion=33359',
    'dndbeyond:27116': 'https://roll20.net/compendium/dnd5e/Items%3AShield%20of%20Expression?expansion=33359',
    'dndbeyond:21731': 'https://online.anyflip.com/tqblu/jphj/files/basic-html/page209.html',
    'dndbeyond:3001260': 'https://anyflip.com/cwvnz/zdcr/basic/51-100',
    'dndbeyond:316637': 'https://online.anyflip.com/tqblu/plwt/files/basic-html/page180.html',
    'dndbeyond:316763': 'https://online.anyflip.com/tqblu/plwt/files/basic-html/page181.html',
    'dndbeyond:4047224': 'https://anyflip.com/lbdvl/isae/basic',
    'dndbeyond:842285': 'https://www.academia.edu/44600065/Baldurs_Gate_Descent_into_Avernus',
    'dndbeyond:843176': 'https://www.academia.edu/44600065/Baldurs_Gate_Descent_into_Avernus',
    'dndbeyond:7102410': 'https://www.dndbeyond.com/sources/dnd/gotg',
    'dndbeyond:7102439': 'https://www.dndbeyond.com/sources/dnd/gotg',
    'dndbeyond:7102441': 'https://www.dndbeyond.com/sources/dnd/gotg',
    'dndbeyond:7102449': 'https://www.dndbeyond.com/sources/dnd/gotg',
    'dndbeyond:1752526': 'https://www.dndbeyond.com/sources/dnd/moot',
    'dndbeyond:982693': 'https://www.dndbeyond.com/sources/dnd/erftlw',
    'dndbeyond:382908': 'https://www.dndbeyond.com/sources/dnd/vgtm',
    'dndbeyond:382914': 'https://www.dndbeyond.com/sources/dnd/vgtm',
    'dndbeyond:10886056': 'https://marketplace.dndbeyond.com/category/5147000',
    'dndbeyond:12467': 'https://www.dndbeyond.com/sources/lmop',
    'dndbeyond:7247069': 'https://www.dndbeyond.com/sources/dnd/pbtso',
    'dndbeyond:5554585': 'https://online.anyflip.com/rhoba/pyxn/files/basic-html/page69.html',
    'dndbeyond:351902': 'https://www.dndbeyond.com/sources/dnd/llok',
    'dndbeyond:351912': 'https://www.dndbeyond.com/sources/dnd/llok',
    'dndbeyond:351921': 'https://www.dndbeyond.com/sources/dnd/llok',
    'dndbeyond:342867': 'https://www.dndbeyond.com/sources/dnd/wdotmm',
    'dndbeyond:8225886': 'https://www.dndbeyond.com/magic-items/8225886-demon-skin',
    'dndbeyond:10674160': 'https://www.dndbeyond.com/sources/dnd/wthc',
    'dndbeyond:11914544': 'https://www.dndbeyond.com/sources/dnd/aud',
    'dndbeyond:11914433': 'https://www.dndbeyond.com/sources/dnd/au',
    'dndbeyond:12133285': 'https://www.dndbeyond.com/sources/dnd/wow',
    'dndbeyond:12133294': 'https://www.dndbeyond.com/sources/dnd/wow',
    'dndbeyond:9228451': MAGIC + '#DemonArmor',
    'dndbeyond:9228541': 'https://roll20.net/compendium/dnd5e/Templates%3AEnspelled%20Armor?expansion=33359',
    'dndbeyond:9228837': 'https://roll20.net/compendium/dnd5e/Templates%3AMariner%27s%20Armor?expansion=33359',
}

METAL_ARMOR_FAMILIES = {'Adamantine Armor', 'Mithral Armor', 'Mizzium Armor'}
PUBLIC_FIXED_BASES = {
    "Heward's Hireling Armor": {'Leather Armor'},
    'Leather Golem Armor': {'Leather Armor'},
    'Powered Armor': {'Plate Armor'},
    'Shield of the Uven Rune': {'Shield'},
    'Spiked Shield': {'Shield'},
    'Defias Leather': {'Leather Armor'},
    'Judgment Armor': {'Plate Armor'},
    'Shield of Expression': {'Shield'},
    "Pariah's Shield": {'Shield'},
    'Scorpion Armor': {'Plate Armor'},
    'Serpent Scale Armor': {'Scale Mail'},
    'Sapphire Buckler': {'Shield'},
    'Obsidian Flint Dragon Plate': {'Plate Armor'},
    'Shield of the Hidden Lord': {'Shield'},
    'Boomerang Shield': {'Shield'},
    "Euryale's Aegis": {'Shield'},
    'Shield of the Tortoise': {'Shield'},
    'Breastplate of Balance': {'Breastplate'},
    "Plate of Knight's Fellowship": {'Plate Armor'},
    'Voidwalker Armor': {'Studded Leather Armor'},
    'Shield of the Blazing Dreadnought': {'Shield'},
    "Stonebreaker's Breastplate": {'Breastplate'},
    'Molten Bronze Skin': {'Breastplate', 'Half Plate Armor', 'Plate Armor'},
    'Shield of Far Sight': {'Shield'},
    'Repulsion Shield': {'Shield'},
    'Dragonguard': {'Breastplate'},
    'Shield of the Silver Dragon': {'Shield'},
}

PUBLIC_TRAINING_LIMITS = {
    'Demon Skin': {'Heavy armor'},
    'Tramontane Armor': {'Light armor', 'Medium armor'},
    'Armor of Safeguarding': {'Heavy armor'},
    'Zephyr Armor': {'Light armor'},
    'Mind Carapace Armor': {'Heavy armor'},
    'Armor of Fungal Spores': {'Medium armor'},
    'Armor of the Fallen': {'Medium armor', 'Heavy armor'},
    'Clockwork Armor': {'Heavy armor'},
}

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
    'dndbeyond:36837': (
        'Smoldering Armor', '36837-smoldering-armor', 0, False, 'Common', {
            'Special powers': 'While worn, the armor gives off small wisps of harmless, odorless smoke. Use the base suit’s normal defenses.',
        },
    ),
    'dndbeyond:27116': (
        'Shield of Expression', '27116-shield-of-expression', 0, False, 'Common', {
            'Special powers': 'While carrying the shield, take a Bonus Action to change the expression of the face on its front.',
        },
    ),
    'dndbeyond:21731': (
        'Scorpion Armor', '21731-scorpion-armor', 0, True, 'Rare', {
            'Special powers': 'While worn, gain +5 to Initiative unless Incapacitated. The armor imposes no Stealth disadvantage and no disadvantage on saves against extreme heat.',
            'Curse': 'Each time you don or doff the armor, make a DC 15 Constitution save. Take 10d10 + 45 Poison damage on a failure or half as much on a success. Only Wish removes this curse.',
            'Publication': 'Tomb of Annihilation, Appendix C, p. 208. Original powers on the 2024 Plate Armor base.',
        },
    ),
    'dndbeyond:3001260': (
        'Serpent Scale Armor', '3001260-serpent-scale-armor', 0, False, 'Uncommon', {
            'Special powers': 'Add your full Dexterity modifier to the armor’s AC. The armor imposes no disadvantage on Dexterity (Stealth) checks.',
            'Publication': 'Candlekeep Mysteries, Book of Cylinders, p. 98. Original exceptions on the 2024 Scale Mail base.',
        },
    ),
    'dndbeyond:316637': (
        'Mizzium Armor', '316637-mizzium-armor', 0, False, 'Rare', {
            'Special powers': 'While worn, a Critical Hit against you becomes a normal hit. If a magical effect allows a Strength or Constitution saving throw for half damage, take no damage on a success.',
            'Publication': 'Guildmasters’ Guide to Ravnica, p. 179. Original powers on eligible 2024 armor bases.',
        },
    ),
    'dndbeyond:316763': (
        "Pariah's Shield", '316763-pariahs-shield', 0, True, 'Rare', {
            'Special powers': 'While wielding it, gain +1 AC for every two allies within 5 feet of you, up to +3 extra AC. When a creature you can see within 5 feet takes damage, you can take a Reaction to take that damage in its place. The transferred damage becomes Force damage.',
            'Publication': 'Guildmasters’ Guide to Ravnica, p. 180. Original powers on the 2024 Shield base.',
        },
    ),
    'dndbeyond:4047224': (
        'Sapphire Buckler', '4047224-sapphire-buckler', 0, True, 'Very Rare', {
            'Special powers': 'While wielding this shield, you have Resistance to Psychic and Thunder damage. When a creature within 5 feet damages you, you can take a Reaction to deal 2d6 Thunder damage to it.',
            'Aberration detection': 'Take a Magic action to detect the directions of Aberrations within 1 mile until the end of your next turn. The shield briefly hums if it detects any. This property recharges at dawn.',
            'Publication': 'Fizban’s Treasury of Dragons, Dragon Magic, Sapphire Buckler. Uses 2024 Shield defenses and Magic action terminology.',
        },
    ),
    'dndbeyond:842285': (
        'Obsidian Flint Dragon Plate', '842285-obsidian-flint-dragon-plate', 2, False, 'Legendary', {
            'Special powers': 'While wearing the armor, gain +2 AC and Resistance to Poison damage. You have Advantage on ability checks and saving throws made to avoid or end the Grappled condition on yourself.',
            'Publication': 'Baldur’s Gate: Descent into Avernus, Appendix C, p. 224. Original powers on the 2024 Plate Armor base.',
        },
    ),
    'dndbeyond:843176': (
        'Shield of the Hidden Lord', '843176-shield-of-the-hidden-lord', 2, True, 'Legendary', {
            'Special powers': 'While holding the shield, gain +2 AC in addition to its usual shield bonus and gain Resistance to Fire damage.',
            'Spellcasting': 'While Gargauth is imprisoned, the shield has 3 charges and regains all spent charges at dawn. Take a Magic action to cast Fireball for 1 charge or Wall of Fire for 2 charges, both with save DC 21. This Wall of Fire lasts 1 minute without Concentration.',
            'Aura of Dread': 'During your turn, Gargauth may activate a 20-foot aura for 1 minute. A creature hostile to you that starts its turn within the aura makes a DC 18 Wisdom saving throw. On a failure it is Frightened until its next turn starts. On a success it is immune to this aura for 24 hours. The aura recharges at dawn.',
            'Sentience': 'While Gargauth is imprisoned, the shield has Intelligence 22, Wisdom 18, and Charisma 24. It hears and has Truesight to 120 feet, speaks and understands Common and Infernal, can read both, and can communicate telepathically with creatures it senses within 120 feet.',
            'Gargauth': 'The trapped pit fiend pretends to be a captive angel, seeks release, and pushes its bearer toward cruelty and domination.',
            'Freeing Gargauth': 'Dispel Evil and Good has a 1% chance to release Gargauth, or releases him automatically if cast by a solar, planetar, or archdevil. A god can also release him by touching the shield and speaking his name. He appears in a random unoccupied space as close to the shield as possible.',
            'Fireball': 'https://www.dndbeyond.com/sources/dnd/br-2024/spell-descriptions#Fireball',
            'Wall of Fire': 'https://www.dndbeyond.com/sources/dnd/br-2024/spell-descriptions#WallofFire',
            'Publication': 'Baldur’s Gate: Descent into Avernus, Appendix C, p. 225. Uses 2024 Shield defenses, spell descriptions, and Magic action terminology.',
        },
    ),
    'dndbeyond:7526578': (
        'Antimagic Armor', '7526578-antimagic-armor', 0, True, 'Very Rare', {
            'Special powers': 'While wearing the armor, take a Reaction when you make a saving throw against a spell to give yourself Advantage on it. Once used, this Reaction recharges at dawn.',
            'Antimagic Field': 'While wearing the armor, take a Magic action to cast Antimagic Field without spell components. The field requires Concentration for up to 1 hour. This casting recharges separately at dawn.',
            'Publication': 'The Book of Many Things, p. 65.',
        },
    ),
    'dndbeyond:7526586': (
        'Armor of Fungal Spores', '7526586-armor-of-fungal-spores', 0, False, 'Uncommon', {
            'Special powers': 'While wearing the armor, take a Bonus Action to release spores in a 10-foot-radius Sphere centered on yourself. Each creature in the Sphere, including you, must make a DC 15 Constitution saving throw or be Poisoned until the end of your next turn. The power recharges at dawn.',
            'Publication': 'The Book of Many Things, p. 65.',
        },
    ),
    'dndbeyond:7526597': (
        'Armor of the Fallen', '7526597-armor-of-the-fallen', 0, True, 'Uncommon', {
            'Special powers': 'While wearing the armor, cast Speak with Dead or Animate Dead from it using the chosen spell’s normal casting time. The two spells share one use, which recharges at dawn. If you die while attuned to the armor, it is destroyed.',
            'Publication': 'The Book of Many Things, p. 65.',
        },
    ),
    'dndbeyond:7526611': (
        'Armor of Weightlessness', '7526611-armor-of-weightlessness', 0, True, 'Uncommon', {
            'Special powers': 'While wearing the armor, take a Bonus Action to cast Jump on yourself for 1 charge or Levitate on yourself for 2 charges. The armor holds 5 charges and regains 1d4 + 1 spent charges at dawn.',
            'Publication': 'The Book of Many Things, p. 65.',
        },
    ),
    'dndbeyond:7526627': (
        'Boomerang Shield', '7526627-boomerang-shield', 0, True, 'Uncommon', {
            'Special powers': 'You can throw the shield as a ranged weapon attack with a normal range of 20 feet and a long range of 60 feet. Choose Strength or Dexterity for the attack roll and add your Proficiency Bonus if you have Shield training. On a hit, the shield deals 1d6 Slashing damage. It returns to your hand immediately after a hit or miss.',
            'Publication': 'The Book of Many Things, p. 66.',
        },
    ),
    'dndbeyond:7526630': (
        'Breastplate of Balance', '7526630-breastplate-of-balance', 0, True, 'Rare', {
            'Special powers': 'The breastplate has 4 charges and regains 1d4 spent charges at dawn.',
            'Equalize': 'When you or a creature you can see within 60 feet of you is about to make a d20 roll with Advantage or Disadvantage, take a Reaction and spend 1 charge to have the roll proceed without either.',
            'Expunge Imbalance': 'Take a Bonus Action and spend 2 charges to cast Lesser Restoration.',
            'Publication': 'The Book of Many Things, p. 34.',
        },
    ),
    'dndbeyond:7526632': (
        'Clockwork Armor', '7526632-clockwork-armor', 0, True, 'Very Rare', {
            'Special powers': 'While wearing the armor, when you make a d20 roll, spend 1 charge to replace the number rolled with a 10. The armor holds 4 charges and regains 1d4 spent charges at dawn.',
            'Publication': 'The Book of Many Things, p. 67.',
        },
    ),
    'dndbeyond:7526655': (
        "Euryale's Aegis", '7526655-euryales-aegis', 0, True, 'Legendary', {
            'Special powers': 'While wielding the shield, you have Resistance to Poison damage and Immunity to the Petrified condition.',
            'Petrifying Heraldry': 'As a Bonus Action, choose one creature you can see within 30 feet. It must succeed on a DC 20 Constitution saving throw or become Restrained. At the start of its next turn it makes the save again. On a failure it is Petrified for 24 hours. On a success the Restrained condition ends. The power recharges at dawn.',
            'Spellcasting': 'While wielding the shield, take a Magic action to cast Lesser Restoration, Locate Creature, or Transport via Plants. Each spell has its own use and recharges at dawn.',
            'Publication': 'The Book of Many Things, p. 35.',
        },
    ),
    'dndbeyond:7526675': (
        'Feywrought Armor', '7526675-feywrought-armor', 0, True, 'Rare', {
            'Special powers': 'While wearing the armor, you have Advantage on saving throws to avoid or end the Charmed condition on yourself. Take a Magic action to spend 1 charge and cast Compulsion (save DC 15). The armor has 3 charges and regains 1d3 spent charges at dawn.',
            'Publication': 'The Book of Many Things, p. 67.',
        },
    ),
    'dndbeyond:7526716': (
        'Gloomwrought Armor', '7526716-gloomwrought-armor', 0, True, 'Rare', {
            'Special powers': 'While wearing the armor, you have Advantage on saving throws to avoid or end the Frightened condition on yourself. Spend 1 charge to cast Calm Emotions using its normal casting time (save DC 15). The armor has 3 charges and regains 1d3 spent charges at dawn.',
            'Publication': 'The Book of Many Things, p. 67.',
        },
    ),
    'dndbeyond:7526744': (
        "Plate of Knight's Fellowship", '7526744-plate-of-knights-fellowship', 0, True, 'Uncommon', {
            'Special powers': 'As a Bonus Action while wearing the armor, summon a spirit that uses the Knight stat block in an unoccupied space within 30 feet. It is an ally and takes its turn immediately after yours on the same Initiative count. It obeys your commands without an action from you. Without commands it Dodges and moves away from danger.',
            'Duration and recharge': 'The spirit disappears after 1 minute or at 0 HP. The armor regains this use at dawn.',
            'Publication': 'The Book of Many Things, p. 37.',
        },
    ),
    'dndbeyond:7526761': (
        'Shield of the Tortoise', '7526761-shield-of-the-tortoise', 1, True, 'Uncommon', {
            'Special powers': 'While wielding the shield, gain +1 AC in addition to its ordinary +2 shield bonus.',
            'Curse': 'Attuning curses you until Remove Curse or similar magic frees you. While cursed, you cannot discard the shield or end attunement. Your Speed is halved. Treat your Initiative d20 as a 1, and no effect can change your Initiative.',
            'Publication': 'The Book of Many Things, p. 67.',
        },
    ),
    'dndbeyond:7526781': (
        'Voidwalker Armor', '7526781-voidwalker-armor', 0, True, 'Rare', {
            'Special powers': 'As a Bonus Action while wearing the armor, project a translucent copy of yourself into an unoccupied space within 30 feet. It is immune to damage and conditions. Until the end of your turn, you can attack or cast non-Self-range spells as though you were in its space. The power recharges at dawn.',
            'Curse': 'Attunement curses you and makes you unwilling to part with the suit. Doffing leaves the curse in effect. At the end of each Long Rest, make a DC 11 Charisma saving throw. On a failure your soul is trapped in an object on another plane chosen by the DM, and your body is inert without aging or needing sustenance. Destroy the object or use Wish to restore your soul.',
            'Publication': 'The Book of Many Things, p. 39.',
        },
    ),
    'dndbeyond:7102410': (
        'Armor of Safeguarding', '7102410-armor-of-safeguarding', 0, True, 'Very Rare', {
            'Special powers': 'While worn, your Hit Point maximum increases by 10 + your level. Take a Magic action to cast Beacon of Hope. It lasts 1 minute without Concentration and recharges at dawn.',
            'Publication': 'Bigby Presents: Glory of the Giants, p. 111.',
        },
    ),
    'dndbeyond:7102439': (
        'Shield of the Blazing Dreadnought', '7102439-shield-of-the-blazing-dreadnought', 0, True, 'Legendary', {
            'Special powers': 'Use a Bonus Action to activate the shield for 1 minute. While active you have Immunity to Fire damage. Activation recharges at dawn.',
            'Cleansing Fire': 'While active, take a Magic action to end one disease or one of these conditions on a creature you can see within 30 feet, including yourself: Blinded, Charmed, Deafened, or Poisoned.',
            'Shield Bash': 'Once per turn while active, replace one attack in your Attack action with a bash against a creature you can see within 5 feet. It makes a Strength saving throw (DC 8 + your Proficiency Bonus + your Strength modifier). On a failure it takes 3d6 Bludgeoning plus 3d6 Fire damage and falls Prone. On a success it takes half damage only.',
            'Publication': 'Bigby Presents: Glory of the Giants, p. 116.',
        },
    ),
    'dndbeyond:7102441': (
        "Stonebreaker's Breastplate", '7102441-stonebreakers-breastplate', 0, True, 'Legendary', {
            'Special powers': 'While worn, you have Resistance to Bludgeoning, Piercing, and Slashing damage, and you cannot be knocked Prone. As a Magic action, cast Wall of Stone (save DC 14) with Advantage on saving throws to maintain Concentration on that casting. The spell use recharges at dawn.',
            'Publication': 'Bigby Presents: Glory of the Giants, p. 116.',
        },
    ),
    'dndbeyond:7102449': (
        'Zephyr Armor', '7102449-zephyr-armor', 0, True, 'Rare', {
            'Special powers': 'While worn, you have Advantage on Dexterity (Acrobatics) checks and Dexterity saving throws. Take a Magic action to cast Wind Wall (save DC 15). This use recharges at dawn.',
            'Publication': 'Bigby Presents: Glory of the Giants, p. 117.',
        },
    ),
    'dndbeyond:1752526': (
        'Molten Bronze Skin', '1752526-molten-bronze-skin', 0, True, 'Rare', {
            'Special powers': 'When you attune to the bronze, it conforms to your body. You can wear it under clothing. You choose when to remove it. While worn, you have Resistance to Fire damage and the armor imposes no Stealth disadvantage.',
            'Publication': 'Mythic Odysseys of Theros, p. 197.',
        },
    ),
    'dndbeyond:982693': (
        'Living Armor', '982693-living-armor', 1, True, 'Very Rare', {
            'Special powers': 'While worn, gain +1 AC and Resistance to Necrotic, Poison, and Psychic damage.',
            'Symbiosis': 'Wear the armor for the entire attunement period. While attuned, you cannot doff it or voluntarily end attunement. A spell that ends a curse on you ends the attunement and detaches it.',
            'Feeding': 'Immediately after each Long Rest, expend half your remaining Hit Point Dice (round up) or gain 1 level of Exhaustion.',
            'Publication': 'Eberron: Rising from the Last War, p. 278.',
        },
    ),
    'dndbeyond:382908': (
        'Mind Carapace Armor', '382908-mind-carapace-armor', 0, True, 'Uncommon', {
            'Special powers': 'Only the specific mind flayer or thrall for whom the armor was made can attune to it. That wearer gains Advantage on Intelligence, Wisdom, and Charisma saves and Immunity to the Frightened condition. For other wearers, use the underlying mundane armor rules.',
            'Publication': 'Volo’s Guide to Monsters, p. 81.',
            'Attunement': 'Only the specific mind flayer or thrall for whom it was made.',
        },
    ),
    'dndbeyond:382914': (
        'Shield of Far Sight', '382914-shield-of-far-sight', 0, False, 'Rare', {
            'Special powers': 'On the same plane, the mind flayer who made this shield can see through its eye, which has Darkvision to 60 feet. While looking through it, that mind flayer can use Mind Blast as though standing behind the shield. If it is destroyed, its maker is Blinded for 2d12 hours.',
            'Publication': 'Volo’s Guide to Monsters, p. 81.',
        },
    ),
    'dndbeyond:10886056': (
        'Repulsion Shield', '10886056-repulsion-shield', 1, False, 'Uncommon', {
            'Special powers': 'While wielding it, gain +1 AC in addition to its normal shield bonus. When a Large or smaller creature within 5 feet hits you with a melee attack roll, take a Reaction and spend 1 charge to push it up to 15 feet straight away. The shield has 4 charges and regains 1d4 spent charges at dawn.',
            'Publication': 'Eberron: Forge of the Artificer, p. 112.',
        },
    ),
    'dndbeyond:12467': (
        'Dragonguard', '12467-dragonguard', 1, False, 'Rare', {
            'Special powers': 'While wearing this breastplate, gain +1 AC and Advantage on saving throws against breath weapons used by creatures of the Dragon type.',
            'Publication': 'Lost Mine of Phandelver, p. 48.',
        },
    ),
    'dndbeyond:7247069': (
        'Dragonguard', '7247069-dragonguard', 1, False, 'Rare', {
            'Special powers': 'While wearing this breastplate, gain +1 AC and Advantage on saving throws against breath weapons used by creatures of the Dragon type.',
            'Publication': 'Phandelver and Below: The Shattered Obelisk, p. 72.',
        },
    ),
    'dndbeyond:5554585': (
        'Shield of the Silver Dragon', '5554585-shield-of-the-silver-dragon', 2, False, 'Unspecified', {
            'Special powers': 'While holding this shield, gain +2 AC in addition to its normal shield bonus. Its whispered warnings grant +2 to Initiative unless you are Incapacitated.',
            'Publication': 'Curse of Strahd, p. 68.',
        },
    ),
    'dndbeyond:351902': (
        "Heward's Hireling Armor", '351902-hewards-hireling-armor', 1, True, 'Very Rare', {
            'Special powers': 'While wearing the armor, gain +1 AC. Whenever you could draw or stow one one-handed weapon, you can draw or stow two instead.',
            'Pockets': 'Six extradimensional pockets each hold up to 20 lb and 2 cubic feet. The armor still weighs 10 lb. Use the normal rules to insert an item. Retrieving an item takes an action, and the requested item is always on top.',
            'Extradimensional hazard': 'Putting this armor into a Bag of Holding or another extradimensional storage space destroys both items and briefly opens a one-way gate. Creatures within 10 feet are pulled through to a random Astral Plane location.',
            'Publication': 'Lost Laboratory of Kwalish, p. 55.',
        },
    ),
    'dndbeyond:351912': (
        'Leather Golem Armor', '351912-leather-golem-armor', 1, True, 'Rare', {
            'Special powers': 'While worn, gain +1 AC and +1 to saving throws against spells and other magical effects. You are immune to effects that change your form. You have Resistance to Lightning damage and gain 5 Temporary Hit Points whenever you take Lightning damage.',
            'Curse': 'Attuning curses you and makes you unwilling to part with the armor until Remove Curse or similar magic breaks the curse. Taking Fire damage gives you Disadvantage on attack rolls and ability checks until the end of your next turn.',
            'Berserk': 'When you suffer a Critical Hit, roll a d6. On a 6, the armor cannot be removed and you go berserk. Each turn, attack the nearest creature you can see, moving toward it if needed. If none is reachable, attack an object, preferring one smaller than you. The effect ends if you are Incapacitated or another creature calms you with suitable magic or a successful DC 15 Charisma (Persuasion) check.',
            'Publication': 'Lost Laboratory of Kwalish, p. 55.',
        },
    ),
    'dndbeyond:351921': (
        'Powered Armor', '351921-powered-armor', 1, True, 'Legendary', {
            'Special powers': 'While worn, gain +1 AC and Advantage on death saving throws. Your Strength becomes 18 if it is lower.',
            'Power supply': 'The suit accepts one energy cell at a time and is found with an installed cell holding 2d10 charges. As a Bonus Action, spend 1 charge or sacrifice 5 HP to activate one mode.',
            'Defense and movement': 'Gain 2d6 + 5 Temporary Hit Points, or gain a 15-foot Fly Speed for 1 minute.',
            'Arm laser': 'Make a ranged weapon attack at +8 to hit against one target within 120 feet. On a hit, deal 2d6 Radiant damage.',
            'Utility modes': 'Translate up to 1,000 visible words in a nonmagical language over 1 minute, breathe normally in any environment for up to 1 hour, or gain Darkvision to 60 feet for up to 1 hour.',
            'Encounter variants': 'The adventure separately describes optional automatic defenses, possession, stasis, and alternative power sources for the DM.',
            'Publication': 'Lost Laboratory of Kwalish, p. 56. Kwalish’s attunement variant.',
        },
    ),
    'dndbeyond:342867': (
        'Shield of the Uven Rune', '342867-shield-of-the-uven-rune', 0, True, 'Very Rare', {
            'Special powers': 'While holding the shield, you are immune to Cold damage. Immediately after a creature hits you with a melee attack, take a Reaction to deal 3d6 Necrotic damage to it.',
            'Bane': 'Cast Bane from the shield (save DC 17). It lasts 1 minute without Concentration. The use returns after a Short or Long Rest.',
            'Gift of Vengeance': 'Trace the rune on a nonmagical weapon and work for 8 hours with both items within 5 feet of each other. The shield is destroyed. The weapon becomes a Rare +1 weapon requiring Attunement. At creation, choose Aberrations, Celestials, Constructs, Dragons, Elementals, Fey, Fiends, Giants, or Undead. The weapon’s attack and damage bonus is +3 against the chosen type.',
            'Identifying the rune': 'A successful DC 20 Intelligence (History) check identifies the Giant rune for enemy.',
            'Publication': 'Waterdeep: Dungeon of the Mad Mage, p. 299.',
        },
    ),
    'dndbeyond:8225886': (
        'Demon Skin', '8225886-demon-skin', 0, True, 'Rare', {
            'Special powers': 'On attunement, the pot disappears and the ichor conforms to your body. It fits beneath ordinary clothing, grants Resistance to Poison damage, and imposes no Stealth disadvantage. Only you can choose to remove it. On removal or your death, the pot reappears and the ichor returns to it.',
            'Publication': 'Descent into the Lost Caverns of Tsojcanth, p. 14.',
        },
    ),
    'dndbeyond:10674160': (
        'Spiked Shield', '10674160-spiked-shield', 0, True, 'Uncommon', {
            'Special powers': 'While holding the shield, you can replace one attack of the Attack action with a bash against a target within 5 feet. Add your Proficiency Bonus and Strength modifier to the attack roll. On a hit, deal 2d6 + your Strength modifier Piercing damage.',
            'Spike Salvo': 'As a Magic action, each creature in a 30-foot Cone makes a DC 13 Dexterity saving throw. It takes 3d6 Piercing damage on a failure or half on a success. This use recharges at dawn.',
            'Publication': 'Stranger Things: Welcome to the Hellfire Club, Spiked Shield.',
        },
    ),
    'dndbeyond:11914544': (
        'Spell-Fueling Armor', '11914544-spell-fueling-armor', 0, True, 'Very Rare', {
            'Special powers': 'While wearing the armor, you can treat each 1 on a spell damage die as a 2. After a Short Rest while wearing it, recover expended spell slots whose levels total 3 or less. This recovery recharges at dawn.',
            'Attunement': 'Required by a spellcaster.',
            'Publication': 'Arcana Unleashed: Deadfall, p. 119.',
        },
    ),
    'dndbeyond:11914433': (
        'Tramontane Armor', '11914433-tramontane-armor', 1, True, 'Very Rare', {
            'Special powers': 'While worn, gain +1 AC. The armor resembles scholarly or priestly robes. Heavy snow, ice, rubble and undergrowth that are Difficult Terrain cost you no extra movement.',
            'Grasping Tendrils': 'Use a Magic action to activate the armor for 1 minute, or use another Magic action to end the effect early. While active, as a Bonus Action choose creatures in a 20-foot Emanation centered on you. Each makes a DC 15 Strength save. On a failure it is Grappled (escape DC 15) and pulled up to 20 feet straight toward you. Activation recharges at dawn.',
            'Publication': 'Arcana Unleashed, p. 124.',
        },
    ),
    'dndbeyond:12133285': (
        'Defias Leather', '12133285-defias-leather', 0, False, 'Rare', {
            'Special powers': 'While worn, gain Advantage on Dexterity (Stealth) checks to hide behind stone objects and structures. You can cast Meld into Stone from the armor. The casting recharges at dawn.',
            'Publication': 'World of Warcraft, p. 108.',
        },
    ),
    'dndbeyond:12133294': (
        'Judgment Armor', '12133294-judgment-armor', 0, False, 'Legendary', {
            'Special powers': 'While wearing the armor, you gain the effects of Detect Evil and Good and Protection from Evil and Good without Concentration. A Paladin wearer can also extend the protection to creatures of their choice in their Aura of Protection.',
            'Publication': 'World of Warcraft, p. 110.',
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
             and item['mechanics'].get('armor')]
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
            shield = armor['name'] == 'Shield'
            fixed_base = PUBLIC_FIXED_BASES.get(name)
            if (fixed_base and armor['name'] not in fixed_base) or (not fixed_base and shield):
                continue
            cap = armor['ac_cap_dexmod']
            if name in METAL_ARMOR_FAMILIES and (
                armor['name'] == 'Hide Armor' or (armor['ac_add_dexmod'] and cap is None)
            ):
                continue
            mithral = name == 'Mithral Armor'
            stealth_exception = name in {'Scorpion Armor', 'Serpent Scale Armor', 'Molten Bronze Skin', 'Demon Skin'}
            uncapped_dexterity = name == 'Serpent Scale Armor'
            formula = str(armor['ac_base'] + bonus)
            if armor['ac_add_dexmod']:
                formula += ' + Dex modifier'
                if cap is not None and not uncapped_dexterity:
                    formula += f' (max +{cap})'
            training = ('Medium armor' if cap is not None else 'Light armor'
                        if armor['ac_add_dexmod'] else 'Heavy armor')
            if name in PUBLIC_TRAINING_LIMITS and training not in PUBLIC_TRAINING_LIMITS[name]:
                continue
            fields = {
                'Armor class bonus' if shield else 'Armor class': '+' + formula if shield else formula,
                'Training': 'Shield' if shield else training,
                'Strength requirement': 'None' if mithral else str(armor['strength_score_required'] or 'None'),
                'Stealth disadvantage': 'Yes' if armor['grants_stealth_disadvantage'] and not (mithral or stealth_exception) else 'No',
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
                **({'stealth_exception': True} if stealth_exception else {}),
                **({'uncapped_dexterity': True} if uncapped_dexterity else {}),
                'fields': fields, 'related_item': {'id': base['id'], 'label': 'Open 2024 base equipment'},
            })
        records[item['id']] = variants
    return records


LEGACY_ARMOR_COUNTERPARTS = {
    'dndbeyond:36571': ('dndbeyond:9228349', PUBLIC_ARMOR_RULES['dndbeyond:9228349']),
    'dndbeyond:36589': ('dndbeyond:9228382', PUBLIC_ARMOR_RULES['dndbeyond:9228382']),
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
