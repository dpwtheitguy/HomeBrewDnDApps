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
