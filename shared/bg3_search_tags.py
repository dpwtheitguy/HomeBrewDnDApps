"""BG3 search classifications from game facts, independent of tabletop magic."""
import re

EQUIPMENT = {'armor', 'shield', 'clothing', 'amulet', 'boots', 'gloves', 'helmet',
             'ring', 'cloak', 'belt', 'wand', 'staff', 'rod', 'instrument', 'wondrous-item'}
ORDINARY = {'book', 'food', 'key', 'container', 'dye', 'material'}
DAMAGE = {'acid', 'bludgeoning', 'cold', 'fire', 'force', 'lightning', 'necrotic',
          'piercing', 'poison', 'psychic', 'radiant', 'slashing', 'thunder'}


def tag_bg3_item(item, weapons, details):
    if item['ruleset'] != 'bg3':
        return
    item_id = item['id']
    weapon_variants = weapons.get(item_id, {}).get('variants', [])
    item_variants = details.get(item_id, {}).get('variants', [])
    templates = item['mechanics'].get('bg3_template_variants', [])
    tags = set(item['tags'])
    evidence = set()
    for variant in templates:
        facts = variant['facts']
        if re.fullmatch(r'\+?[1-9]\d*', str(facts.get('enchantment', '')).strip()):
            evidence.add('enchantment')
            if variant['template'] == 'weaponpage':
                tags.add('property:enchanted')
        if variant['template'] == 'weaponpage':
            for field in ('finesse', 'light', 'heavy', 'reach', 'thrown', 'dippable', 'ammunition', 'loading'):
                if facts.get(field, '').strip().lower() in ('yes', 'true', '1'):
                    tags.add('property:' + field)
            handedness = facts.get('handedness', '').strip().lower()
            if handedness in ('one-handed', 'two-handed', 'versatile'):
                tags.add('property:' + handedness)
            weapon_range = facts.get('melee or ranged', '').strip().lower()
            if weapon_range in ('melee', 'ranged'):
                tags.add('property:' + weapon_range)
        for field in ('damage type', 'damage2 type'):
            damage = facts.get(field, '').strip().lower()
            if damage in DAMAGE:
                tags.add('damage:' + damage)
    for variant in weapon_variants:
        if any(group != 'weapon actions' and entries for group, entries in variant['features'].items()):
            evidence.add('additional-weapon-ability')
            tags.add('property:special')
        if variant['stats'].get("can't dual wield", '').strip().lower() in ('y', 'yes', 'true', '1'):
            tags.add('property:cant-dual-wield')
        if variant['special_stats'] and item.get('rarity') in ('uncommon', 'rare', 'very rare', 'legendary'):
            evidence.add('unusual-weapon-effect')
    for variant in item_variants:
        for line in variant['facts'].get('Damage', []):
            for damage in DAMAGE:
                if re.search(r'\b' + damage + r'\b', line, re.I):
                    tags.add('damage:' + damage)
        has_effect = variant['has_rule_text'] or variant['effects'] or variant['conditions']
        if has_effect and item['type'] in {'ammunition', 'potion', 'scroll'}:
            evidence.add('special-consumable')
        if has_effect and item['type'] in EQUIPMENT and any(t['template'] == 'equipmentpage' for t in templates):
            evidence.add('equipment-effect')
    if evidence:
        tags.add('magic')
        item['mechanics']['bg3_search_classification'] = {'magic': True, 'basis': sorted(evidence)}
    elif (item['type'] in ORDINARY and not any(v['has_rule_text'] for v in item_variants)
          or weapon_variants and item.get('rarity') in (None, 'common')):
        tags.add('mundane')
        item['mechanics']['bg3_search_classification'] = {'magic': False, 'basis': ['ordinary-game-item']}
    item['tags'] = sorted(tags)
