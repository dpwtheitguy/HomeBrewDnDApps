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
                        ["Armor accessory", "Use as armor+0", "no separate AC"]
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
                'Four public common armor entries show their published rules': '''(async () => {
                    const cases = [
                        ["dndbeyond:36571", ["never gets dirty", "13 + Dex modifier", "2024 armor counterpart"]],
                        ["dndbeyond:36589", ["Magic action to doff", "Armor class18"]],
                        ["dndbeyond:36837", ["harmless, odorless smoke", "Armor class18"]],
                        ["dndbeyond:27116", ["Armor class bonus+2", "TrainingShield", "Bonus Action"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                        if (![...inspection.querySelectorAll("a")].some(link =>
                            link.textContent === "Read published rules" && link.href.includes("roll20.net"))) return false;
                    }
                    return true;
                })()''',
                'Mithral Half Plate +1 keeps its bonus and removes Stealth disadvantage': '''(async () => {
                    inspect("dndbeyond:722094", grid.firstElementChild);
                    await itemDetails;
                    const terms = ["Armor class16 + Dex modifier (max +2)", "Stealth disadvantageNo",
                        "AttunementNone", "Dhargun Ironworks wedding gifts"];
                    return terms.every(term => inspection.textContent.includes(term))
                        && [...inspection.querySelectorAll("a")].some(link => link.href.endsWith("#MithralArmor"));
                })()''',
                'Salubrious Armor shows both bases and the corrected healing bonus': '''(async () => {
                    const cases = [
                        ["dndbeyond:11628225", "Verified 2024 armor rules"],
                        ["adventurers-vault-1-reference:0bc22a5f6002434b", "D&D 2024 conversion using the published counterpart"],
                    ];
                    for (const [id, label] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        const terms = [label + " · Scale Mail", label + " · Plate Armor",
                            "Armor class15 + Dex modifier (max +2)", "Armor class19",
                            "bonus becomes +2 until the end of your next turn"];
                        if (id === "dndbeyond:11628225" && ![...inspection.querySelectorAll("a")].some(link =>
                            link.textContent === "Read published rules" && link.href.includes("/posts/2222-"))) return false;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Expanded armor preserves published exceptions and curses': '''(async () => {
                    const cases = [
                        ["dndbeyond:21731", ["Armor class18", "Stealth disadvantageNo", "DC 15 Constitution", "10d10 + 45"]],
                        ["dndbeyond:3001260", ["Armor class14 + Dex modifier", "Stealth disadvantageNo", "full Dexterity modifier"]],
                        ["dndbeyond:316637", ["Critical Hit", "Strength or Constitution", "armor rules · Plate Armor"]],
                        ["dndbeyond:316763", ["Armor class bonus+2", "every two allies", "Force damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        const missing = terms.filter(term => !details.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                        if (id === "dndbeyond:3001260" && details.includes("(max +2)")) return false;
                    }
                    return true;
                })()''',
                'Dragon armor and sentient shields show their complete combat rules': '''(async () => {
                    const cases = [
                        ["dndbeyond:4047224", ["Armor class bonus+2", "2d6 Thunder", "within 1 mile"]],
                        ["dndbeyond:842285", ["Armor class20", "Resistance to Poison", "Grappled"]],
                        ["dndbeyond:843176", ["Armor class bonus+4", "save DC 21", "DC 18 Wisdom", "120 feet", "1% chance"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return [...inspection.querySelectorAll("a")].some(link => link.href.endsWith("#WallofFire"));
                })()''',
                'Book of Many Things armor shows eligible bases and combat exceptions': '''(async () => {
                    const cases = [
                        ["dndbeyond:7526586", ["10-foot-radius", "DC 15 Constitution", "including you"]],
                        ["dndbeyond:7526611", ["5 charges", "1d4 + 1", "Levitate"]],
                        ["dndbeyond:7526627", ["Armor class bonus+2", "1d6 Slashing", "60 feet"]],
                        ["dndbeyond:7526655", ["DC 20 Constitution", "24 hours", "recharges at dawn"]],
                        ["dndbeyond:7526761", ["Armor class bonus+3", "Speed is halved", "Initiative d20"]],
                        ["dndbeyond:7526781", ["DC 11 Charisma", "30 feet", "Wish"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        const missing = terms.filter(term => !details.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                        if (id === "dndbeyond:7526586" && details.includes("armor rules · Plate Armor")) return false;
                    }
                    return true;
                })()''',
                'Expanded armor cards preserve runes and published shield reactions': '''(async () => {
                    const cases = [
                        ["dndbeyond:7102439", ["Immunity to Fire", "3d6 Bludgeoning plus 3d6 Fire", "once per turn"]],
                        ["dndbeyond:1752526", ["Stealth disadvantageNo", "Resistance to Fire", "Plate Armor"]],
                        ["dndbeyond:382908", ["specific mind flayer or thrall", "Charisma saves"]],
                        ["dndbeyond:10886056", ["Armor class bonus+3", "Large or smaller", "15 feet"]],
                        ["dndbeyond:5554585", ["Armor class bonus+4", "+2 to Initiative", "Incapacitated"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent.toLowerCase();
                        const missing = terms.filter(term => !details.includes(term.toLowerCase()));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return true;
                })()''',
                'Expanded item cards distinguish source-specific powers': '''(async () => {
                    const cases = [
                        ["dndbeyond:351921", ["Armor class19", "2d10 charges", "5 HP", "+8 to hit"]],
                        ["dndbeyond:342867", ["3d6 Necrotic", "DC 17", "8 hours"]],
                        ["dndbeyond:10674160", ["2d6", "30-foot Cone", "DC 13 Dexterity"]],
                        ["dndbeyond:11914544", ["Required by a spellcaster", "levels total 3"]],
                        ["dndbeyond:12133294", ["Armor class18", "Aura of Protection"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return true;
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
                'Hazirawn and Hellfire Weapon preserve their distinct triggers': '''(async () => {
                    const cases = [
                        ["5602", ["2d6 Slashing", "2d6 Necrotic instead of 1d6", "DC 15 Constitution", "at midnight"]],
                        ["842365", ["kills a Humanoid", "River Styx", "immediately becomes a Lemure", "5-foot radius"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Enhanced boomerangs and yklwas show verified range and damage': '''(async () => {
                    const families = [
                        [["535335", "535336", "535339"], "1d4 Bludgeoning", "60/120 feet",
                            "Dexterity modifier", "returns to your hand on a miss"],
                        [["21941", "21942", "21943"], "1d8 Piercing", "10/30 feet",
                            "Strength modifier", "Chultan warriors"],
                    ];
                    for (const [ids, damage, range, modifier, effect] of families) {
                        for (const [index, id] of ids.entries()) {
                            inspect("dndbeyond:" + id, grid.firstElementChild);
                            await itemDetails;
                            const terms = [damage + " + " + modifier + " + " + (index + 1), range, effect];
                            if (!terms.every(term => inspection.textContent.includes(term)) ||
                                inspection.textContent.includes("2024 provisional profile")) return false;
                        }
                    }
                    return true;
                })()''',
                'Orcus and Dawnbringer cards preserve their named effects': '''(async () => {
                    const cases = [
                        ["5428", ["2024 counterpart", "2d12 Necrotic", "15 Skeletons and 15 Zombies", "1d4 + 3"]],
                        ["5533", ["1d8 Radiant", "Lesser Restoration", "Magic action", "Lost Tomb of Khaem"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Apocalypse weapons show sentience and special throwing rules': '''(async () => {
                    const cases = [
                        ["5589", ["1d12 Slashing", "DC 17 Constitution", "Initiative roll", "Torhild Flametongue"]],
                        ["5582", ["120 feet", "1 inch wide", "DC 16 Dexterity", "3d4 Lightning"]],
                        ["5585", ["Thrown 60/120 feet", "3d4 Thunder", "DC 10 Constitution", "elemental air node"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Elemental weapons show their distinct damage, spells, and rituals': '''(async () => {
                    const cases = [
                        ["5590", ["1d8 Cold", "Thrown 20/60 feet", "barnacles", "Tears of Endless Anguish"]],
                        ["5591", ["1d8 Thunder", "Tremorsense to 60 feet", "DC 17 Constitution", "1d3 expended charges"]],
                        ["5592", ["2d6 Fire", "Finesse, Light, Thrown", "Dance of the All-Consuming Fire"]],
                        ["5593", ["1d6 Lightning", "Finesse, Thrown, Versatile", "Song of the Four Winds"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (![...terms, "Wisdom save DC 17", "2,000 gp"].every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Yawning Portal weapons show curse and object hit rules': '''(async () => {
                    const cases = [
                        ["9379", ["Thrown 50/90 feet", "2d6 Piercing", "against your own AC"]],
                        ["9390", ["Thrown 60/150 feet", "2d6 Piercing", "against your own AC"]],
                        ["9320", ["automatically a Critical Hit", "Bludgeoning or Slashing", "nonmagical sources"]],
                        ["9349", ["2d6 Slashing", "DC 15 Strength", "1 of 7 charges", "Wisdom 2"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("Portal.pdf#page=230"))) return false;
                    }
                    return true;
                })()''',
                'Remaining Book of Many Things weapons show their original effects': '''(async () => {
                    const cases = [
                        ["7526657", ["Sever Threads", "natural 19 or 20", "any attacker"]],
                        ["7526677", ["Fool’s Feint", "DC 15 Intelligence", "separately at dawn"]],
                        ["7526701", ["1d6 Radiant", "Semi-incorporeal", "Resistance to Bludgeoning"]],
                        ["7526751", ["double damage", "2d4 Necrotic", "end of each turn"]],
                        ["7526771", ["Hand 30/90 feet", "Heavy 100/400 feet", "2d8 Fire", "1d3 expended charges"]],
                        ["7526785", ["Zone of Truth", "Dominate Person", "DC 16", "1d4 expended charges"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Book of Many Things planar and aquatic weapons show casting details': '''(async () => {
                    const cases = [
                        ["7526775", ["fewer than 100 Hit Points", "1d6 + 1 petrification charges", "8 hours"]],
                        ["7526777", ["10 feet high and 10 feet wide", "nearest unoccupied space", "recharges at dawn"]],
                        ["7526779", ["Thrown 20/60 feet", "Advantage while you are underwater", "range 1 mile", "6 rounds"]],
                        ["7526787", ["Half Cover and Three-Quarters Cover", "long range", "launcher’s normal damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("/magic-items/" + id))) return false;
                    }
                    return true;
                })()''',
                'Book of Many Things weapons preserve unusual activation rules': '''(async () => {
                    const cases = [
                        ["7526654", ["1d4 Piercing", "10 damage in total", "Utilize action"]],
                        ["7526697", ["20-foot Cube", "Forcecage", "Bludgeoning damage"]],
                        ["7526717", ["pull it 5 feet", "instead of dealing damage", "no saving throw"]],
                        ["7526722", ["15-foot radius", "inside your rune circle", "1d3 expended charges"]],
                        ["7526769", ["30/120 feet", "DC 18 Constitution", "falls Prone"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Book of Many Things weapons show item-specific triggers': '''(async () => {
                    const cases = [
                        ["7526614", ["natural 19 or 20", "DC 15 Constitution", "6d6 Necrotic"]],
                        ["7526617", ["half your Hit Point maximum", "+2", "Cleave"]],
                        ["7526618", ["Advantage against a creature below its Hit Point maximum", "compatible launcher"]],
                        ["7526628", ["150/600 feet", "1d6 Fire", "Utilize action"]],
                        ["7526629", ["Melody of Precision", "Expertise in Performance", "Melody of Reverberation", "Charisma modifier"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("/magic-items/" + id))) return false;
                    }
                    return true;
                })()''',
                'Fizban hoard states and the Topaz Annihilator show their own rules': '''(async () => {
                    const cases = [
                        ["4047217", ["Slumbering · Uncommon", "Wakened · Very Rare", "DC 16 Dexterity",
                            "Ascendant · Legendary", "DC 18", "12d6", "every 30 days"]],
                        ["5917281", ["2d6 Necrotic", "100/300 feet", "10d6 + 40 Force", "True Resurrection or Wish"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Fizban weapon adaptations keep their variants and powers': '''(async () => {
                    const cases = [
                        ["4047184", ["1d8 Radiant", "1d3 expended charges", "Dim Light alone for 10 feet"]],
                        ["4047200", ["80/320 feet", "150/600 feet", "Vex", "Slow"]],
                        ["4047212", ["1d10 Piercing", "3d6 Force", "Lance Topple", "Pike Push"]],
                        ["4047219", ["5d4 damage", "90-foot Cone", "DC 18 Dexterity", "14d6"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("/magic-items/" + id))) return false;
                    }
                    return true;
                })()''',
                'Phandelver weapon variants show the correct base and powers': '''(async () => {
                    const cases = [
                        ["12482", ["both base weapon dice", "dryads", "Topple"]],
                        ["7247071", ["object made of wood", "Venomfang", "Topple"]],
                        ["12465", ["1d6 Bludgeoning", "1d6 Radiant", "Sap"]],
                        ["7247072", ["1d6 Bludgeoning", "20 feet", "Sap"]],
                        ["7247070", ["1d12 Slashing", "DC 15 Strength", "Cleave"]],
                        ["7247073", ["1d8 Piercing", "60-foot Emanation", "while it is held", "recharges at dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("/magic-items/" + id))) return false;
                    }
                    return true;
                })()''',
                'Eberron weapon families show their distinct triggers and bonuses': '''(async () => {
                    const cases = [
                        ["10886041", ["Requires attunement", "Reaction", "DC 15 Constitution", "1d4 expended charges"]],
                        ["10886055", ["Requires attunement", "+1 to ranged attack rolls", "ignore that property", "hits or misses"]],
                        ["10886064", ["No attunement", "+1 to melee and ranged", "returns to your hand immediately"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            inspection.textContent.includes("2024 provisional profile") ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.endsWith("equipment#Weapons"))) return false;
                    }
                    return true;
                })()''',
                'Energy Bow Greatclub and Niko mace show the published powers': '''(async () => {
                    const cases = [
                        ["9058960", ["Energy Bow · Longbow", "Energy Bow · Shortbow", "DC 15 Strength",
                            "DC 20 Strength (Athletics)", "5-foot Cube", "Energy Ladder"]],
                        ["9058872", ["1d8 Thunder", "30-foot Cone", "50 Bludgeoning", "DC 20 Constitution",
                            "Earthquake recharges at dawn"]],
                        ["9058987", ["Requires attunement by a Spellcaster", "+9 to hit", "90-foot casting range",
                            "6 charges", "1d6 expended charges at dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link => link.href.includes("/magic-items/" + id))) return false;
                    }
                    return true;
                })()''',
                'Published weapon variants and ammunition show exact rules': '''(async () => {
                    const cases = [
                        ["36822", ["Moon-Touched Sword · Glaive", "Moon-Touched Sword · Shortsword",
                            "10 feet melee with Reach", "1d8 Piercing", "In Darkness"]],
                        ["36839", ["DC 10 Strength saving throw", "falls Prone", "compatible launcher"]],
                        ["11295689", ["Launcher damage +1", "Launcher damage +2", "Launcher damage +3",
                            "loses its magic", "lots of 10 or 20"]],
                        ["36838", ["Antimagic Field", "150/600 feet", "normal ammunition recovery"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term)) ||
                            details.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Ravenloft shortsword and axe retain their source-specific powers': '''(async () => {
                    const cases = [
                        ["5554570", "82", ["1d6 Piercing", "30-foot Emanation", "recharges at dawn", "K74h"]],
                        ["5554591", "199", ["ordinary plant", "1d8 Slashing", "even on a miss", "2 lb"]],
                    ];
                    for (const [id, page, terms] of cases) {
                        inspect("dndbeyond:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term)) ||
                            ![...inspection.querySelectorAll("a")].some(link =>
                                link.href.includes("Curse%20of%20Strahd.pdf#page=" + page))) return false;
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
                'Diablo II armor cards show native defense and separate tabletop AC': '''(async () => {
                    const cases = [
                        ["01d717672609a221", ["Defense (game)", "410-524", "15 + Dex modifier (max +2)", "Open 2024 Half Plate Armor"]],
                        ["953d379727aca7a6", ["Paladin only", "40%", "Armor class bonus+2", "normal Shield training"]],
                        ["789568bb9f4e2f02", ["Necromancer only", "23%", "Armor class bonus+2", "rigid shield backing"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("diablo-2-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Diablo II unique armor shows native facts and authored effects': '''(async () => {
                    inspect("diablo-2-reference:2881788f41e838a7", grid.firstElementChild);
                    await itemDetails;
                    const shield = inspection.textContent;
                    inspect("diablo-2-reference:e7a12ed5d7fa05c3", grid.firstElementChild);
                    await itemDetails;
                    const mail = inspection.textContent;
                    inspect("diablo-2-reference:d499390f4ac17e61", grid.firstElementChild);
                    await itemDetails;
                    const gold = inspection.textContent;
                    return ["Indestructible", "35% damage reduction", "reduce that damage by 2d8", "twice per Long Rest"]
                        .every(term => shield.includes(term)) &&
                        ["163-172", "DC 15 Constitution", "Speed is 0"].every(term => mail.includes(term)) &&
                        ["356-405", "D&D 2024 unique armor adaptation", "Bright Light within 10 feet"].every(term => gold.includes(term));
                })()''',
                'Diablo II unique plate preserves area saves and armor exceptions': '''(async () => {
                    inspect("diablo-2-reference:cdacf15d0b0df6b0", grid.firstElementChild);
                    await itemDetails;
                    const corpse = inspection.textContent;
                    inspect("diablo-2-reference:a7737c7acb1e3063", grid.firstElementChild);
                    await itemDetails;
                    const tyrael = inspection.textContent;
                    return ["DC 16 Dexterity save", "within 10 feet", "4d6 Fire"].every(term => corpse.includes(term)) &&
                        ["Armor class18", "Strength requirementNone.", "1d8 Radiant"].every(term => tyrael.includes(term));
                })()''',
                'Mystara armor shows verified enhancements and distinct local rules': '''(async () => {
                    const cases = [
                        ["wrath-of-the-immortals-local:ebd0772d6f50f49a", ["Armor class19", "Legendary", "cosmetic"]],
                        ["wrath-of-the-immortals-local:ffda5c5377ad0e7f", ["13 + Dex modifier", "Very Rare", "personal Dexterity bonus"]],
                        ["gazetteer-local-pdf-reference:579294a755b5b670", ["Armor class18", "10 lb", "Linias"]],
                        ["gazetteer-local-pdf-reference:6a9440c634d1adb8", ["Armor class bonus+2", "2d4 Slashing", "20/60 ft", "does not return"]],
                        ["gazetteer-local-pdf-reference:d40bbd47d4ca7ecd", ["Armor accessory", "no separate AC"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara Immortal and creature armor preserves source effects': '''(async () => {
                    const cases = [
                        ["mystara-monstrous-compendium-local:d118fd136619e510", ["Resistance to Fire", "four sound hides", "1d4 weeks"]],
                        ["mystara-monstrous-compendium-local:a8049d2ecb89761f", ["Armor class bonus+2", "20-foot radius", "50 gp of ruby dust"]],
                        ["local-mystara-handbook-tables:8a8d72cf9f72e0bf", ["Fire Resistance", "closest Red Dragon within 30 miles", "15 + Dex modifier"]],
                        ["wrath-of-the-immortals-local:546a4cad7f1a4a0a", ["Armor class20", "descending AC by nine", "Very Rare"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Wrath weapons show published bonuses and distinct artifact effects': '''(async () => {
                    const cases = [
                        ["1685fc1ca41a08aa", ["Greatsword +2", "2d6 Slashing", "Graze"]],
                        ["27c9cc14fce3682d", ["20/60 ft thrown", "hit a Giant", "extra 1d8"]],
                        ["9a661b1e329c5f56", ["hit against a Dragon", "30-foot Emanation", "2d6 Cold"]],
                        ["04374080dc3bf5b9", ["Magic action", "within 30 feet", "flies back to your hand"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("wrath-of-the-immortals-local:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Wrath artifact cards show action costs saves and recovery': '''(async () => {
                    const cases = [
                        ["911442c04239a270", ["natural 19 or 20", "DC 17 Constitution", "4d6 Slashing"]],
                        ["48c0d2e9e1eadad9", ["No direct damage", "DC 10 Strength", "30 feet with Flying", "stays in place"]],
                        ["db6a70a41c17e186", ["1d10 Bludgeoning", "3 charges", "Rheddrian directly", "randomly chosen prepared spell"]],
                        ["41e442619c114b08", ["portion of its +3 enhancement to AC", "can breathe water", "1d8 Piercing"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("wrath-of-the-immortals-local:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara weapon cards show senses storage and target-specific damage': '''(async () => {
                    const cases = [
                        ["dawn-of-the-emperors-local:9c32c49ff44a95f8", ["Intelligence 7", "Invisible condition within 20 feet", "extra 1d6 Fire"]],
                        ["mystara-monstrous-compendium-local:25cd4d9c2e6f57e1", ["holds up to three spells", "A Nagpa deals 1d8"]],
                        ["mystara-monstrous-compendium-local:2e9fcab3fdc37823", ["hit an Efreeti", "2d6 Cold"]],
                        ["local-mystara-handbook-tables:d5539f39f66f07b3", ["1d4 Bludgeoning", "Finesse, Light", "Nick"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Gazetteer weapon drafts show control gear and bow differences': '''(async () => {
                    const cases = [
                        ["gazetteer-equipment-reference:1b56b9fc840b85eb", ["No direct damage", "15 feet", "Restrained", "DC 10 Strength"]],
                        ["gazetteer-equipment-reference:315e78dd072c732d", ["Speed becomes 0", "20 feet", "Utilize action"]],
                        ["gazetteer-equipment-reference:ee675d0479ab7828", ["40/160 ft", "Requires a Javelin"]],
                        ["gazetteer-bow-reference:e0876799868e6e9e", ["80/320 ft", "Can be fired while mounted"]],
                        ["gazetteer-equipment-reference:578f64f766b15b4b", ["150/600 ft", "1d8 Piercing", "Revised Bows"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Karameikos equipment preserves enhancements and the dagger trigger': '''(async () => {
                    const cases = [
                        ["02fbb75e850bc390", ["currently concentrating on a spell", "instead of +2", "supplied PDF p. 60"]],
                        ["c314f33975834496", ["Warhammer +2", "1d8 Bludgeoning", "Push"]],
                        ["a9b88d9954fb92b7", ["Armor class19", "Legendary", "supplied PDF p. 46"]],
                        ["e2aae6a7f0f1e5e9", ["Armor class bonus+4", "Ring of Protection", "Shield training"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("gazetteer-npc-equipment-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Blackflame cards preserve storage reflection and non-AC protection': '''(async () => {
                    const cases = [
                        ["gaz8-name-reference:da62eb18e833fa48", ["attack roll only", "1d10 + 10", "random stored object"]],
                        ["gaz8-name-reference:405d59fd0824ef47", ["10-foot radius", "40-foot-long", "DC 15 Dexterity"]],
                        ["gaz8-name-reference:3033f3098efb3837", ["20-foot Emanation", "targets only you", "original caster"]],
                        ["gaz8-name-reference:14b3126f248071f7", ["no AC bonus", "Resistance to Cold and Fire", "0 lb"]],
                        ["gazetteer-npc-equipment-reference:ee4c6df9d0d0e9e1", ["Armor class20", "Ludwig von Hendriks", "Very Rare"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Atruaghin cards show poison modes and armor exceptions': '''(async () => {
                    const cases = [
                        ["atruaghin-dmg-local:e43c4640017428d7", ["DC 15 Constitution", "2d10 Poison", "Sleep", "Paralyzed"]],
                        ["atruaghin-dmg-local:736f119cc8cd0497", ["3 lb", "14 + Dex modifier", "unravels"]],
                        ["atruaghin-dmg-local:a8d7c57c3bca2d66", ["no ordinary shield bonus", "incorporeal Undead", "Disadvantage"]],
                        ["atruaghin-players-guide-local:10b30d0b2584c423", ["1d8 Fire", "Proficiency Bonus", "spectral arrow"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy DMG armor shows 2024 AC and labels conversions': '''(async () => {
                    const cases = [
                        ["dmg-1e-reference:f4fe2e4af2ee2fe2", ["Armor class19", "Verified 2024 equipment mapping", "III.F"]],
                        ["dmg-1e-reference:d6ca7bff4c84ea86", ["Armor class bonus+5", "Very Rare"]],
                        ["dmg-1e-reference:5356aaf55225d639", ["Armor class21", "Strength requirementNone", "Stealth disadvantageNo", "conversion draft"]],
                        ["dmg-1e-reference:e6bb10fc4bad57b2", ["Critical Hits against you become normal hits", "AttunementRequired"]],
                        ["dmg-2e-reference:ce4a9d08045577e1", ["Armor class18", "table 105"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy DMG special armor shows charges curses and reactions': '''(async () => {
                    const cases = [
                        ["dmg-1e-reference:5003ee3a0bd2f04d", ["Armor class by charges", "cannot regain", "up to 8 hours"]],
                        ["dmg-2e-reference:e030cf575bdcef9b", ["Cursed armor class14, 15, or 16", "natural 20"]],
                        ["dmg-2e-reference:62ade0786a04042d", ["Cursed shield bonus+0", "within 10 feet"]],
                        ["dmg-2e-reference:2423313ed73a2e69", ["+5 AC total", "roll a d10"]],
                        ["dmg-2e-reference:de359f74f62a0dee", ["14 + Dex modifier (max +2)", "treated as trained", "Published 2024 counterpart"]],
                        ["dmg-2e-reference:9f0e259e0ad010e7", ["2d6 charges", "DC 15 Wisdom", "30-foot Emanation"]],
                        ["dmg-2e-reference:aef79c18677bac3c", ["Bonus Action", "Truesight", "Armor class17"]],
                        ["dmg-2e-reference:c3377e7c6f6e7771", ["Charisma (Persuasion)", "Frightened condition"]],
                        ["dmg-2e-reference:a7d39d7d8edaa926", ["18 against ranged weapon attacks", "19 against other attacks"]],
                        ["dmg-2e-reference:2e3a515dad808b1d", ["Disadvantage on Charisma", "Remove Curse"]],
                        ["dmg-2e-reference:a90a7727f4a39e25", ["15 + Dex modifier (max +2)", "Medium armor"]],
                        ["dmg-2e-reference:edcdfbe057a290bd", ["Armor class14", "130 lb", "Table 27"]],
                        ["dmg-2e-reference:bafc45cdb54d9584", ["48.75 lb", "Critical Hit", "25%"]],
                        ["dmg-2e-reference:c1819e413941a417", ["6 feet 6 inches", "250 lb", "14 + Dex modifier", "Open published 2024 counterpart"]],
                        ["dmg-2e-reference:828266aa4a13406d", ["no separate AC bonus", "Great Helm row"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!terms.every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'D&D 3.5 armor shows verified and converted AC': '''(async () => {
                    const cases = [
                        ["dmg-35-reference:0c35cd5327472d87", ["16 + Dex modifier (max +2)", "Very Rare", "p. 113"]],
                        ["dmg-35-reference:6dbb586e767df27a", ["Armor class bonus+3", "Uncommon", "Verified 2024 equipment mapping"]],
                        ["dmg-35-reference:db4f44212c1486c7", ["17 + Dex modifier (max +2)", "Legendary", "conversion draft"]],
                        ["dmg-35-reference:a153508f6388f498", ["Armor class bonus+4", "occupies one hand", "conversion draft"]],
                        ["dmg-35-reference:1a12c2006b6212cc", ["1d8 Slashing", "Abyssal", "Remove Curse"]],
                        ["dmg-35-reference:7804a6bfdaf74b94", ["Armor class20", "up to 10 ft.", "Published 2024 counterpart"]],
                        ["dmg-35-reference:dac3457dc8c40bbe", ["20 feet straight", "2d6", "mount"]],
                        ["dmg-35-reference:92b4e00f098bb896", ["120/480 feet", "1d10", "three spines"]],
                        ["dmg-35-reference:fae0641c67338f45", ["Armor class20", "before damage", "seven days later"]],
                        ["dmg-35-reference:b5613e7549a47912", ["133 lb", "266 lb", "Concentration"]],
                        ["dmg-35-reference:8f9f91d52600bd6d", ["half the listed raw-material cost", "level 1–3", "Spell Scroll"]],
                        ["dmg-35-reference:9da803feb17b26a0", ["25 lb", "lethargy", "Strength requirementNone"]],
                        ["dmg-35-reference:a446fcafe8835edb", ["DC 17 Dexterity", "10-foot Cube", "second dawn"]],
                        ["dmg-35-reference:79211eaca6e4d533", ["Armor class bonus+2", "Half Cover", "Utilize action"]],
                        ["dmg-35-reference:0a7b78d2a1e37610", ["15 + Dex modifier", "150 gp", "40 lb"]],
                        ["dmg-35-reference:4b5de21d35a42563", ["Armor class bonus+2", "2.5 lb", "darkwood"]],
                        ["dmg-35-reference:084a0eb692ad1954", ["Armor class18", "Resistance to Lightning"]],
                        ["dmg-35-reference:17c64070fe4b05b8", ["One shield", "Thunder damage", "reduce that damage by 10"]],
                        ["dmg-35-reference:533684ed1ebd3331", ["adds no AC", "reduce that damage by 20", "next dawn"]],
                        ["dmg-35-reference:9e59bcb13de27714", ["Bonus Action", "freeing both hands", "1 minute"]],
                        ["dmg-35-reference:a826105644abdcdc", ["level 9 or lower", "Spell attack rolls", "Disadvantage"]],
                        ["dmg-35-reference:eba10ceab91d6d09", ["Critical Hit", "normal hit"]],
                        ["dmg-35-reference:ad7ff581e80e999f", ["Armor class bonus+3", "1d4", "Piercing"]],
                        ["dmg-35-reference:de0ab3aecec8b9db", ["Half Plate or Plate Armor", "8 hours", "recharges at dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        const missing = terms.filter(term => !details.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return true;
                })()''',
                'Dwarven Plate links to the published magic armor card': '''(async () => {
                    inspect("dmg-35-reference:7804a6bfdaf74b94", grid.firstElementChild);
                    await itemDetails;
                    const related = [...inspection.querySelectorAll("button")]
                        .find(button => button.textContent === "Open published 2024 counterpart");
                    if (!related) return false;
                    related.click();
                    await itemDetails;
                    return inspection.textContent.includes("Dwarven Plate")
                        && inspection.textContent.includes("up to 10 ft.")
                        && !inspection.textContent.includes("legacy suit");
                })()''',
                'DMG 3.5 weapons show verified 2024 dice and mastery': '''(async () => {
                    const cases = [
                        ["dmg-35-reference:2fd0d4d5dc8e380b", ["Simple ranged", "20/60 ft thrown", "Vex"]],
                        ["dmg-35-reference:f9ab5fa1437f6b83", ["1d12", "+1 to attack and damage", "Cleave"]],
                        ["dmg-35-reference:94ba88205605b2dd", ["10 ft melee", "two hands when you are unmounted", "Topple"]],
                        ["dmg-35-reference:cfda535e670d4be3", ["20/60 ft thrown", "Nick", "craftsmanship"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return true;
                })()''',
                'Named DMG weapons display their published 2024 effects': '''(async () => {
                    const cases = [
                        ["dmg-35-reference:2908af3f4ee1599b", ["150/600 ft", "3d6 Piercing", "seven days"]],
                        ["dmg-35-reference:3a7c44ca206643f2", ["fewer than 100 HP", "DC 15 Constitution", "1d8 + 1 charges"]],
                        ["dmg-35-reference:70243a6190019dbe", ["20/60 ft", "2d8 Force", "Dwarf"]],
                        ["dmg-35-reference:9aab5d05003a19c4", ["30 Slashing", "natural 20", "Verified 2024 counterpart"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    return [...inspection.querySelectorAll("button")].some(button =>
                        button.textContent === "Open published 2024 weapon");
                })()''',
                'Legacy staves show current charge costs and link to modern staff cards': '''(async () => {
                    inspect("dmg-35-reference:5f4b7de783af3b00", grid.firstElementChild);
                    await itemDetails;
                    const power = inspection.textContent;
                    if (!["2d8 + 4", "DC 17 Dexterity", "30-foot Emanation", "Wall of Force"].every(value => power.includes(value))) return false;
                    inspect("dmg-35-reference:1ab5c397356dca27", grid.firstElementChild);
                    await itemDetails;
                    const related = [...inspection.querySelectorAll("button")]
                        .find(button => button.textContent === "Open published 2024 staff");
                    if (!related || !inspection.textContent.includes("Pass without Trace cost 2")) return false;
                    related.click();
                    await itemDetails;
                    return inspection.textContent.includes("Published 2024 staff rules")
                        && inspection.textContent.includes("Wall of Thorns costs 6");
                })()''',
                'Luck Blade variants retain wishes and AD&D darts show per-weapon damage': '''(async () => {
                    for (const [id, count] of [["178523807355d19a", 0], ["d5567cc9bad1dbbd", 1],
                        ["88d9dcccb086ec6b", 2], ["68dbb88212ffff68", 3]]) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!details.includes(count + " Wish charges remaining")
                                || !details.includes("reroll recharges at dawn")
                                || (count === 0 && details.includes("spend a Wish charge"))) return false;
                    }
                    inspect("dmg-2e-reference:a25be151305d8c7d", grid.firstElementChild);
                    await itemDetails;
                    return ["Dart (3d4)", "1d4 + Strength or Dexterity", "20/60 ft thrown", "Vex"]
                        .every(value => inspection.textContent.includes(value));
                })()''',
                'AD&D named weapons show published effects and original source links': '''(async () => {
                    const cases = [
                        ["dmg-2e-reference:5717b7cc83a31802", ["DC 15 Strength", "2d6", "Giant"]],
                        ["dmg-2e-reference:f3e3aa8bc9a5c8f4", ["DC 17 Constitution", "Warhammer", "20/60 ft"]],
                        ["dmg-2e-reference:492de4de5e41af35", ["DC 17 Dexterity", "Retributive Strike"]],
                        ["dmg-2e-reference:148be346d484ab9e", ["1d3 charges", "failed D20 Test"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                        if (![...inspection.querySelectorAll("a")].some(link => link.href.includes("corerule-page=DD"))) return false;
                    }
                    return true;
                })()''',
                'AD&D transforming staves show distinct attack modes': '''(async () => {
                    const cases = [
                        ["dmg-2e-reference:680079a22843134e", ["6 to 12 feet", "10-foot reach", "original item is +5"]],
                        ["dmg-2e-reference:6e18ee13d4ebe531", ["2d4", "Sap mastery", "10-foot reach"]],
                        ["dmg-2e-reference:a92f8721d4212a02", ["11–20 gives +3", "On a 20", "Magic action"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
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
                'Adventurer’s Vault armor shows compatible bases and converted effects': '''(async () => {
                    const cases = [
                        ["be5eceafe26ff24d", ["Chain Mail", "Armor class18", "2 Piercing", "1 minute"]],
                        ["6e983289cd873bc8", ["Armor class20", "Temporary Hit Points", "immediately after resolving"]],
                        ["63d64294994e9d5f", ["Armor class20", "Swim Speed", "breathe underwater"]],
                        ["a93d3e44b9c63bba", ["Armor class19", "+2 to Wisdom saving throws", "half your Hit Point maximum"]],
                        ["f07d0f1c1a881dd5", ["Armor class20", "damage you take by 6", "end of your next turn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D plate conversions show charge thresholds and hidden curse': '''(async () => {
                    inspect("dmg-2e-reference:5003ee3a0bd2f04d", grid.firstElementChild);
                    await itemDetails;
                    const ethereal = inspection.textContent;
                    inspect("dmg-1e-reference:e030cf575bdcef9b", grid.firstElementChild);
                    await itemDetails;
                    const cursed = inspection.textContent;
                    return ethereal.includes("21 with 11–20 charges") && ethereal.includes("level 7 spell")
                        && cursed.includes("Identify reports the apparent bonus")
                        && cursed.includes("natural 20") && cursed.includes("14, 15, or 16");
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
