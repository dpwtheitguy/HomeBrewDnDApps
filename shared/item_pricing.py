"""Produce a complete, attributable market appraisal without replacing source values."""
import re
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from economy import bg3_style_quote
from item_enrichment import positive_amount

EQUIPMENT = 'https://www.dndbeyond.com/sources/dnd/br-2024/equipment'
MAGIC = 'https://www.dndbeyond.com/sources/dnd/br-2024/magic-items#MagicItemValuesbyRarity'
TRADE = 'https://bg3.wiki/wiki/Trading_and_item_pricing'
MASTERWORK = 'https://www.d20srd.org/srd/skills/craft.htm#creatingMasterworkItems'
LEGACY_ARMOR = 'https://www.d20srd.org/srd/equipment/armor.htm'
LEGACY_WEAPONS = 'https://www.d20srd.org/srd/equipment/weapons.htm'
RARITY = {'common': 100, 'uncommon': 400, 'rare': 4000, 'very-rare': 40000, 'legendary': 200000}
SCROLL_VALUES = (30, 50, 200, 300, 2000, 3000, 20000, 25000, 30000, 100000)
TYPE_VALUES = {
    'adventuring-gear': 5, 'alchemical-extracts': 5, 'alchemical-ingredients': 1, 'alchemy': 10,
    'ammunition': '.05', 'amulet': 15, 'armor': 45, 'belt': 2, 'book': 25, 'boots': 2,
    'cloak': 5, 'clothing': 2, 'consumable': 10, 'consumables': 10, 'container': 2,
    'dye': 1, 'food': '.5', 'furnishing': 10, 'gear': 5, 'gem': 50, 'gloves': 2, 'helmet': 10,
    'instrument': 25, 'item-set': 40, 'key': 1, 'material': 2, 'misc': 2, 'mount': 50,
    'other': 5, 'poison': 100, 'potion': 50, 'ring': 10, 'rod': 50, 'scroll': 50,
    'shield': 10, 'spellcasting-focus': 10, 'staff': 5, 'tools': 15, 'trade-good': 10,
    'wand': 25, 'weapon': 15, 'wondrous-item': 25,
    'construction-component': 15, 'structure': 1000, 'land-vehicle': 100,
    'waterborne-vehicle': 1000, 'air-vehicle': 5000, 'flying-vehicle': 5000,
}
METHODS = {
    'source': 'Source-listed base cost',
    'source-metadata': 'Source-reported value from catalog provenance',
    'source-sale': 'Source-reported resale value used as the base benchmark',
    'source-retail': 'Source-reported retail price used as the base benchmark',
    'existing-estimate': 'Existing catalog appraisal',
    'legacy-equipment': 'Comparable 3.5e equipment plus masterwork appraisal',
    'base-item': 'Estimate from a documented base item',
    'equipment-analogue': 'Estimate from comparable 2024 equipment',
    'barding-2024': '2024 barding at four times the base armor price',
    'bg3-comparable': 'Estimate from comparable BG3 catalog prices',
    'magic-rarity': '2024 magic-item rarity estimate',
    'scroll-level': '2024 scroll value based on scribing cost',
    'construction': 'Construction or installation estimate',
    'category': 'Low-confidence 2024 tabletop category appraisal',
    'exceptional': 'DM appraisal for an exceptional or priceless item',
}
CONSTRUCTION_TYPES = {'structure', 'construction-component'}
CONSTRUCTION_KINDS = {'structure', 'construction-component', 'integrated-weapon-system'}
CONSTRUCTION_PATTERNS = (
    (r'\b(?:citadel|fortress|castle|palace|step pyramid)\b', 5000),
    (r'\b(?:tower|gatehouse|temple|observatory|vault|keep)\b', 1000),
    (r'\b(?:room|hut|workshop|bridge|shrine|stairwell|kiln|furnace)\b', 150),
    (r'\b(?:portcullis|gate|lift|elevator|drawbridge)\b', 75),
    (r'\b(?:wall|floor|ceiling|roof|stair|foundation|column|palisade)\b', 15),
    (r'\b(?:trim|banner|mat|pile|torch|shelf|sign)\b', 5),
)
EQUIPMENT_TYPES = {'weapon', 'armor', 'shield', 'ammunition'}
UNIT_TYPES = {'ammunition', 'food', 'material', 'trade-good', 'construction-component'}
CRAFT_MARKER = re.compile(r'\b(?:masterwork|mastercrafted|mastercraft|master crafted)\b')
ART_MARKER = re.compile(r'\b(?:ornate|gilded|engraved|etched|carved|filigree|inlaid|decorated|embossed|painted|enamelled|enameled|work of art)\b')
JEWEL_MARKER = re.compile(r'\b(?:bejewell?ed|jewell?ed|gem studded|gem encrusted|gem set|jewel encrusted|jewel studded|jewel inlay)\b')
PRECIOUS_MARKER = re.compile(r'\b(?:diamond|ruby|emerald|sapphire|platinum)s?\b')
MASTERWORK_ARMOR_BASES = {
    'full plate': 1500, 'half plate': 600, 'banded mail': 250, 'splint mail': 200,
    'chainmail': 150, 'chain mail': 150, 'chain shirt': 100, 'breastplate': 200,
    'scale mail': 50, 'studded leather': 25, 'hide armor': 15, 'leather armor': 10,
    'padded armor': 5, 'buckler': 15, 'light wooden shield': 3, 'light steel shield': 9,
    'heavy wooden shield': 7, 'heavy steel shield': 20, 'tower shield': 30,
}
MASTERWORK_WEAPON_BASES = {
    'heavy repeating crossbow': 400, 'light repeating crossbow': 250, 'repeating crossbow': 250,
    'hand crossbow': 100, 'dire flail': 90, 'gnome hooked hammer': 20, 'two bladed sword': 100,
    'dwarven urgrosh': 50,
}


def amount(value):
    parsed = positive_amount(value)
    return Decimal(parsed) if parsed else None


def name_key(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value).casefold()).strip()


def rarity_key(item):
    return str(item.get('rarity') or '').lower().replace(' ', '-')


def construction(item):
    return item['type'] in CONSTRUCTION_TYPES or item.get('record_kind') in CONSTRUCTION_KINDS


def metadata_price(item):
    meta = item['mechanics'].get('reference_metadata') or {}
    for field in ('source_cost', 'source_stated_value'):
        entry = meta.get(field)
        if isinstance(entry, dict) and str(entry.get('currency')).lower() in ('gp', 'sp', 'cp', 'ep', 'pp'):
            value = amount(f"{entry.get('amount')} {str(entry['currency']).lower()}")
            if value:
                scope = entry.get('unit') or entry.get('scope')
                kind = entry.get('kind') or field
                method = {'source-buyer-offer': 'source-sale',
                          'source-retail-price': 'source-retail'}.get(kind, 'source-metadata')
                note = ' · '.join(filter(None, (kind.replace('-', ' '), scope)))
                return value, method, note
    for field in ('source_market_price_gp', 'source_base_value_gp', 'source_unit_value_gp', 'source_sale_gp'):
        value = amount(meta.get(field))
        if value:
            method = 'source-sale' if field == 'source_sale_gp' else 'source-metadata'
            note = field.removeprefix('source_').removesuffix('_gp').replace('_', ' ')
            if field == 'source_sale_gp' and meta.get('source_sale_unit'):
                note += ' per ' + str(meta['source_sale_unit'])
            return value, method, note
    if value := amount(f"{meta.get('source_face_value_sp')} sp"):
        return value, 'source-metadata', 'Face value'
    # Free-text fan lists can contain multiple prices, units, rewards and cost formulas.
    # Only an unqualified single coin amount is an eligible source value.
    reported = meta.get('reported_source_cost')
    if isinstance(reported, str) and re.fullmatch(r'\s*[\d,]+(?:\.\d+)?\s*(?:cp|sp|ep|gp|pp)\s*', reported, re.I):
        value = amount(reported.strip().lower())
        if value:
            return value, 'source-metadata', 'Reported legacy or fan price'
    return None


def source_price(item):
    values = (item.get('valuation') or {}).get('base_values') or []
    for entry in values:
        value = amount(entry.get('amount_gp'))
        if value:
            status = entry.get('status') or ''
            method = 'existing-estimate' if status in ('author-estimate', '2024-base-item-reference-price') else 'source'
            return value, method, entry.get('economy_id') or item['ruleset'], entry.get('context') or ''
    metadata = metadata_price(item)
    if metadata:
        value, method, note = metadata
        return value, method, item['ruleset'], note
    return None


def normalized_type(item):
    if item['type'] in ('misc', 'weapon') and (item['mechanics'].get('source_type') or '').lower() in ('ammo', 'ammunition'):
        return 'ammunition'
    return item['type']


def scope_for(item, kind):
    if item.get('record_kind') == 'trade-category':
        return 'Illustrative unit or lot; quantity and quality vary'
    if construction(item):
        return 'One listed component or project; excludes land and site adjustments'
    if kind in UNIT_TYPES:
        return 'One listed item or bundle'
    return 'One listed item'


def scroll_level(item):
    data = (item['mechanics'].get('reference_metadata') or {}).get('inscribed_spell') or {}
    value = data.get('level')
    if value is None:
        match = re.search(r'\b([1-9])(?:st|nd|rd|th)?[ -]+level\b', item['name'], re.I)
        value = int(match[1]) if match else None
    return value if type(value) is int and 0 <= value <= 9 else None


def money(number):
    value = max(Decimal('.01'), number.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    return format(value.normalize(), 'f')


def decoration_premium(item, kind, physical_cost):
    if kind not in {'weapon', 'armor', 'shield', 'helmet'}:
        return None
    reference = item['mechanics'].get('reference_metadata') or {}
    evidence = name_key(' '.join(filter(None, (
        item['name'], str(reference.get('source_note') or '')[:300], (item.get('description') or '')[:300]
    ))))
    if item['ruleset'] in ('dnd-3e', 'dnd-3.5') and CRAFT_MARKER.search(evidence):
        value = Decimal(300 if kind == 'weapon' else 150)
        return value, '3.5e masterwork price benchmark', MASTERWORK
    if JEWEL_MARKER.search(evidence):
        if PRECIOUS_MARKER.search(evidence):
            return physical_cost, 'Precious gemstone ornament · +100%', None
        return physical_cost / 2, 'Jewelled ornament · +50%', None
    if ART_MARKER.search(evidence) or CRAFT_MARKER.search(evidence):
        return physical_cost / 5, 'Decorative workmanship · +20%', None
    return None


def legacy_masterwork_base(item, kind):
    choices = MASTERWORK_WEAPON_BASES if kind == 'weapon' else MASTERWORK_ARMOR_BASES
    title = name_key(item['name'])
    for label, cost in choices.items():
        if re.search(r'\b' + re.escape(label) + r'\b', title):
            if label == 'repeating crossbow':
                label = 'light repeating crossbow comparison'
            return Decimal(cost), label, LEGACY_WEAPONS if kind == 'weapon' else LEGACY_ARMOR
    return None


def price_catalog(items, curated=None):
    by_id = {item['id']: item for item in items}
    direct = {item['id']: source_price(item) for item in items}
    barding_prices = {}
    for item_id, entries in (curated or {}).items():
        for entry in entries:
            if not entry.get('barding') or entry.get('profile_kind') != 'published-armor-mapping':
                continue
            base_id = entry['related_item']['id']
            base = by_id[base_id]
            if (item_id not in by_id or base['source_id'] != 'open5e-srd-2024' or base['magic']
                    or base['type'] != 'armor' or direct[base_id] is None):
                raise ValueError(f'Invalid 2024 barding price basis for {item_id}')
            barding_prices[item_id] = (
                4 * direct[base_id][0], 'barding-2024', 'dnd-2024-appraisal',
                f"Four times the 2024 price of {base['name']}",
            )
    exact = defaultdict(set)
    equipment = {}
    bg3_comparables = defaultdict(list)
    for item in items:
        source = direct[item['id']]
        if not source:
            continue
        kind = normalized_type(item)
        if item['source_id'] == 'open5e-srd-2024' and item.get('magic') is False:
            key = name_key(item['name'])
            exact[kind, key].add(source[0])
            mechanics = item['mechanics']
            if key and ((kind == 'weapon' and mechanics.get('weapon'))
                        or (kind in ('armor', 'shield') and mechanics.get('armor'))):
                equipment[kind, key] = source[0]
        if item['ruleset'] == 'bg3' and source[3] == 'standard':
            bg3_comparables[kind, rarity_key(item)].append(source[0])
            bg3_comparables[kind, None].append(source[0])
    equipment_patterns = defaultdict(list)
    for (kind, key), value in sorted(equipment.items(), key=lambda row: -len(row[0][1])):
        equipment_patterns[kind].append((re.compile(r'\b' + re.escape(key) + r'\b'), key, value))

    def estimate(item, kind):
        rarity = rarity_key(item)
        key = name_key(item['name'])
        if construction(item):
            patterns = CONSTRUCTION_PATTERNS
            if kind == 'construction-component':
                patterns = patterns[3:] + patterns[:3]
            value = next((value for pattern, value in patterns if re.search(pattern, key)), TYPE_VALUES[kind])
            return Decimal(value), 'construction', 'dnd-2024-appraisal', 'Size and component type'
        if rarity == 'artifact':
            return Decimal(200000), 'exceptional', 'dnd-2024-appraisal', 'Illustrative DM appraisal; the 2024 guideline calls artifacts priceless'
        if item['ruleset'] == 'bg3':
            comparable = bg3_comparables[kind, rarity]
            if len(comparable) < 3:
                comparable = bg3_comparables[kind, None]
            if comparable:
                return median(comparable), 'bg3-comparable', 'bg3', f'Median of {len(comparable)} comparable listed prices'
        base_id = item.get('base_item_id')
        base_item = by_id.get(base_id)
        base = direct.get(base_id)
        base_cost = base[0] if base and base_item['ruleset'] == 'dnd-2024' else None
        analogue = next(((label, value) for pattern, label, value in equipment_patterns[kind] if pattern.search(key)), None)
        if kind == 'scroll' and (level := scroll_level(item)) is not None:
            return Decimal(SCROLL_VALUES[level]), 'scroll-level', 'dnd-2024-appraisal', f'Spell level {level}; twice the scribing cost'
        clearly_magic = (item.get('magic') is True or 'magic' in item.get('tags', [])
                         or item['source_id'] == 'dndbeyond-public-index'
                         or rarity in ('uncommon', 'rare', 'very-rare', 'legendary'))
        if rarity in RARITY and clearly_magic and item.get('magic') is not False:
            value = Decimal(RARITY[rarity])
            if kind in ('potion', 'poison', 'consumable', 'consumables', 'ammunition') or re.match(r'ammunition\b', key):
                value /= 2
            if kind in EQUIPMENT_TYPES:
                value += base_cost or (analogue[1] if analogue else Decimal(0))
            return value, 'magic-rarity', 'dnd-2024-appraisal', f'{rarity.replace("-", " ").title()} rarity guideline'
        if base_cost is not None:
            return base_cost, 'base-item', 'dnd-2024-appraisal', base_item['name']
        exact_values = exact[kind, key]
        if item.get('magic') is not True and len(exact_values) == 1:
            return next(iter(exact_values)), 'equipment-analogue', 'dnd-2024-appraisal', 'Same equipment name in 2024 SRD'
        if analogue and item.get('magic') is not True:
            return analogue[1], 'equipment-analogue', 'dnd-2024-appraisal', 'Comparable ' + analogue[0]
        value = Decimal(TYPE_VALUES.get(kind, 5))
        if kind == 'ammunition' and re.search(r'\b(?:ice|fire|acid|lightning|cold|thunder|slaying|poison)\b', key):
            value = Decimal(50)
        if clearly_magic and value < 100 and kind not in ('potion', 'ammunition', 'scroll', 'poison', 'consumable', 'consumables'):
            value = Decimal(100)
        return value, 'category', 'dnd-2024-appraisal', 'Typical ' + kind.replace('-', ' ') + ' benchmark'

    records = {}
    counts = Counter()
    ornament_counts = Counter()
    for item in items:
        kind = normalized_type(item)
        value, method, economy, basis = direct[item['id']] or barding_prices.get(item['id']) or estimate(item, kind)
        ornament = None
        if direct[item['id']] is None and not construction(item):
            # A decoration only increases the physical item's appraisal. Any magical
            # rarity premium stays outside the percentage calculation.
            physical_cost = value
            if method in ('magic-rarity', 'exceptional'):
                key = name_key(item['name'])
                base = direct.get(item.get('base_item_id'))
                physical_cost = base[0] if base and base[2] == 'dnd-2024' else next(
                    (cost for pattern, _, cost in equipment_patterns[kind] if pattern.search(key)),
                    Decimal(TYPE_VALUES.get(kind, 5)),
                )
            premium = decoration_premium(item, kind, physical_cost)
            if premium:
                increment, label, source = premium
                base_source = None
                legacy = legacy_masterwork_base(item, kind) if source == MASTERWORK and method != 'magic-rarity' else None
                if legacy:
                    physical_cost, basis, base_source = legacy
                    value = physical_cost
                    method = 'legacy-equipment'
                    economy = 'dnd-3.5-appraisal'
                increment = Decimal(money(increment))
                ornament = {'premium_gp': money(increment), 'physical_base_gp': money(physical_cost), 'label': label}
                if source:
                    ornament['source_url'] = source
                if base_source:
                    ornament['base_source_url'] = base_source
                value += increment
                ornament_counts[label] += 1
        if construction(item):
            buy, sell = value * Decimal('1.25'), value / 2
            policy = 'construction-appraisal'
        else:
            quote = bg3_style_quote(value)
            buy = value if method == 'source-retail' else Decimal(quote['buy_estimate_gp'])
            sell = value if method == 'source-sale' else Decimal(quote['sell_estimate_gp'])
            policy = {'source-sale': 'source-resale-and-bg3-buy',
                      'source-retail': 'source-retail-and-bg3-sell'}.get(method, 'bg3-style-v1')
        appraisal_only = rarity_key(item) in ('story', 'artifact') or construction(item) or item.get('record_kind') == 'trade-category'
        records[item['id']] = {
            'base_cost_gp': money(value), 'base_buy_gp': money(buy), 'base_sell_gp': money(sell),
            'economy_id': economy, 'method': method, 'basis': basis, 'policy': policy,
            'scope': scope_for(item, kind), 'appraisal_only': appraisal_only,
        }
        if ornament:
            records[item['id']]['decoration'] = ornament
        counts[method] += 1
    return {
        'schema_version': 1, 'records': records, 'method_labels': METHODS, 'counts': dict(counts),
        'decoration_counts': dict(ornament_counts),
        'references': {'equipment': EQUIPMENT, 'magic_items': MAGIC, 'trading': TRADE, 'masterwork': MASTERWORK},
    }
