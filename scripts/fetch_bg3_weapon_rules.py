#!/usr/bin/env python3
"""Fetch revision-pinned BG3 weapon stats and structured feature facts."""
import json
import re
from pathlib import Path

from fetch_bg3 import OUT, extract_templates, request

DESTINATION = OUT.parent.parent / 'supplements' / 'bg3-weapon-rules.json'
WEAPON_FIELDS = {
    'uid', 'uuid', 'name', 'category', 'melee or ranged', 'handedness', 'type',
    'enchantment', 'damage', 'damage type', 'versatile damage', 'range', 'range m', 'range ft',
    'finesse', 'light', 'heavy', 'reach', 'thrown', 'dippable', 'ammunition', 'loading', "can't dual wield", 'weight kg',
    'passives', 'passives main hand', 'passives off hand', 'weapon actions', 'special weapon actions',
    'special', 'condition', 'condition duration', 'condition save', 'condition dc',
}
FEATURE_FIELDS = {
    'type', 'cost', 'recharge', 'duration', 'range', 'range m', 'range ft', 'aoe', 'aoe m',
    'aoe ft', 'targets', 'save', 'save dc', 'attack roll', 'variants', 'condition',
    'condition duration', 'condition save', 'condition dc', 'damage', 'damage type', 'damage info',
}
FEATURE_LISTS = ('passives', 'passives main hand', 'passives off hand', 'weapon actions',
                 'special weapon actions', 'condition')
SPECIAL_LINK = re.compile(r'\{\{(?:SpellAction|SAI|SmSAI|Passive|PassiveLink|Cond|SmCond)\s*\|\s*([^|{}]+)', re.I)
DAMAGE_TEMPLATE = re.compile(r'\{\{DamageText\|([0-9]+d[0-9]+|[0-9]+)\|([a-zA-Z ]+)(?:\|[^{}]+)?}}', re.I)
SPECIAL_STAT = re.compile(r'\{\{(Skill\|[^|{}]+|ArmourClass)\}\}\s*([+-]\s*\d+)\s*(\([^()\n]+\))?', re.I)
SPECIAL_WEAPONS = {
    'Harmonium Halberd': 'Strength +2, to a maximum of 23. Intelligence and Wisdom each decrease by 1.',
    "Handmaiden's Mace": 'Sets Strength to at least 18.',
    "Assassin's Shortsword": 'Grants advantage on Stealth checks.',
    'Blood-Bound Blade': 'Its magic requires an Eldritch Knight bond or a Warlock pact bond.',
    'Charge-Bound Warhammer': 'An Eldritch Knight bond or Warlock pact or hex bond activates its extra magic. The bound attack and damage bonus stacks with its innate +1.',
    'Cold Snap': 'Grants +1 AC in the off hand.',
    'Rebound Battleaxe': 'Its magic requires an Eldritch Knight bond or a Warlock pact bond.',
    'Watcher Greatsword': 'Only Steel Watchers can wield it.',
    'Watcher Crossbow': 'Only Steel Watchers can wield it.',
    'Heavy Spiked Club': 'Humanoids cannot wield it.',
    'Shortsword (Yurgir)': 'Humanoids cannot wield it.',
    'Hand Crossbow (Yurgir)': 'Humanoids cannot wield it.',
    'Gnarled Tree Branch': 'Humanoids cannot wield it.',
    'Greatclub (Minotaur)': 'Humanoids cannot wield it.',
    'Chaos Flail': 'Only Gnolls can equip it.',
    "Wulbren's Hammer": 'Deals 2d4 Force damage to items and objects.',
    'Moonblade': 'Adds +1 to melee attack rolls.',
}
INLINE_FEATURES = {
    'Ruptured': 'Lasts three turns. Movement deals 1d4 Piercing per metre and reduces the remaining duration by one each time damage triggers.',
    'Moonshield': 'Protects against the Shadow Curse within the lantern’s 13 m aura.',
    'Ironwood Harmony': 'Adds 1d4 Bludgeoning damage while Shillelagh is active on the club.',
    'Scarlet Remittance +3': 'Kills of living hostile targets add +1 to attacks, damage, and spell save DC, up to +3. Scarlet Regeneration can spend the full bonus to restore 3d10 HP once per Long Rest.',
}


# Condition pages whose descriptions fall outside the structured template fields.
REVIEWED_CONDITIONS = {
    'Momentum': (444042,
        'Gain 5 ft of movement speed per remaining turn, up to five turns. Reapplication adds duration and it ticks down at the end of each turn. In the current game, Slowed ends it early.'),
    'Moonshield': (444051,
        'The light from a Moonlantern or Shadow Lantern protects affected creatures from the Shadow Curse.'),
    'Madness': (443956,
        'The affected creature becomes hostile to nearby creatures. The game AI takes control of affected party members.'),
    'Ironwood Harmony': (443867,
        'The club deals an extra 1d4 Bludgeoning damage while imbued with Shillelagh.'),
}


def simple(value):
    value = re.sub(r'\[\[([^]|]+)\|([^]]+)]]', r'\2', value)
    value = re.sub(r'\[\[([^]]+)]]', r'\1', value)
    return re.sub(r"'{2,5}", '', value).strip()


def names(value):
    return list(dict.fromkeys(
        simple(part) for part in value.split(',')
        if part.strip() and not re.search(r'[{}<>\n]', part)
    ))


def fetch_batches(values, field):
    for offset in range(0, len(values), 45):
        response = request({'action': 'query', 'prop': 'revisions', 'redirects': 1,
                            field: '|'.join(map(str, values[offset:offset + 45])),
                            'rvprop': 'ids|content', 'rvslots': 'main'})['query']
        aliases = {row['from']: row['to'] for row in response.get('redirects', [])}
        aliases.update({row['from']: row['to'] for row in response.get('normalized', [])})
        yield response['pages'], aliases


def feature_field(key):
    return key in FEATURE_FIELDS or bool(re.fullmatch(
        r'(?:damage|condition) \d+(?: (?:type|info|duration|save|dc))?', key
    ))


def main():
    pages = json.loads((OUT / 'weapon-pages.json').read_text())
    summaries = json.loads((OUT / "weapon-feature-summaries.json").read_text())
    weapons = {}
    feature_names = set()
    inline_revisions = {}
    for batch, _ in fetch_batches([row['pageid'] for row in pages], 'pageids'):
        for page in batch:
            if 'revisions' not in page:
                continue
            revision = page['revisions'][0]
            variants = []
            for template in extract_templates(revision['slots']['main']['content'], {'weaponpage'}, WEAPON_FIELDS.__contains__):
                raw = template['facts']
                groups = {field: names(raw[field]) for field in FEATURE_LISTS if field in raw}
                special = raw.get('special', '')
                groups['special'] = list(dict.fromkeys(match.strip() for match in SPECIAL_LINK.findall(special)))
                special_stats = [
                    ' '.join(filter(None, (label.split('|')[-1] if '|' in label else 'Armor Class', amount, qualifier)))
                    for label, amount, qualifier in SPECIAL_STAT.findall(special)
                ]
                if special and page['title'] in SPECIAL_WEAPONS:
                    special_stats.append(SPECIAL_WEAPONS[page['title']])
                for group in groups.values():
                    feature_names.update(group)
                    for title in group:
                        if title in INLINE_FEATURES:
                            inline_revisions.setdefault(title, revision['revid'])
                variants.append({
                    'stats': {key: simple(value) for key, value in raw.items()
                              if key not in FEATURE_LISTS and key != 'special' and not re.search(r'[{}<>]', value)},
                    'features': {key: group for key, group in groups.items() if group},
                    'special_stats': special_stats,
                    'unparsed_special': bool(special and not (groups['special'] or special_stats)),
                })
            if variants:
                weapons[f'bg3-wiki:{page["pageid"]}'] = {'revision': revision['revid'], 'variants': variants}
    features = {}
    remaining = feature_names
    for _ in range(3):
        if not remaining:
            break
        discovered = set()
        for batch, aliases in fetch_batches(sorted(remaining), 'titles'):
            for page in batch:
                title = page['title']
                if 'revisions' not in page:
                    continue
                revision = page['revisions'][0]
                templates = extract_templates(revision['slots']['main']['content'],
                    {'featurepage', 'passivefeaturepage', 'conditionpage', 'weaponactionpage', 'spellpage', 'actionpage'},
                    lambda key: key == 'description' or feature_field(key))
                raw = templates[0]['facts'] if templates else {}
                facts = {key: simple(value) for key, value in raw.items()
                         if key != 'description' and not re.search(r'[{}<>]', value)}
                extra_damage = [' '.join(match) for match in DAMAGE_TEMPLATE.findall(raw.get('description', ''))] if not any(k.startswith('damage') for k in facts) else []
                if 'variants' in facts:
                    discovered.update(names(facts['variants']))
                entry = {'title': title, 'revision': revision['revid'], 'facts': facts, 'extra_damage': extra_damage}
                if title in summaries:
                    entry['summary'] = summaries[title]
                reviewed = REVIEWED_CONDITIONS.get(title)
                if reviewed and revision['revid'] == reviewed[0]:
                    entry.setdefault('summary', reviewed[1])
                features[title] = entry
                for alias, target in aliases.items():
                    if target == title:
                        features[alias] = entry
        remaining = discovered - features.keys()
    for title, revision in inline_revisions.items():
        features.setdefault(title, {'title': title, 'revision': revision, 'facts': {},
                                    'extra_damage': [], 'summary': INLINE_FEATURES[title]})
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps({'schema_version': 1, 'source': 'https://bg3.wiki/wiki/Template:Weapon_page',
                                      'weapons': weapons, 'features': features}, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(weapons)} weapons, {len(features)} feature titles, {len(feature_names - features.keys())} unresolved links')


if __name__ == '__main__':
    main()
