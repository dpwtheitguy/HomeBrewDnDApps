#!/usr/bin/env python3
"""Check catalog filter composition against the running Android WebView and shared data."""
import argparse
import collections
import json
import re
import sqlite3
import string
import subprocess
import unicodedata
import urllib.request
from decimal import Decimal
from pathlib import Path

from websocket import create_connection

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = 'org.completeguide.armory'
TYPES = {
    'Weapons': {'weapon', 'ammunition'},
    'Armor': {'armor', 'shield', 'helmet', 'boots', 'gloves', 'cloak', 'belt'},
    'Consumables': {'potion', 'scroll', 'poison', 'consumable', 'consumables', 'food', 'alchemy',
                    'alchemical-ingredients', 'alchemical-extracts'},
    'Gear': {'adventuring-gear', 'gear', 'tools', 'container', 'clothing', 'book', 'key', 'instrument',
             'furnishing', 'misc', 'gem', 'material', 'trade-good', 'dye', 'other'},
    'Construction': {'construction-component', 'structure', 'mount', 'waterborne-vehicle', 'land-vehicle',
                     'air-vehicle', 'flying-vehicle'},
}
FACETS = {
    'ruleset': 'ruleset', 'source': 'source_id', 'rarity': 'rarity_key',
    'setting': 'association', 'region': 'association', 'culture': 'association',
}
SETUP = """
window.armoryQA = {
    savedAbout: byId("about").open,
    savedBasket: new Map(toyBasket),
    saved: {category, initial, term:byId("search").value, sort:byId("sort").value,
        min:byId("price-min").value, max:byId("price-max").value,
        facets:Object.keys(facets).reduce((saved,key)=>{saved[key]=facets[key].value;return saved;},{})},
    original:window.receiveSearch,
    result:null,
    run(options) {
        const chosen = options.facets || {};
        Object.keys(facets).forEach(key=>{
            const value = chosen[key] || "";
            facets[key].value=value;
            if(facets[key].value!==value) throw Error("Unavailable facet "+key+"="+value);
        });
        byId("search").value=options.term || "";
        byId("sort").value=options.sort || "relevance";
        byId("price-min").value=options.min || "";
        byId("price-max").value=options.max || "";
        if(!applyBuyBudget()) throw Error("Invalid QA budget");
        setInitial(options.initial || "");
        const button=Array.from(byId("categories").children)
            .find(node=>node.textContent===(options.category || "All"));
        this.result=null;
        button.click();
    },
    restore() {
        closeShop();
        dismissInspection();
        window.receiveSearch=this.original;
        byId("about").open=this.savedAbout;
        toyBasket.clear();
        this.savedBasket.forEach((value,key)=>toyBasket.set(key,value));
        this.run(this.saved);
    }
};
byId("about").open=false;
toyBasket.clear();
window.receiveSearch=(id,payload)=>{
    armoryQA.original(id,payload);
    if(id===searchId) armoryQA.result=JSON.parse(payload);
};
true
"""


def cases():
    def case(name, **options):
        return name, options

    result = [case('All records'), *(case('Category ' + category, category=category) for category in (*TYPES, 'Magic'))]
    result += [
        case('Regression · Magic plus BG3 source', category='Magic', facets={'source': 'bg3-wiki'}, positive=True),
        case('BG3 Dippable property with cold damage', facets={'source': 'bg3-wiki', 'property': 'dippable', 'damage': 'cold'}),
        case('BG3 edition plus Magic', category='Magic', facets={'ruleset': 'bg3'}, positive=True),
        case('Magic facet plus BG3 source', facets={'enchantment': 'magic', 'source': 'bg3-wiki'}, positive=True),
        case('BG3 Magic and mundane conflict', category='Magic', facets={'source': 'bg3-wiki', 'enchantment': 'mundane'}, exact_count=0),
        case('Magic plus mismatched edition/source', category='Magic', facets={'ruleset': 'dnd-2024', 'source': 'bg3-wiki'}),
        case('Bloodthirst in BG3 Magic', category='Magic', term='Bloodthirst',
             facets={'scope': 'exact', 'source': 'bg3-wiki'}, positive=True),
        case('Ordinary Dagger outside BG3 Magic', category='Magic', term='Dagger',
             facets={'scope': 'exact', 'source': 'bg3-wiki'}, exact_count=0),
        case('Ordinary Dagger in BG3 mundane', term='Dagger',
             facets={'scope': 'exact', 'source': 'bg3-wiki', 'enchantment': 'mundane'}, positive=True),
        case('Trident of the Depths cannot dual wield', term='Trident of the Depths',
             facets={'scope': 'exact', 'source': 'bg3-wiki', 'property': 'cant-dual-wield'}, positive=True),
        case('Arrow of Ice is magic and cold', category='Magic', term='Arrow of Ice',
             facets={'scope': 'exact', 'source': 'bg3-wiki', 'damage': 'cold'}, positive=True),
        case('Arrow of Ice does not deal fire', term='Arrow of Ice',
             facets={'scope': 'exact', 'source': 'bg3-wiki', 'damage': 'fire'}),
    ]
    result += [case('Initial ' + letter.upper(), initial=letter) for letter in string.ascii_lowercase + '#']
    result += [case('BG3 rarity ' + rarity, facets={'source': 'bg3-wiki', 'rarity': rarity}, positive=True)
               for rarity in ('common', 'uncommon', 'rare', 'very-rare', 'legendary')]
    result += [case('BG3 property ' + prop, category='Weapons', facets={'source': 'bg3-wiki', 'property': prop})
               for prop in ('ammunition', 'cant-dual-wield', 'dippable', 'enchanted', 'finesse', 'heavy',
                            'light', 'loading', 'melee', 'one-handed', 'ranged', 'reach', 'special', 'thrown',
                            'two-handed', 'versatile')]
    result += [case('D&D 2024 property ' + prop, category='Weapons', facets={'ruleset': 'dnd-2024', 'property': prop})
               for prop in ('ammunition', 'finesse', 'heavy', 'light', 'loading', 'reach', 'thrown', 'two-handed', 'versatile')]
    result += [
        case('Ravenloft setting', facets={'setting': 'setting:ravenloft'}, positive=True),
        case('Mystara setting and Glantri region', facets={'setting': 'setting:mystara', 'region': 'region:glantri'}, positive=True),
        case('Mystara and Thyatian culture', facets={'setting': 'setting:mystara', 'culture': 'culture:thyatian'}, positive=True),
        case('BG3 source and Mystara conflict', facets={'setting': 'setting:mystara', 'source': 'bg3-wiki'}),
        case('Case-normalized rarity in D&D Beyond', facets={'source': 'dndbeyond-public-index', 'rarity': 'very-rare'}, positive=True),
        case('Name-only with several words', term='ice arrow', facets={'scope': 'name', 'source': 'bg3-wiki'}, positive=True),
        case('Ranged Defender import excluded', term='Defender (Longbow)', category='Weapons',
             facets={'scope': 'exact', 'source': 'open5e-srd-2024'}, exact_count=0),
        case('Ranged Flame Tongue import excluded', term='Flame Tongue Dart', category='Weapons',
             facets={'scope': 'exact', 'source': 'open5e-srd-2024'}, exact_count=0),
        case('Legacy Mithral Half-Plate appears under Armor', term='Mithral Armor (Half-Plate)', category='Armor',
             facets={'scope': 'exact', 'source': 'open5e-srd-2014'},
             contains='open5e-srd-2014:srd_mithral-armor-half-plate'),
        case('No match exact', term='No Item Named Qzxxy', facets={'scope': 'exact'}),
        case('Full text Dagger prefix', term='dagg', facets={'source': 'bg3-wiki'}, fulltext='bg3-wiki:9'),
        case('Price ascending', sort='price-asc', pages=2),
        case('Price descending', sort='price-desc', pages=2),
        case('Alphabetic descending', sort='reverse'),
        case('Name ascending', sort='alpha'),
        case('One copper to buy', min='0.01', max='0.01'),
        case('Zero-gold ceiling', max='0'),
        case('Minimum buy only', min='100000', sort='price-desc', positive=True),
        case('BG3 buy cap plus letter', max='10', initial='a', facets={'source': 'bg3-wiki'}, positive=True),
        case('Buy budget uses buy price · inclusive', min='25', max='25', term='Arrow of Ice',
             facets={'source': 'bg3-wiki', 'scope': 'exact'}, positive=True),
        case('Buy budget excludes base-cost-only match', max='10', term='Arrow of Ice',
             facets={'source': 'bg3-wiki', 'scope': 'exact'}),
        case('Rogue simple Dagger', term='Dagger', facets={'scope': 'exact', 'proficiency': 'rogue-2024'}, contains='open5e-srd-2024:srd-2024_dagger'),
        case('Rogue excludes martial non-finesse Longsword', term='Longsword',
             facets={'scope': 'exact', 'proficiency': 'rogue-2024'}, exact_count=0),
        case('Fighter Chain Mail', term='Chain Mail', facets={'scope': 'exact', 'proficiency': 'fighter-2024'},
             contains='open5e-srd-2024:srd-2024_chain-mail'),
        case('Rogue plus Mystara', facets={'proficiency': 'rogue-2024', 'setting': 'setting:mystara'}, positive=True),
        case('Mystara adaptation retains documented Finesse', term='Atruaghin Bone Dagger',
             facets={'scope': 'exact', 'setting': 'setting:mystara', 'property': 'finesse'}, positive=True),
    ]
    return result


def load_oracle():
    with sqlite3.connect(ROOT / 'catalog/indexes/items.sqlite3') as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute('SELECT id,name,name_key,type,ruleset,source_id,rarity FROM items')]
        tags = collections.defaultdict(set)
        for item_id, tag in db.execute('SELECT item_id,tag FROM tags'):
            tags[item_id].add(tag)
        associations = collections.defaultdict(set)
        for item_id, entity in db.execute('SELECT item_id,entity_id FROM associations'):
            associations[item_id].add(entity)
    prices = json.loads((ROOT / 'catalog/supplements/item-prices.json').read_text())['records']
    for row in rows:
        item_id = row['id']
        row['tags'] = tags[item_id]
        row['association'] = associations[item_id]
        row['rarity_key'] = (row['rarity'] or '').strip().lower().replace(' ', '-')
        normalized = unicodedata.normalize('NFKD', row['name']).casefold()
        letter = next((c for c in normalized if c.isalnum()), '')
        row['initial'] = letter if letter in string.ascii_lowercase and letter else '#'
        row['buy'] = Decimal(prices[item_id]['base_buy_gp'])
        row['price'] = Decimal(prices[item_id]['base_cost_gp'])
    return rows


def expected(rows, options):
    facets = options.get('facets', {})
    category = options.get('category', 'All')
    required_tags = set()
    if category == 'Magic':
        required_tags.add('magic')
    for key, prefix in (('enchantment', ''), ('property', 'property:'), ('damage', 'damage:')):
        if facets.get(key):
            required_tags.add(prefix + facets[key])
    term = options.get('term', '').strip().lower()
    minimum = Decimal(options.get('min', '0'))
    maximum = Decimal(options.get('max', 'Infinity'))

    def matches(row):
        if category in TYPES and row['type'] not in TYPES[category]:
            return False
        if not required_tags.issubset(row['tags']):
            return False
        for facet, column in FACETS.items():
            if facet in facets and (facets[facet] not in row[column] if column == 'association' else facets[facet] != row[column]):
                return False
        if options.get('initial') and row['initial'] != options['initial']:
            return False
        if not minimum <= row['buy'] <= maximum:
            return False
        if facets.get('scope') == 'exact' and term and row['name'].lower() != term:
            return False
        if facets.get('scope') == 'name' and any(word not in row['name'].lower() for word in re.findall(r'\w+', term)):
            return False
        return True

    return [row for row in rows if matches(row)]


class DevTools:
    def __init__(self, socket):
        self.socket = socket
        self.counter = 0

    def eval(self, expression, *, user_gesture=False):
        self.counter += 1
        self.socket.send(json.dumps({'id': self.counter, 'method': 'Runtime.evaluate', 'params': {
            'expression': expression, 'returnByValue': True, 'awaitPromise': True, 'userGesture': user_gesture,
        }}))
        while True:
            response = json.loads(self.socket.recv())
            if response.get('id') == self.counter:
                break
        result = response.get('result', {})
        if 'exceptionDetails' in result or 'error' in response:
            raise AssertionError(result.get('result', {}).get('description') or response)
        return result['result'].get('value')

    def result(self):
        return self.eval("""new Promise((resolve,reject)=>{
            const until=Date.now()+4000;
            function check(){
                if(armoryQA.result) resolve(armoryQA.result);
                else if(Date.now()>until) reject(Error("Search timed out"));
                else setTimeout(check,20);
            }
            check();
        })""")


def run_case(dev, rows, options):
    dev.eval('armoryQA.run(' + json.dumps(options) + ')')
    result = dev.result()
    assert 'error' not in result, result.get('error')
    eligible = expected(rows, options)
    ids = {row['id'] for row in eligible}
    items = result['items']
    assert set(item['id'] for item in items) <= ids, 'Results include IDs outside the oracle'
    if options.get('exact_count') is not None:
        assert result['total'] == options['exact_count'], result['total']
    elif not options.get('fulltext') and not options.get('facets', {}).get('proficiency'):
        assert result['total'] == len(ids), (result['total'], len(ids))
    if options.get('positive'):
        assert result['total'] > 0, 'Expected matching results'
    required = options.get('contains') or options.get('fulltext')
    if required:
        assert required in {item['id'] for item in items}, required
    assert len(items) == min(48, result['total']), 'Wrong first page size'
    assert dev.eval('grid.children.length') == len(items), 'Rendered card count differs'
    for _ in range(1, options.get('pages', 1)):
        dev.eval('armoryQA.result=null; byId("more").click();true')
        next_page = dev.result()
        items += next_page['items']
        assert len(items) == len({item['id'] for item in items}), 'Duplicate ID across pages'
    sort = options.get('sort')
    if sort and sort.startswith('price-'):
        values = [int(item['price_copper']) for item in items]
        assert values == sorted(values, reverse=sort == 'price-desc'), 'Prices not ordered across the result pages'
    elif sort in ('alpha', 'reverse'):
        keys = {row['id']: row['name_key'] for row in eligible}
        values = [keys[item['id']] for item in items]
        assert values == sorted(values, reverse=sort == 'reverse'), 'Names not ordered'
    return result['total']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default=str(ROOT / '.cache/android-tools/sdk/platform-tools/adb'))
    parser.add_argument('--serial', default='emulator-5580')
    parser.add_argument('--expect-layout', choices=('compact', 'wide'))
    args = parser.parse_args()
    adb = [args.adb, '-s', args.serial]
    rows = load_oracle()
    pid = subprocess.check_output([*adb, 'shell', 'pidof', PACKAGE], text=True).strip().split()[0]
    port = subprocess.check_output([*adb, 'forward', 'tcp:0', 'localabstract:webview_devtools_remote_' + pid], text=True).strip()
    failures = []
    total = 0
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=4) as response:
            page = next(page for page in json.load(response) if page.get('url', '').startswith('https://armory.local/'))
        socket = create_connection(page['webSocketDebuggerUrl'], timeout=8, suppress_origin=True)
        try:
            dev = DevTools(socket)
            dev.eval(SETUP)
            if args.expect_layout:
                assert dev.eval('compactInspection.matches') == (args.expect_layout == 'compact')
            print('Catalog release ' + dev.eval('JSON.parse(Armory.metadata()).manifest.content_version'))
            for name, options in cases():
                total += 1
                try:
                    count = run_case(dev, rows, options)
                    print(f'PASS {name} ({count:,})')
                except (AssertionError, KeyError, TypeError) as error:
                    failures.append(name)
                    print(f'FAIL {name}: {error}')
            total += 1
            try:
                dev.eval('armoryQA.run({category:"Magic"})')
                dev.result()
                dev.eval('armoryQA.result=null;facets.source.value="bg3-wiki";facets.source.dispatchEvent(new Event("change"));true')
                result = dev.result()
                target_count = len(expected(rows, {'category': 'Magic', 'facets': {'source': 'bg3-wiki'}}))
                assert target_count > 0 and result['total'] == target_count
                print(f'PASS Magic first, then select BG3 source ({target_count:,})')
            except (AssertionError, KeyError, TypeError) as error:
                failures.append('Magic first, then select BG3 source')
                print(f'FAIL Magic first, then select BG3 source: {error}')
            total += 1
            try:
                dev.eval('armoryQA.run({facets:{setting:"setting:mystara",proficiency:"rogue-2024"}})')
                initial_count = dev.result()['total']
                dev.eval("""byId("price-min").value="30";byId("price-max").value="10";
                    byId("price-max").dispatchEvent(new Event("change"));armoryQA.result=null;
                    byId("active-filters").querySelector('[aria-label^="Remove Class proficiency"]').click();true""")
                actual = dev.result()['total']
                target = len(expected(rows, {'facets': {'setting': 'setting:mystara'}}))
                assert actual == target and actual > initial_count
                assert dev.eval('facets.proficiency.value==="" && !byId("active-filters").textContent.includes("Rogue")')
                print(f'PASS Remove Rogue chip with invalid draft budget ({initial_count:,} → {actual:,})')
                dev.eval('armoryQA.run({})')
                dev.result()
            except (AssertionError, KeyError, TypeError) as error:
                failures.append('Remove Rogue chip with invalid draft budget')
                print(f'FAIL Remove Rogue chip with invalid draft budget: {error}')
            total += 1
            try:
                dev.eval('armoryQA.run({term:"Dagger",facets:{scope:"exact",ruleset:"bg3"}})')
                dev.result()
                dev.eval("""grid.firstElementChild.click();
                    armoryQA.result=null;facets.ruleset.value="dnd-2024";
                    facets.ruleset.dispatchEvent(new Event("change"));true""")
                result = dev.result()
                assert result['items'] and all(item['ruleset']=='dnd-2024' for item in result['items'])
                assert dev.eval('selected==="" && !inspection.classList.contains("active") && '
                                'Array.from(grid.querySelectorAll(".card small")).every(row=>row.textContent.includes("D&D 2024"))')
                print('PASS Rules edition clears the previously pinned BG3 item')
            except (AssertionError, KeyError, TypeError) as error:
                failures.append('Rules edition clears the previously pinned BG3 item')
                print(f'FAIL Rules edition clears the previously pinned BG3 item: {error}')
            checks = {
                'Expanded filters remain tappable with inspection selected': '''(async () => {
                    const previousScroll = scrollY;
                    const previousOpen = !byId("filters").hidden;
                    showFilters(false);
                    inspect("bg3-wiki:9688", grid.firstElementChild);
                    await itemDetails;
                    byId("filter-toggle").click();
                    const inspectionState = compactInspection.matches ? !selected : selected === "bg3-wiki:9688";
                    const controls = Array.from(byId("filters").querySelectorAll("select, input, button"));
                    const reachable = controls.every(control => {
                        control.scrollIntoView({block: "center"});
                        const bounds = control.getBoundingClientRect();
                        return control.contains(document.elementFromPoint(
                            bounds.left + bounds.width / 2, bounds.top + bounds.height / 2));
                    });
                    grid.firstElementChild.click();
                    const reopening = selected && byId("filters").hidden === compactInspection.matches;
                    dismissInspection(false);
                    showFilters(previousOpen);
                    scrollTo(0, previousScroll);
                    return !!(inspectionState && reachable && reopening);
                })()''',
                'Legacy enchanted Lance shows the 2024 base-rule change': '''(async () => {
                    inspect("open5e-srd-2014:srd_lance-2", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return text.includes("Verified 2024 enhancement") && text.includes("2024 rules note")
                        && text.includes("1d10 Piercing") && text.includes("+2 to attack and damage");
                })()''',
                'Legacy Net and crossbow link to their 2024 equipment rules': '''(async () => {
                    inspect("open5e-srd-2014:srd_net", grid.firstElementChild);
                    await itemDetails;
                    const net = inspection.textContent;
                    inspect("open5e-srd-2014:srd_crossbow-hand", grid.firstElementChild);
                    await itemDetails;
                    const crossbow = inspection.textContent;
                    return net.includes("Verified 2024 equipment counterpart") &&
                        net.includes("The 2024 Net is adventuring gear") && net.includes("Dexterity save") &&
                        crossbow.includes("Verified 2024 equipment counterpart") &&
                        crossbow.includes("Hand Crossbow") && crossbow.includes("Vex");
                })()''',
                'Vicious Longsword shows the verified 2024 hit trigger': '''(async () => {
                    inspect("open5e-srd-2014:srd_vicious-weapon-longsword", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return text.includes("Published 2024 · Vicious Weapon") && text.includes("Base 1d8 Slashing")
                        && text.includes("Add 2d6") && text.includes("every hit against a creature")
                        && text.includes("Open published 2024 item") && text.includes("Sap");
                })()''',
                'Legacy Defender and Dagger of Venom show 2024 activation and timing': '''(async () => {
                    inspect("open5e-srd-2014:srd_defender-longsword", grid.firstElementChild);
                    await itemDetails;
                    const defender = inspection.textContent;
                    inspect("open5e-srd-2014:srd_dagger-of-venom", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    return ["Published 2024 · Defender", "start of your next turn", "Sap"]
                        .every(value => defender.includes(value)) &&
                        ["Published 2024 · Dagger of Venom", "Bonus Action", "2d10 Poison",
                            "DC 15 Constitution", "next dawn", "Nick"].every(value => dagger.includes(value));
                })()''',
                'Legacy Dragon Slayer and Lightning Javelin show 2024 variant rules': '''(async () => {
                    inspect("open5e-srd-2014:srd_dragon-slayer-longsword", grid.firstElementChild);
                    await itemDetails;
                    const slayer = inspection.textContent;
                    inspect("open5e-srd-2014:srd_javelin-of-lightning", grid.firstElementChild);
                    await itemDetails;
                    const javelin = inspection.textContent;
                    return ["Published 2024 · Dragon Slayer", "3d6", "Sap", "Open published 2024 item"]
                        .every(value => slayer.includes(value)) &&
                        ["Published 2024 · Javelin of Lightning", "120 ft", "DC 13 Dexterity", "4d6 Lightning"]
                        .every(value => javelin.includes(value));
                })()''',
                'Legacy Sword of Wounding shows 2024 rules and base mastery': '''(async () => {
                    inspect("open5e-srd-2014:srd_sword-of-wounding-rapier", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Published 2024 · Sword of Wounding", "2d6 Necrotic",
                        "DC 15 Constitution", "1 hour", "Vex"].every(value => text.includes(value));
                })()''',
                'Legacy Oathbow, Thunderbolts, and Trident show published rules': '''(async () => {
                    inspect("open5e-srd-2014:srd_oathbow", grid.firstElementChild);
                    await itemDetails;
                    const bow = inspection.textContent;
                    inspect("open5e-srd-2014:srd_hammer-of-thunderbolts", grid.firstElementChild);
                    await itemDetails;
                    const hammer = inspection.textContent;
                    inspect("open5e-srd-2014:srd_trident-of-fish-command", grid.firstElementChild);
                    await itemDetails;
                    const trident = inspection.textContent;
                    return ["Published 2024 · Oathbow", "Longbow", "150/600 ft", "3d6 Piercing"]
                        .every(value => bow.includes(value)) &&
                        ["Published 2024 · Hammer of Thunderbolts", "Maul", "2d6 Bludgeoning", "DC 17 Constitution"]
                        .every(value => hammer.includes(value)) &&
                        ["Published 2024 · Trident of Fish Command", "DC 15 Wisdom", "telepathic orders", "Topple"]
                        .every(value => trident.includes(value));
                })()''',
                'Legacy magic net shows a playable save-based conversion': '''(async () => {
                    inspect("open5e-srd-2014:srd_net-2", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["D&D 2024 tabletop conversion", "DM review", "DC = 10 +",
                        "Restrained", "DC 10 Strength", "No direct damage"].every(value => text.includes(value));
                })()''',
                'Mystara crafting examples show verified weapon and shield rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:e36299388b2c22e3", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:401e6f0f5da97a7b", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    return ["Verified 2024 equipment mapping", "1d4 Piercing + 1", "Nick", "1,050 ducats"]
                        .every(value => dagger.includes(value)) &&
                        ["Verified 2024 equipment mapping", "Armor class bonus+3", "3,000 ducats"]
                        .every(value => shield.includes(value));
                })()''',
                'Darokin guard equipment shows training and armor rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:946280f6cf1dad4e", grid.firstElementChild);
                    await itemDetails;
                    const rapier = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:f10e05f231013ac5", grid.firstElementChild);
                    await itemDetails;
                    const armor = inspection.textContent;
                    return ["DM review", "1d8 Piercing + 2", "Reaction", "Vex"].every(value => rapier.includes(value))
                        && ["Verified 2024 equipment mapping", "14 + Dex modifier (max +2)", "Medium armor"]
                            .every(value => armor.includes(value));
                })()''',
                'Named Mystara drafts show healing and lightweight plate rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:b3c8c399c9fb2980", grid.firstElementChild);
                    await itemDetails;
                    const sword = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:579294a755b5b670", grid.firstElementChild);
                    await itemDetails;
                    const armor = inspection.textContent;
                    return ["DM review", "2d6 Radiant", "2d8 HP", "dawn"].every(value => sword.includes(value))
                        && ["DM review", "Armor class18", "10 lb", "Heavy armor"]
                            .every(value => armor.includes(value));
                })()''',
                'Mystara dagger and trident show recharge and curse rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:d554313cb4c98e86", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:c3006121b0a2603b", grid.firstElementChild);
                    await itemDetails;
                    const trident = inspection.textContent;
                    return ["DM review", "Veiled Flight", "fourth dawn", "Nick"].every(value => dagger.includes(value))
                        && ["DM review", "then −2", "Remove Curse", "Topple"].every(value => trident.includes(value));
                })()''',
                'Mystara mail and Dragon Slayer show verified and draft rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:2795e93f9805c38d", grid.firstElementChild);
                    await itemDetails;
                    const armor = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:c5e5f4a776f2dae2", grid.firstElementChild);
                    await itemDetails;
                    const sword = inspection.textContent;
                    return ["Verified 2024 equipment mapping", "13 + Dex modifier (max +2)", "Medium armor"]
                        .every(value => armor.includes(value)) &&
                        ["DM review", "green dragon", "DC 17 Dexterity", "10d6 + 40 Force", "43,800 ducats"]
                            .every(value => sword.includes(value));
                })()''',
                'Mystara staff and library dagger show distinct rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:82e2b50caafdfb82", grid.firstElementChild);
                    await itemDetails;
                    const staff = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:f43daed45edb4310", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    return ["DM review", "2d6 Necrotic", "2d6 HP", "holds up to 3"].every(value => staff.includes(value))
                        && ["Verified 2024 equipment mapping", "library dome", "+2 to attack"].every(value => dagger.includes(value));
                })()''',
                'Glantrian crafting weapons show flight, speed, and legacy costs': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:01cb1241597f745d", grid.firstElementChild);
                    await itemDetails;
                    const hammer = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:f98b5563265e99aa", grid.firstElementChild);
                    await itemDetails;
                    const lance = inspection.textContent;
                    return ["DM review", "Fly Speed of 60 ft", "recharges at dawn", "24,250 ducats"]
                        .every(value => hammer.includes(value)) &&
                        ["DM review", "Bonus Action", "unless mounted", "45,000 ducats"]
                            .every(value => lance.includes(value));
                })()''',
                'Sparkling Spear and Black Eagle sword show their source-specific effects': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:5687931e1fb287f3", grid.firstElementChild);
                    await itemDetails;
                    const spear = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:04e916215c2eb5ae", grid.firstElementChild);
                    await itemDetails;
                    const sword = inspection.textContent;
                    return ["DM review", "300 ft", "See Invisibility", "2d6 Force"].every(value => spear.includes(value))
                        && ["DM review", "DC 16 Wisdom", "Geas", "Remove Curse"].every(value => sword.includes(value));
                })()''',
                'Mystara staffs show charges and the planar aura': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:0327b74e1c90da05", grid.firstElementChild);
                    await itemDetails;
                    const wizardry = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:1b722f9aeb985909", grid.firstElementChild);
                    await itemDetails;
                    const water = inspection.textContent;
                    return ["DM review", "20 charges", "Wall of Force", "156,200 ducats"]
                        .every(value => wizardry.includes(value)) &&
                        ["DM review", "Swim Speed", "within 10 ft", "Pearl of Power"]
                            .every(value => water.includes(value));
                })()''',
                'Karst shield and Thunderbolt scabbard show distinct combat rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:6a9440c634d1adb8", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:3bded5794e3835eb", grid.firstElementChild);
                    await itemDetails;
                    const sword = inspection.textContent;
                    return ["DM review", "2d4 Slashing", "20/60 ft", "Utilize action"]
                        .every(value => shield.includes(value)) &&
                        ["DM review", "scabbard", "+11", "2d8 Slashing", "until dawn"]
                            .every(value => sword.includes(value));
                })()''',
                'Mystara training weapon and bone helm show their tabletop roles': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:db6c9b50d292fa40", grid.firstElementChild);
                    await itemDetails;
                    const weapon = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:d40bbd47d4ca7ecd", grid.firstElementChild);
                    await itemDetails;
                    const helm = inspection.textContent;
                    return ["DM review", "1 HP", "Unconscious", "DC 10 Wisdom"]
                        .every(value => weapon.includes(value)) &&
                        ["DM review", "Armor class bonus+0", "no separate AC"]
                            .every(value => helm.includes(value));
                })()''',
                'Mystara reference cards explain the chosen weapon and ceremonial focus': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:54427e4f83d487c5", grid.firstElementChild);
                    await itemDetails;
                    const family = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:094b8e35215c6610", grid.firstElementChild);
                    await itemDetails;
                    const symbol = inspection.textContent;
                    return ["2024 use and source context", "+1 or +2 enhancement", "attack and damage"]
                        .every(value => family.includes(value)) &&
                        ["2024 use and source context", "Spellcasting Focus", "ceremonial role"]
                            .every(value => symbol.includes(value)) &&
                        ![family, symbol].some(value => value.includes("2024 provisional profile"));
                })()''',
                'Soul Dagger and Dragonfly staff show their activation rules': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:5ebc4c822e60b6be", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:49aed8261f01cf1c", grid.firstElementChild);
                    await itemDetails;
                    const staff = inspection.textContent;
                    return ["DM review", "Reaction", "24 hours", "release the soul"].every(value => dagger.includes(value))
                        && ["DM review", "1d4 + 1 Force", "120 ft", "spends 1 charge"]
                            .every(value => staff.includes(value));
                })()''',
                'Blackmoor relic and slime show their distinct tabletop saves': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:7a8f9c7f0b2fb1cf", grid.firstElementChild);
                    await itemDetails;
                    const relic = inspection.textContent;
                    inspect("gazetteer-local-pdf-reference:fc0b404799da8e64", grid.firstElementChild);
                    await itemDetails;
                    const slime = inspection.textContent;
                    return ["DM review", "20d6 Lightning", "DC 17 Dexterity", "50 charges"]
                        .every(value => relic.includes(value)) &&
                        ["DM review", "2d6 Acid", "20 ft", "Utilize action"]
                            .every(value => slime.includes(value));
                })()''',
                '2024 public sword pages show eligible variants and distinct masteries': '''(async () => {
                    inspect("dndbeyond:9229115", grid.firstElementChild);
                    await itemDetails;
                    const wounding = inspection.textContent;
                    inspect("dndbeyond:9229181", grid.firstElementChild);
                    await itemDetails;
                    const vorpal = inspection.textContent;
                    return ["Sword of Wounding · Glaive", "Sword of Wounding · Rapier", "10 ft melee", "Vex", "2d6 Necrotic"]
                        .every(value => wounding.includes(value)) &&
                        ["Vorpal Sword · Scimitar", "Vorpal Sword · Longsword", "30 Slashing"]
                            .every(value => vorpal.includes(value)) &&
                        !vorpal.includes("Vorpal Sword · Shortsword");
                })()''',
                'Public armor cards show Cavalier shield and Metal Shell rules': '''(async () => {
                    inspect("dndbeyond:9058943", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    inspect("dndbeyond:9228350", grid.firstElementChild);
                    await itemDetails;
                    const armor = inspection.textContent;
                    return ["Verified 2024 armor rules", "Armor class bonus+4", "Forceful Bash", "Protective Field"]
                        .every(value => shield.includes(value)) &&
                        ["Verified 2024 armor rules", "Armor class18", "Metal Shell", "10 minutes"]
                            .every(value => armor.includes(value));
                })()''',
                'Public chain armor cards distinguish their two base suits': '''(async () => {
                    inspect("dndbeyond:9228530", grid.firstElementChild);
                    await itemDetails;
                    const efreeti = inspection.textContent;
                    inspect("dndbeyond:9228539", grid.firstElementChild);
                    await itemDetails;
                    const elven = inspection.textContent;
                    return ["armor rules · Chain Mail", "armor rules · Chain Shirt", "Armor class19",
                        "Armor class16 + Dex modifier (max +2)", "Fire immunity"].every(value => efreeti.includes(value))
                        && ["Armor class17", "Armor class14 + Dex modifier (max +2)", "count as trained"]
                            .every(value => elven.includes(value));
                })()''',
                'Public armor families show base suits and their published effects': '''(async () => {
                    inspect("dndbeyond:9228837", grid.firstElementChild);
                    await itemDetails;
                    const mariner = inspection.textContent;
                    inspect("dndbeyond:9228541", grid.firstElementChild);
                    await itemDetails;
                    const enspelled = inspection.textContent;
                    return ["armor rules · Leather Armor", "armor rules · Plate Armor", "Swim Speed",
                        "underwater at 0 HP", "1d4 HP"].every(value => mariner.includes(value))
                        && ["Armor class18", "Abjuration or Illusion", "6 charges", "DC 18, +10"]
                            .every(value => enspelled.includes(value));
                })()''',
                'Cast-Off and Gleaming armor show eligible suits and readable rules links': '''(async () => {
                    inspect("dndbeyond:9228382", grid.firstElementChild);
                    await itemDetails;
                    const castoff = inspection.textContent;
                    const sourceLink = Array.from(inspection.querySelectorAll("a")).some(link =>
                        link.textContent === "Read published rules" && link.href.includes("roll20.net"));
                    inspect("dndbeyond:9228349", grid.firstElementChild);
                    await itemDetails;
                    const gleaming = inspection.textContent;
                    return sourceLink && ["armor rules · Padded Armor", "armor rules · Plate Armor",
                        "Magic action to doff", "Armor class18"].every(value => castoff.includes(value))
                        && ["never gets dirty", "armor rules · Chain Shirt", "13 + Dex modifier (max +2)"]
                            .every(value => gleaming.includes(value));
                })()''',
                'Public magic weapon cards distinguish bases and attunement': '''(async () => {
                    inspect("dndbeyond:9228714", grid.firstElementChild);
                    await itemDetails;
                    const hammer = inspection.textContent;
                    inspect("dndbeyond:9228415", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    return ["Thunderbolts · Maul", "Thunderbolts · Warhammer", "Base 2d6", "Base 1d8", "DC 17 Constitution"]
                        .every(value => hammer.includes(value))
                        && ["Dagger of Venom · Dagger", "AttunementNone", "Nick", "2d10 Poison"]
                            .every(value => dagger.includes(value));
                })()''',
                'Broad weapon families respect melee eligibility and collapse long lists': '''(async () => {
                    inspect("dndbeyond:9228647", grid.firstElementChild);
                    await itemDetails;
                    const flame = inspection.textContent;
                    const variants = Array.from(inspection.querySelectorAll("details")).filter(panel =>
                        panel.querySelector("summary") && panel.querySelector("summary").textContent.includes("Published 2024 · Flame Tongue"));
                    inspect("dndbeyond:9228520", grid.firstElementChild);
                    await itemDetails;
                    const dragon = inspection.textContent;
                    return flame.includes("Flame Tongue · Dagger") && !flame.includes("Flame Tongue · Dart")
                        && !flame.includes("Flame Tongue · Longbow") && variants.length === 28
                        && variants.filter(panel => panel.open).length === 1
                        && ["Dragon Slayer · Longbow", "Dragon Slayer · Dart", "3d6"]
                            .every(value => dragon.includes(value));
                })()''',
                'White Plume Mountain artifacts show their revised combat rules': '''(async () => {
                    inspect("dndbeyond:9229201", grid.firstElementChild);
                    await itemDetails;
                    const whelm = inspection.textContent;
                    inspect("dndbeyond:9229198", grid.firstElementChild);
                    await itemDetails;
                    const wave = inspection.textContent;
                    return ["Published 2024 · Whelm", "60/180 ft", "4d8", "DC 20 Constitution", "returns"]
                        .every(value => whelm.includes(value)) &&
                        ["Published 2024 · Wave", "21 Necrotic", "DC 20", "level 9", "Topple"]
                            .every(value => wave.includes(value));
                })()''',
                'Executioner axe and thunderous lute use their published bases': '''(async () => {
                    inspect("dndbeyond:9228603", grid.firstElementChild);
                    await itemDetails;
                    const axe = inspection.textContent;
                    inspect("dndbeyond:9228833", grid.firstElementChild);
                    await itemDetails;
                    const lute = inspection.textContent;
                    return ["Axe · Handaxe", "Axe · Halberd", "2d6 Slashing", "temporary HP"]
                        .every(value => axe.includes(value)) &&
                        ["Thumping · Club", "1d4 Bludgeoning", "2d8 Thunder", "Charisma", "Slow"]
                            .every(value => lute.includes(value));
                })()''',
                'Weapon templates preserve eligible forms and special effects': '''(async () => {
                    inspect("dndbeyond:9228341", grid.firstElementChild);
                    await itemDetails;
                    const adamantine = inspection.textContent;
                    inspect("dndbeyond:9229199", grid.firstElementChild);
                    await itemDetails;
                    const warning = inspection.textContent;
                    return ["Adamantine Weapon · Ammunition", "Adamantine Weapon · Dagger", "automatically a Critical Hit"]
                        .every(value => adamantine.includes(value)) && !adamantine.includes("Adamantine Weapon · Longbow")
                        && ["Weapon of Warning · Longbow", "within 30 ft", "Advantage on Initiative", "sleeping naturally"]
                            .every(value => warning.includes(value));
                })()''',
                'Moonblade runes and Slaying ammunition show full triggers': '''(async () => {
                    inspect("dndbeyond:9228858", grid.firstElementChild);
                    await itemDetails;
                    const moonblade = inspection.textContent;
                    inspect("dndbeyond:9228344", grid.firstElementChild);
                    await itemDetails;
                    const slaying = inspection.textContent;
                    return ["Moonblade · Greatsword", "Moonblade · Rapier", "76–80", "20/60 ft",
                        "DC 15 Constitution", "spectral elf"].every(value => moonblade.includes(value))
                        && ["Ammunition of Slaying", "6d10 Force", "DC 17 Constitution", "becomes nonmagical"]
                            .every(value => slaying.includes(value));
                })()''',
                'Indexed shields distinguish conditional and permanent AC bonuses': '''(async () => {
                    inspect("dndbeyond:4577", grid.firstElementChild);
                    await itemDetails;
                    const catcher = inspection.textContent;
                    inspect("dndbeyond:5158", grid.firstElementChild);
                    await itemDetails;
                    const enhanced = inspection.textContent;
                    return ["Verified 2024 shield counterpart", "Armor class bonus+2", "additional AC against ranged",
                        "within 5 ft"].every(value => catcher.includes(value)) &&
                        ["Armor class bonus+5", "normal +2 shield bonus", "Read published rules"]
                            .every(value => enhanced.includes(value));
                })()''',
                'Indexed metal armor variants show published eligibility and exceptions': '''(async () => {
                    inspect("dndbeyond:5381", grid.firstElementChild);
                    await itemDetails;
                    const mithral = inspection.textContent;
                    inspect("dndbeyond:5370", grid.firstElementChild);
                    await itemDetails;
                    const adamantine = inspection.textContent;
                    return ["armor counterpart · Plate Armor", "Strength requirementNone", "Stealth disadvantageNo"]
                        .every(value => mithral.includes(value)) &&
                        ["armor counterpart · Chain Shirt", "Critical Hit against you becomes a normal hit"]
                            .every(value => adamantine.includes(value)) &&
                        !adamantine.includes("armor counterpart · Hide Armor");
                })()''',
                'Legacy public weapons show revised counterparts and separate citations': '''(async () => {
                    inspect("dndbeyond:4613", grid.firstElementChild);
                    await itemDetails;
                    const dagger = inspection.textContent;
                    const links = Array.from(inspection.querySelectorAll("a")).map(link => link.href);
                    inspect("dndbeyond:5388", grid.firstElementChild);
                    await itemDetails;
                    const giant = inspection.textContent;
                    return ["2024 counterpart · Dagger of Venom", "Bonus Action", "next dawn"]
                        .every(value => dagger.includes(value)) &&
                        links.some(url => url.includes("4613-dagger-of-venom")) &&
                        links.some(url => url.includes("br-2024")) &&
                        ["2024 counterpart · Giant Slayer · Longbow", "DC 15 Strength", "Prone"]
                            .every(value => giant.includes(value));
                })()''',
                'Indexed enhancements distinguish weapons, armor and ammunition': '''(async () => {
                    inspect("dndbeyond:5404", grid.firstElementChild);
                    await itemDetails;
                    const weapon = inspection.textContent;
                    inspect("dndbeyond:5379", grid.firstElementChild);
                    await itemDetails;
                    const armor = inspection.textContent;
                    inspect("dndbeyond:5411", grid.firstElementChild);
                    await itemDetails;
                    const ammo = inspection.textContent;
                    return ["2024 counterpart · Longbow +3", "+3 to attack and damage", "150/600 ft"]
                        .every(value => weapon.includes(value)) &&
                        ["Armor class21", "Legendary", "Plate Armor"].every(value => armor.includes(value)) &&
                        ["Ammunition +3", "compatible launcher", "becomes nonmagical"]
                            .every(value => ammo.includes(value));
                })()''',
                'Legacy armor pages show revised rules and retain their original links': '''(async () => {
                    inspect("dndbeyond:5507", grid.firstElementChild);
                    await itemDetails;
                    const mariner = inspection.textContent;
                    const links = Array.from(inspection.querySelectorAll("a")).map(link => link.href);
                    inspect("dndbeyond:4645", grid.firstElementChild);
                    await itemDetails;
                    const glamour = inspection.textContent;
                    return ["armor counterpart · Leather Armor", "underwater at 0 HP", "1d4 HP"]
                        .every(value => mariner.includes(value)) &&
                        links.some(url => url.includes("5507-mariners-armor")) &&
                        links.some(url => url.includes("roll20.net")) &&
                        ["Armor class13 + Dex modifier", "Bonus Action", "Weight and bulk stay the same"]
                            .every(value => glamour.includes(value));
                })()''',
                'Legacy artifact cards show 2024 rules and preserve their source links': '''(async () => {
                    inspect("dndbeyond:5432", grid.firstElementChild);
                    await itemDetails;
                    const whelm = inspection.textContent;
                    const links = Array.from(inspection.querySelectorAll("a")).map(link => link.href);
                    inspect("dndbeyond:5430", grid.firstElementChild);
                    await itemDetails;
                    const moonblade = inspection.textContent;
                    return ["2024 counterpart · Whelm", "60/180 ft", "Open published 2024 item"]
                        .every(value => whelm.includes(value)) &&
                        links.some(url => url.includes("5432-whelm")) &&
                        links.some(url => url.includes("roll20.net")) &&
                        ["2024 counterpart · Moonblade · Rapier", "76–80", "The revised blade chooses its bearer"]
                            .every(value => moonblade.includes(value));
                })()''',
                'Cursed weapon counterparts show distinct triggers and end conditions': '''(async () => {
                    inspect("dndbeyond:5382", grid.firstElementChild);
                    await itemDetails;
                    const axe = inspection.textContent;
                    inspect("dndbeyond:5505", grid.firstElementChild);
                    await itemDetails;
                    const sword = inspection.textContent;
                    return ["Berserker Axe · Halberd", "HP maximum", "DC 15 Wisdom", "within 60 ft"]
                        .every(value => axe.includes(value)) &&
                        ["Sword of Vengeance · Rapier", "DC 15 Wisdom", "Banishment", "0 HP"]
                            .every(value => sword.includes(value));
                })()''',
                'Curse of Strahd conversions preserve adventure-specific combat rules': '''(async () => {
                    const cases = [
                        ["curse-of-strahd-reference:0d78caf0c91ed39e", ["2d6 Temporary Hit Points", "20/60 feet", "Kavan"]],
                        ["dndbeyond:5531", ["2d6 Radiant", "DC 15 Wisdom", "crumbles when that battle ends"]],
                        ["curse-of-strahd-reference:919ef60581cee5bc", ["1d8 Radiant", "sunlight", "Communicates emotions"]],
                        ["dndbeyond:5528", ["1d6 + 4", "DC 12 Wisdom", "300 feet"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        const links = Array.from(inspection.querySelectorAll("a"));
                        if (!terms.every(term => details.includes(term)) ||
                            !links.some(link => link.href.includes("/cos/treasures"))) return false;
                    }
                    return true;
                })()''',
                'Ravenloft cards distinguish weapon rules from encounter effects': '''(async () => {
                    const cases = [
                        ["d01396b5ec856e1c", ["One charge remains", "escape Barovia fails"]],
                        ["16885f3067840a8a", ["2024 base weapon rules", "4d10 Lightning", "crypt mechanism"]],
                        ["9edb3e613b296ebe", ["Cone of Cold (5)", "Resistance to Cold", "overriding thirst"]],
                        ["f9580784d28dcdbc", ["DC 14 Dexterity", "40 pounds", "resets after 1 minute"]],
                        ["1f01af15fd48f8ea", ["30/120 feet", "250 gp", "separate treasure"]],
                        ["364d99c685736ae0", ["Cane: 1d6 Bludgeoning", "Blade: 1d6 Piercing", "shape-shifted"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("curse-of-strahd-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Ravenloft armor cards distinguish worn armor from constructs': '''(async () => {
                    const cases = [
                        ["46fa332ea1bbfd53", ["11 + Dex modifier", "Light armor", "Open 2024 Leather Armor"]],
                        ["b7d42274e00db79a", ["15 + Dex modifier (max +2)", "AC 17", "80 lb", "Base cost3000 gp", "Base buy7500 gp", "Base sell1200 gp"]],
                        ["c0969d5dcc3473aa", ["AC 18", "24 hours", "no player equipment AC"]],
                        ["04f9651b9a775b54", ["AC 21", "112 Hit Points", "no player equipment profile"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("curse-of-strahd-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Barding preserves legacy prices and shows 2024 replacement costs': '''(async () => {
                    inspect("dmg-2e-reference:5dac7f0e655b4f6b", grid.firstElementChild);
                    await itemDetails;
                    const plate = inspection.textContent;
                    inspect("mystara-fan-names-reference:83eb29ff24e8bfed", grid.firstElementChild);
                    await itemDetails;
                    const chain = inspection.textContent;
                    return ["130 lb", "Base cost6000 gp", "Open 2024 Plate Armor"].every(term => plate.includes(term)) &&
                        ["110 lb", "300 gp", "Base cost150 gp"].every(term => chain.includes(term));
                })()''',
                'Barding adaptations show legacy facts and 2024 rules': '''(async () => {
                    const cases = [
                        ["dawn-of-the-emperors-local:d294223f54d5ea0b", ["2,500 cn", "250 lb", "carrying capacity", "11 + Dex modifier"]],
                        ["mystara-fan-names-reference:afe258c608a2edc8", ["0 [19]", "130 lb", "tournament suit"]],
                        ["dmg-35-reference:c5deb249aa77ccd1", ["masterwork banded mail", "120 lb", "Splint Armor"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy crossbow alias links to the verified 2024 weapon': '''(async () => {
                    inspect("open5e-srd-2014:srd_crossbow-heavy-2", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Verified 2024 enhancement", "Heavy Crossbow", "+2 to attack and damage"]
                        .every(value => text.includes(value));
                })()''',
                '2024 Net shows its official save and escape rules': '''(async () => {
                    inspect("open5e-srd-2024:srd-2024_net", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Published 2024 combat reference", "No direct damage", "15 ft", "DC 10 Strength"]
                        .every(value => text.includes(value));
                })()''',
                'BG3 armor shows native damage reduction and training exceptions': '''(async () => {
                    inspect("bg3-wiki:18", grid.firstElementChild);
                    await itemDetails;
                    const scale = inspection.textContent;
                    inspect("bg3-wiki:8156", grid.firstElementChild);
                    await itemDetails;
                    const helldusk = inspection.textContent;
                    inspect("bg3-wiki:10413", grid.firstElementChild);
                    await itemDetails;
                    const sentinel = inspection.textContent;
                    return scale.includes("Magical Plate (-1)") && scale.includes("1 from incoming damage of any type")
                        && helldusk.includes("The wearer is proficient with this armor")
                        && sentinel.includes("BG3 shield training") && sentinel.includes("Heightened Awareness");
                })()''',
                'Legacy Mithral and Shield show verified 2024 armor rules': '''(async () => {
                    inspect("open5e-srd-2014:srd_mithral-armor-plate", grid.firstElementChild);
                    await itemDetails;
                    const mithral = inspection.textContent;
                    inspect("open5e-srd-2014:srd_mithral-armor-half-plate", grid.firstElementChild);
                    await itemDetails;
                    const halfPlate = inspection.textContent;
                    inspect("open5e-srd-2014:srd_shield", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    return mithral.includes("Verified 2024 armor counterpart") &&
                        mithral.includes("Armor class18") && mithral.includes("Strength requirementNone") &&
                        mithral.includes("Stealth disadvantageNo") && shield.includes("Armor class bonus+2") &&
                        ["Verified 2024 armor counterpart", "Armor class15 + Dex modifier (max +2)",
                            "Stealth disadvantageNo"].every(value => halfPlate.includes(value));
                })()''',
                '2024 armor families show attunement and Mithral exceptions': '''(async () => {
                    inspect("open5e-srd-2024:srd-2024_armor-of-resistance-splint", grid.firstElementChild);
                    await itemDetails;
                    const resistance = inspection.textContent;
                    inspect("open5e-srd-2024:srd-2024_mithral-armor-plate", grid.firstElementChild);
                    await itemDetails;
                    const mithral = inspection.textContent;
                    return resistance.includes("AttunementRequired") &&
                        mithral.includes("Strength requirementNone") && mithral.includes("Stealth disadvantageNo");
                })()''',
                'Legacy Dragon Scale Mail shows the 2024 variant and its rule change': '''(async () => {
                    inspect("open5e-srd-2014:srd_dragon-scale-mail", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return text.includes("Verified 2024 armor counterpart") && text.includes("Armor class15")
                        && text.includes("2024 rules note") && text.includes("Magic action");
                })()''',
                'Cursed armor shows published plate counterpart and attunement': '''(async () => {
                    inspect("open5e-srd-2014:srd_demon-armor", grid.firstElementChild);
                    await itemDetails;
                    const demon = inspection.textContent;
                    inspect("open5e-srd-2024:srd-2024_armor-of-vulnerability-padded-armor", grid.firstElementChild);
                    await itemDetails;
                    const padded = inspection.textContent;
                    return demon.includes("Verified 2024 armor counterpart") && demon.includes("Armor class19")
                        && demon.includes("1d8 Slashing") && demon.includes("Unarmed Strikes")
                        && padded.includes("AttunementRequired") && padded.includes("vulnerability to the other two");
                })()''',
                'Armor cards distinguish shield bonuses and worn AC': '''(async () => {
                    inspect("open5e-srd-2024:srd-2024_arrow-catching-shield", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    inspect("open5e-srd-2024:srd-2024_plate-armor-plus-1", grid.firstElementChild);
                    await itemDetails;
                    const plate = inspection.textContent;
                    return shield.includes("Armor class bonus+2") && shield.includes("extra +2 AC against ranged")
                        && plate.includes("Armor class19") && plate.includes("Rare") && plate.includes("Base cost5500 gp");
                })()''',
                'Diablo II unique weapon has native damage and source': '''(async () => {
                    inspect("diablo-2-reference:0192f30052d4ae98", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return text.includes("Arreat Summit") && text.includes("Damage")
                        && Array.from(inspection.querySelectorAll("a")).some(link => link.href.includes("/elite/upolearms"));
                })()''',
                'Legacy Dagger +2 shows the verified 2024 bonus and mastery': '''(async () => {
                    inspect("open5e-srd-2014:srd_dagger-2", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Verified 2024 enhancement", "+2 to attack and damage", "Nick", "20/60 ft"]
                        .every(value => text.includes(value));
                })()''',
                'BG3 restricted equipment explains player availability': '''(async () => {
                    inspect("bg3-wiki:27980", grid.firstElementChild);
                    await itemDetails;
                    const branch = inspection.textContent.includes("cannot equip it");
                    inspect("bg3-wiki:31041", grid.firstElementChild);
                    await itemDetails;
                    return branch && inspection.textContent.includes("unavailable through normal Patch 8 gameplay");
                })()''',
                'Diablo II sword shows separate native damage modes': '''(async () => {
                    inspect("diablo-2-reference:2c9596b23ad6d909", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Arreat Summit", "One-handed damage (Barbarian only)", "14–40", "39–60", "Max sockets"]
                        .every(value => text.includes(value));
                })()''',
                'GAZ1 sword shows original source and the playable 2024 draft': '''(async () => {
                    inspect("gaz1-karameikos-local:1b271b99d66a7272", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["Printed p. 45", "1d8 Slashing", "1d10 Slashing", "Sap", "DM review"]
                        .every(value => text.includes(value));
                })()''',
                '2024 Dagger shows damage, thrown range, and mastery': '''(async () => {
                    inspect("open5e-srd-2024:srd-2024_dagger", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return /1d4 piercing/i.test(text) && text.includes("20/60 ft") && text.includes("Nick")
                        && !text.includes("provisional profile");
                })()''',
                'BG3 Bloodthirst shows native damage and ability links': '''(async () => {
                    inspect("bg3-wiki:9688", grid.firstElementChild);
                    await Promise.all([itemDetails, bg3WeaponRules]);
                    const text = inspection.textContent;
                    return text.includes("1d4 + 2") && text.includes("Exploit Weakness")
                        && Array.from(inspection.querySelectorAll("a")).some(link => link.href.includes("bg3.wiki"))
                        && !text.includes("provisional profile");
                })()''',
                'Savage Coast Boomerang shows the playable draft and legacy source': '''(async () => {
                    inspect("savage-coast-local:6ba83af5224e6597", grid.firstElementChild);
                    await itemDetails;
                    const draft = Array.from(inspection.querySelectorAll("details")).find(details =>
                        details.querySelector("summary").textContent.includes("2024 tabletop profile"));
                    return draft && draft.open && draft.textContent.includes("1d4 Bludgeoning")
                        && draft.textContent.includes("20/60 ft") && draft.textContent.includes("DM review")
                        && inspection.textContent.includes("AD&D source facts")
                        && !inspection.textContent.includes("provisional profile");
                })()''',
                'Mercy Mace preserves inherited Sap mastery': '''(async () => {
                    inspect("thunder-rift:mercy-mace", grid.firstElementChild);
                    await itemDetails;
                    return inspection.textContent.includes("Sap") && inspection.textContent.includes("2d8");
                })()''',
                'Arrow of Justice shows its activation, damage, and saves': '''(async () => {
                    inspect("gazetteer-local-pdf-reference:ee88cccbaef81eef", grid.firstElementChild);
                    await itemDetails;
                    const text = inspection.textContent;
                    return ["GAZ8 p. 11", "120 ft", "2d6 Force", "DC 13 Strength", "Magic action", "DM review"]
                        .every(value => text.includes(value));
                })()''',
                'Mystara Ballista and Bolt share published rules and link both ways': '''(async () => {
                    const engine = "mystara-fan-names-reference:3ffbb53cafbb75be";
                    const bolt = "mystara-fan-names-reference:86a0c93771c65462";
                    const button = label => Array.from(inspection.querySelectorAll("button"))
                        .find(control => control.textContent === label);
                    inspect(engine, grid.firstElementChild);
                    await itemDetails;
                    const engineText = inspection.textContent;
                    button("View Ballista Bolt ammunition").click();
                    await itemDetails;
                    const boltText = inspection.textContent;
                    const openedBolt = selected === bolt;
                    button("View Ballista siege engine").click();
                    await itemDetails;
                    return openedBolt && selected === engine && engineText.includes("50")
                        && [engineText, boltText].every(text => text.includes("3d10 Piercing")
                            && text.includes("480 ft") && !text.includes("provisional profile"));
                })()''',
                'Reject inverted buy budget': '''(() => {const prior=searchId;byId("price-min").value="30";byId("price-max").value="10";
                    byId("price-max").dispatchEvent(new Event("change"));
                    return !byId("budget-error").hidden && searchId===prior;})()''',
                'Blinsky hidden under About': '''!byId("about").open && byId("blinsky-shop").hidden
                    && byId("visit-blinsky").closest("#about")===byId("about")''',
                'Blinsky stock and source prices': '''byId("about").open=true;byId("visit-blinsky").click();
                    !byId("blinsky-shop").hidden && shopStock.length===6
                    && shopStock.map(item=>item.shopCopper).sort((a,b)=>a-b).join(",")==="9,9,9,9,90,90"''',
                'Blinsky basket totals': '''(() => {const adds=byId("shop-stock").querySelectorAll(".shop-add");
                    adds[0].click(); adds[4].click(); return byId("basket-total").textContent==="Total · 9 sp 9 cp";})()''',
                'Blinsky Jack springs and the eye fades without intercepting taps': '''(() => {
                    const jack = byId("jack-box");
                    jack.click();
                    const sprang = jack.classList.contains("jack-open");
                    const savedTimeout = window.setTimeout;
                    let reveal;
                    try {
                        window.setTimeout = callback => { reveal = callback; };
                        scheduleShopEye();
                    } finally {
                        window.setTimeout = savedTimeout;
                    }
                    reveal();
                    const eye = byId("shop-eye");
                    const appeared = !eye.hidden && getComputedStyle(eye).pointerEvents === "none"
                        && !!eye.style.getPropertyValue("--gaze-x");
                    eye.dispatchEvent(new Event("animationend"));
                    return sprang && appeared && eye.hidden;
                })()''',
                'Blinsky music starts on demand and can be muted': '''(async () => {
                    const music = byId("shop-music");
                    const toggle = byId("shop-music-toggle");
                    if (!music.paused) toggle.click();
                    toggle.click();
                    const started = await new Promise(resolve => {
                        const until = Date.now() + 3000;
                        const check = () => {
                            if (!music.paused && music.currentTime > 0) resolve(true);
                            else if (Date.now() >= until || music.error) resolve(false);
                            else setTimeout(check, 30);
                        };
                        check();
                    });
                    toggle.click();
                    const muted = music.paused;
                    shopMusicWanted = true;
                    return started && muted;
                })()''',
                'Clear Blinsky basket and return': '''(() => {byId("clear-basket").click(); const empty=toyBasket.size===0;
                    byId("leave-shop").click();byId("about").open=false;return empty&&byId("blinsky-shop").hidden;})()''',
            }
            for name, expression in checks.items():
                total += 1
                try:
                    assert dev.eval(expression, user_gesture=name.startswith("Blinsky music"))
                    print('PASS ' + name)
                except AssertionError as error:
                    failures.append(name)
                    print(f'FAIL {name}: {error}')
        finally:
            try:
                dev.eval('armoryQA.restore(); true')
            finally:
                socket.close()
    finally:
        subprocess.run([*adb, 'forward', '--remove', 'tcp:' + port], check=True)
    print(f'{total - len(failures)}/{total} checks passed')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
