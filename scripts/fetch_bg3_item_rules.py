#!/usr/bin/env python3
"""Project structured rule and location facts from BG3 item templates."""
import argparse
import json
import re

from fetch_bg3 import OUT, extract_templates
from fetch_bg3_weapon_rules import feature_field, fetch_batches, names, simple

DESTINATION = OUT.parent.parent / 'supplements' / 'bg3-item-rules.json'
FIELDS = {
    'name', 'type', 'usage cost', 'single use', 'camp supplies', 'hp', 'weight kg',
    'armour class', 'armour class bonus', 'armour type', 'proficiency', 'stealth disadvantage',
    'enchantment', 'passives', 'passives main hand', 'passives off hand', 'effect', 'special',
    'area', 'area shape', 'area range m', 'area range ft', 'area duration', 'book author',
}
LOCATION_FIELDS = re.compile(r'where to find\d*(?: location| x| y)?$')
CONDITION_FIELDS = re.compile(r'condition\d*(?: duration| save| dc| radius m| radius ft)?$')
WIKI_LINK = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?]]')
NAMED_EFFECT = re.compile(r'\{\{(?:SpellAction|SmSAI|SAI|SmCond|Cond|PassiveLink)\s*\|\s*([^|{}]+)', re.I)
MARKUP = re.compile(r'\{\{([a-z ]+)\s*\|([^{}]+)}}', re.I)
DICE = re.compile(r'(?:\d+d\d+|\d+)(?:\s*[+-]\s*\d+)?$', re.I)
SAVE = re.compile(r'\{\{Saving ?Throw\s*\|\s*([a-z]+)(?:\|[^{}]+)?}}(?:[^\n]{0,100}?\bDC\s*(\d+))?', re.I)


def allowed(field):
    return field in FIELDS or bool(LOCATION_FIELDS.fullmatch(field) or CONDITION_FIELDS.fullmatch(field))


def unique(values):
    return list(dict.fromkeys(values))


def scalar(value):
    if re.search(r'[{}<>\n]', value):
        return None
    return simple(value)


def project_markup(text):
    facts = {}
    for template, value in MARKUP.findall(text):
        args = [arg.strip() for arg in value.split('|')]
        params = {arg.split('=', 1)[0].strip(): arg.split('=', 1)[1].strip() for arg in args if '=' in arg}
        kind = template.replace(' ', '').lower()
        if kind in ('damagetext', 'heal', 'healing') and DICE.fullmatch(args[0]):
            label = 'Damage' if kind == 'damagetext' else 'Healing'
            result = ' '.join(arg for arg in args[:2] if re.fullmatch(r'[\w +.-]+', arg))
        elif kind in ('range', 'aoe', 'radius'):
            label = 'Range' if kind == 'range' else 'Area'
            result = ' / '.join(params[unit] + ' ' + unit for unit in ('m', 'ft')
                                if re.fullmatch(r'\d+(?:\.\d+)?', params.get(unit, '')))
            if not result and kind == 'range':
                result = {'ranged': '18 m / 60 ft', 'short ranged': '15 m / 50 ft',
                          'melee': '1.5 m / 5 ft', 'self': 'Self', 'touch': 'Touch',
                          'weapon': 'Weapon range', 'reach': '2.5 m / 8 ft'}.get(args[0].lower(), '')
            if result and kind != 'range' and (kind == 'radius' or any(arg.lower() == 'radius' for arg in args)):
                result += ' radius'
        elif kind == 'ability' and (stat := re.search(
                r'\{\{Ability\|' + re.escape(args[0]) + r'}}\s*([+-]\s*\d+)', text, re.I)):
            label = args[0].title()
            result = stat.group(1)
        else:
            continue
        if result:
            facts.setdefault(label, []).append(result)
    if re.search(r'\{\{InfoBlob\|Weapon Damage}}', text, re.I):
        facts.setdefault('Damage', []).insert(0, 'Weapon damage')
    for ability, dc in SAVE.findall(text):
        facts.setdefault('Saving throw', []).append((f'DC {dc} ' if dc else '') + ability.title())
    for ability, score in re.findall(
            r"set [^.\n]{0,45}?\{\{Ability\|([a-z]+)}} score to (\d+)", text, re.I):
        facts.setdefault(ability.title(), []).append('At least ' + score)
    for amount in re.findall(r'\[\[[^\]]*\|(?:Attack Rolls?|Attacks?)]]\s*([+-]\s*\d+)', text, re.I):
        facts.setdefault('Attack rolls', []).append(amount)
    return {label: unique(values) for label, values in facts.items()}


def project(raw):
    rules = '\n'.join(raw.get(key, '') for key in ('effect', 'special'))
    findings = '\n'.join(value for key, value in raw.items() if re.fullmatch(r'where to find\d*', key))
    locations = []
    for key, value in raw.items():
        if re.fullmatch(r'where to find\d* location', key) and (place := scalar(value)):
            root = key.removesuffix(' location')
            coordinates = [raw.get(root + ' ' + axis, '') for axis in ('x', 'y')]
            if all(re.fullmatch(r'-?\d+', coordinate) for coordinate in coordinates):
                place += f' ({coordinates[0]}, {coordinates[1]})'
            locations.append(place)
    tags = [simple(match.strip()) for match in NAMED_EFFECT.findall(rules)]
    for key in ('passives', 'passives main hand', 'passives off hand'):
        tags.extend(names(raw.get(key, '')))
    conditions = {key: scalar(value) for key, value in raw.items() if CONDITION_FIELDS.fullmatch(key)}
    recipe = []
    for line in findings.splitlines():
        if not re.search(r'\b(?:craft(?:ed|ing)?|alchemy|combine|extract)\b', line, re.I):
            continue
        recipe.extend(simple(match) for match in re.findall(
            r'\{\{(?:SmItemIcon|SmRarityItem|RarityItem)\|([^|{}]+)', line, re.I))
    return {
        'stats': {key: value for key in sorted(FIELDS - {'effect', 'special', 'passives', 'passives main hand', 'passives off hand'})
                  if key in raw and (value := scalar(raw[key]))},
        'facts': project_markup(rules),
        'effects': unique(tags),
        'conditions': {key: value for key, value in conditions.items() if value},
        'locations': unique(locations),
        'acquisition_refs': unique(simple(match) for match in WIKI_LINK.findall(findings))[:20],
        'recipe_refs': unique(recipe),
        'has_rule_text': bool(rules.strip()),
    }


def fetch_items():
    indexes = [OUT / f'{kind}-pages.json' for kind in ('equipment', 'misc')]
    ids = sorted({row['pageid'] for path in indexes for row in json.loads(path.read_text())})
    output = {}
    for batch, _ in fetch_batches(ids, 'pageids'):
        for page in batch:
            if 'revisions' not in page:
                continue
            revision = page['revisions'][0]
            templates = extract_templates(revision['slots']['main']['content'], {'equipmentpage', 'miscitempage'}, allowed)
            if templates:
                output[f'bg3-wiki:{page["pageid"]}'] = {
                    'revision': revision['revid'],
                    'variants': [project(row['facts']) for row in templates],
                }
    return output


def fetch_effects(items):
    wanted = sorted({effect for item in items.values() for variant in item['variants']
                     for effect in variant['effects'] if not re.search(r'[\[\]{}<>|]', effect)})
    output = {}
    for batch, aliases in fetch_batches(wanted, 'titles'):
        for page in batch:
            if 'revisions' not in page:
                continue
            revision = page['revisions'][0]
            templates = extract_templates(revision['slots']['main']['content'],
                {'featurepage', 'passivefeaturepage', 'conditionpage', 'spellpage', 'actionpage'},
                lambda key: key == 'description' or feature_field(key))
            if not templates:
                continue
            raw = templates[0]['facts']
            stats = {key: value for key in raw if key != 'description' and (value := scalar(raw[key]))}
            facts = project_markup(raw.get('description', ''))
            if not stats and not facts:
                continue
            entry = {'title': page['title'], 'revision': revision['revid'], 'stats': stats, 'facts': facts}
            output[page['title']] = entry
            for alias, title in aliases.items():
                if title == page['title']:
                    output[alias] = entry
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-items', action='store_true', help='Keep the existing item projections and fetch referenced effects')
    args = parser.parse_args()
    items = json.loads(DESTINATION.read_text())['records'] if args.reuse_items else fetch_items()
    effects = fetch_effects(items)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps({'schema_version': 1, 'records': items, 'effects': effects},
                                      ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'Projected facts from {len(items)} BG3 equipment and misc pages and {len(effects)} linked effects.')


if __name__ == '__main__':
    main()
