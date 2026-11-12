#!/usr/bin/env python3
"""Check catalog filter composition against the running Android WebView and shared data."""
import argparse
import collections
import json
import re
import sqlite3
import string
import subprocess
import time
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
        case('Vault Blue Wyrm whip search finds all printed enhancements', category='Weapons',
             term='Whip of the Blue Wyrm', facets={'source': 'open5e-vom'}, exact_count=3),
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
        case('Dungeon Crawler Carl source contains weapons', category='Weapons',
             facets={'source': 'dungeon-crawler-carl-drafts'}, contains='dungeon-crawler-carl-drafts:grull-war-gauntlet'),
        case('Dungeon Crawler Carl source contains armor', category='Armor',
             facets={'source': 'dungeon-crawler-carl-drafts'}, contains='dungeon-crawler-carl-drafts:right-back-atcha-shield'),
        case('Dungeon Crawler Carl magic armor filters', category='Armor',
             facets={'source': 'dungeon-crawler-carl-drafts', 'enchantment': 'magic'},
             contains='dungeon-crawler-carl-drafts:trollskin-shirt'),
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
            deadline = time.monotonic() + 5
            while True:
                try:
                    if dev.eval("typeof byId === 'function' && typeof compactInspection !== 'undefined'"):
                        break
                except AssertionError as error:
                    if 'Execution context was destroyed' not in str(error):
                        raise
                if time.monotonic() >= deadline:
                    raise AssertionError('Armory guide script did not load')
                time.sleep(0.05)
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
                        ["dmg-1e-reference:5003ee3a0bd2f04d", ["Armor class by charges", "never regains", "up to 8 hours", "20 with 1–5 charges", "19 with 0 charges"]],
                        ["dmg-2e-reference:e030cf575bdcef9b", ["Cursed armor class14, 15, or 16", "natural 20"]],
                        ["dmg-2e-reference:62ade0786a04042d", ["Cursed shield bonus+0", "within 10 feet"]],
                        ["dmg-2e-reference:2423313ed73a2e69", ["+5 AC total", "roll a d10"]],
                        ["dmg-2e-reference:de359f74f62a0dee", ["14 + Dex modifier (max +2)", "treated as trained", "Published 2024 counterpart"]],
                        ["dmg-2e-reference:9f0e259e0ad010e7", ["2d12 charges", "DC 15 Wisdom", "30-foot Emanation"]],
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
                'Dungeon Crawler Carl cards show playable stats, prices and sources': '''(async () => {
                    const cases = [
                        ["grull-war-gauntlet", ["1d6", "Bludgeoning", "DC 14 Strength", "3 charges"]],
                        ["right-back-atcha-shield", ["+2 AC", "Reaction", "3d8 Force"]],
                        ["trollskin-shirt", ["AC 12", "Medium Armor", "2d6"]],
                        ["prism-industries-goggles", ["three force darts", "1d4 + 1 Force"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dungeon-crawler-carl-drafts:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !["Base cost", "Base buy", "Base sell"].every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href^="https://"]')
                            || !inspection.textContent.includes("Original conversion draft")) return false;
                    }
                    return true;
                })()''',
                'Kahn branding is visible in the app': '''(() => {
                    const title = "Kahn’s Complete Guide to Arms and Equipment";
                    const header = document.querySelector(".masthead");
                    return document.title === title && header.querySelector("h1").textContent === title
                        && header.scrollWidth <= header.clientWidth;
                })()''',
                'Custom magic items save, reopen, edit and delete through the app': '''(() => {
                    const name = "QA Lantern " + Date.now();
                    const click = id => byId(id).click();
                    const set = (id, value) => { byId(id).value = value; };
                    let id;
                    try {
                        click("open-custom-items");
                        click("custom-item-new");
                        set("custom-item-name", name);
                        set("custom-item-type", "weapon");
                        byId("custom-item-type").dispatchEvent(new Event("change"));
                        if (byId("custom-item-weapon-fields").hidden) return false;
                        set("custom-item-rarity", "rare");
                        set("custom-item-attunement", "Required");
                        set("custom-item-damage", "1d8 Radiant");
                        set("custom-item-range", "5 feet");
                        set("custom-item-rules", "On a hit, create a light.");
                        set("custom-item-notes", "Test notes.");
                        set("custom-item-price", "37.25");
                        click("custom-item-save");
                        const item = JSON.parse(Armory.customMagicItems()).find(row => row.name === name);
                        if (!item) return false;
                        id = item.id;
                        if (byId("custom-item-status").textContent !== "Item saved."
                            || !byId("custom-item-details").textContent.includes("37.25 gp")) return false;
                        click("close-custom-items");
                        click("open-custom-items");
                        byId("custom-items-list").querySelector('[data-custom-item-id="' + id + '"]').click();
                        if (!byId("custom-item-details").textContent.includes("Test notes.")) return false;
                        click("custom-item-edit");
                        set("custom-item-name", name + " Revised");
                        set("custom-item-type", "shield");
                        byId("custom-item-type").dispatchEvent(new Event("change"));
                        if (!byId("custom-item-weapon-fields").hidden || byId("custom-item-armor-fields").hidden) return false;
                        set("custom-item-ac", "+3 AC");
                        click("custom-item-save");
                        if (!byId("custom-item-details").textContent.includes("+3 AC")
                            || byId("custom-item-details").textContent.includes("1d8 Radiant")) return false;
                        click("custom-item-delete");
                        if (!JSON.parse(Armory.customMagicItems()).some(row => row.id === id)) return false;
                        click("custom-item-confirm-delete");
                        return byId("custom-item-status").textContent === "Item deleted."
                            && !JSON.parse(Armory.customMagicItems()).some(row => row.id === id);
                    } finally {
                        if (id) Armory.deleteCustomMagicItem(id);
                        if (!byId("custom-items").hidden) click("close-custom-items");
                    }
                })()''',
                'Customize copies playable catalog fields and saves edits independently': '''(async () => {
                    const lance = "open5e-vom:vom_breaker-lance";
                    const shield = "open5e-srd-2024:srd-2024_shield";
                    const before = Armory.item(lance);
                    const count = JSON.parse(Armory.customMagicItems()).length;
                    const name = "QA Customized Lance " + Date.now();
                    const field = name => byId("custom-item-" + name);
                    const customize = async id => {
                        inspect(id, grid.firstElementChild);
                        const action = Array.from(inspection.querySelectorAll("button"))
                            .find(button => button.textContent === "Customize");
                        action.click();
                        await Promise.all([itemDetails, bg3WeaponRules]);
                        return !byId("custom-items").hidden && !field("form").hidden;
                    };
                    let saved;
                    try {
                        if (!await customize(shield) || field("type").value !== "shield"
                            || !field("ac").value.includes("+2")) return false;
                        field("cancel").click();
                        if (JSON.parse(Armory.customMagicItems()).length !== count) return false;
                        byId("close-custom-items").click();
                        if (!await customize(lance) || field("name").value !== "Breaker Lance"
                            || field("type").value !== "weapon" || field("rarity").value !== "rare"
                            || !field("damage").value.includes("1d10 Piercing")
                            || !field("range").value.includes("10 feet") || !field("properties").value.includes("Topple")
                            || !field("rules").value.includes("3 charges")) return false;
                        field("name").value = name;
                        field("damage").value = "2d10 Piercing";
                        field("save").click();
                        saved = JSON.parse(Armory.customMagicItems()).find(item => item.name === name);
                        return saved && saved.id !== lance && saved.damage === "2d10 Piercing"
                            && saved.rules.includes("Breaker Lance") && Armory.item(lance) === before;
                    } finally {
                        if (saved) Armory.deleteCustomMagicItem(saved.id);
                        if (!byId("custom-items").hidden) byId("close-custom-items").click();
                        dismissInspection(false);
                    }
                })()''',
                'Mystara unique weapons show hazards, malfunction, and curses': '''(async () => {
                    for (const [id, terms] of [
                        ["643a32f128416154", ["30-foot-radius Cylinder", "6d6 Fire", "one year"]],
                        ["7de600da367b4ab1", ["Malfunction table", "Random discharge", "3d6 Thunder"]],
                        ["54ea1104b4525d1f", ["Antimagic quarrel", "DC 17 Constitution", "Comprehend Languages"]],
                        ["1b6c5ec577dd3ebe", ["Shadow servant", "one Shadow at a time", "Vulnerability to Radiant"]],
                        ["4ab6737d694fb516", ["3d8 Necrotic", "reduce its Hit Point maximum", "undead exorcism"]],
                        ["7dee634f7c0d00cc", ["Verbal spell components", "hostile Giant Spider", "seven-day count"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara unique weapons show charges, stasis, and range riders': '''(async () => {
                    for (const [id, terms] of [
                        ["dc367942057bea5e", ["extra 2d8 Piercing", "reduces the bow’s enhancement", "returns to +3"]],
                        ["6727ece52b93d20f", ["10,000 gp", "wounds do not stack", "30-foot-radius Sphere"]],
                        ["c9bb5b6dd4cd0971", ["Paralyzed", "Full-moon seed", "DC 17 Strength"]],
                        ["a80100e794be3c80", ["4 charges", "midnight", "Phantasmal Force", "spell slots"]],
                        ["3cd1a7b87f14e9d2", ["Antitoxin", "Gold Dragon", "7 days"]],
                        ["c0c392b31eb4fc49", ["DC 17 Charisma", "home plane", "Concentration"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara Treasures of Sind and unique weapons show their linked powers': '''(async () => {
                    for (const [id, terms] of [
                        ["2898c2823ac08f1e", ["within 30 feet", "maximum of +3 total", "Paralyzed", "secret passage"]],
                        ["7fbf7ab893d2342a", ["move from attack and damage to AC", "Verbal spell components"]],
                        ["5a6ca62b0c44ef1b", ["See Invisibility", "double up to five", "spellcaster"]],
                        ["9b15c60abfc81427", ["Levitate", "3d10 Slashing"]],
                        ["eac188cc4baf0e32", ["Construct", "Earthquake", "share one use"]],
                        ["0a89f808e4609f9f", ["Young Red Dragon", "8d6 Fire"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara weapon variants show distinct reload, ammunition, and grip rules': '''(async () => {
                    for (const [id, terms] of [
                        ["9af1fe16a5a60878", ["90/270 feet", "two Utilize actions", "nonmagical Medium or Heavy armor"]],
                        ["d680dc1698442577", ["50/140 feet", "dedicated atlatl dart", "1d6 + 1"]],
                        ["4abcca0fee5aaff3", ["20/60 feet", "Nick", "mundane dagger"]],
                        ["eaaa36de8424c615", ["1d8", "Strength 16", "Sap"]],
                        ["7414df7d146ef77b", ["1d10", "Piercing", "Topple"]],
                        ["e00488f70c7bcad0", ["50/150 feet", "sling bullet", "cannot fire arrows"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara siege engines show crew actions, minimum range, and ammunition links': '''(async () => {
                    for (const [id, terms] of [
                        ["949e0e5645c4a10b", ["2d10 Piercing", "80/320 feet", "Scorpio Bolt"]],
                        ["e5a8c2469d03473d", ["4d10 Piercing", "110/470 feet", "Springal Bolt"]],
                        ["6fbec7152a651e4a", ["5d10 Bludgeoning", "closer than 175 feet", "2 Utilize actions"]],
                        ["09d921833d5ba27a", ["6d10 Bludgeoning", "four additional crew", "spend their Reactions"]],
                        ["cbdec1181e82f8a0", ["8d10 Bludgeoning", "300/1,200 feet", "View Normal Trebuchet Shot"]],
                        ["39ebd1a27ac70e77", ["Fire instead of Bludgeoning", "automatic splash"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    inspect("mystara-fan-names-reference:cbdec1181e82f8a0", grid.firstElementChild);
                    await itemDetails;
                    const link = [...inspection.querySelectorAll("button")]
                        .find(button => button.textContent === "View Normal Trebuchet Shot");
                    if (!link) throw new Error("Trebuchet ammunition link missing");
                    link.click();
                    await itemDetails;
                    if (!inspection.textContent.includes("6d10 from Traction Trebuchet")) {
                        throw new Error("Trebuchet ammunition did not open");
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara launchers and thrown weapons show ammo, range, and control rules': '''(async () => {
                    for (const [id, terms] of [
                        ["fa2665b9013c078e", ["60/120 feet", "expends one Javelin", "Slow mastery"]],
                        ["b68469f06708a8d1", ["10/30 feet", "Speed becomes 0", "5 Slashing damage"]],
                        ["6ba83af5224e6597", ["40/160 feet", "misses outdoors", "DC 10 Dexterity"]],
                        ["92443a32b33d7036", ["80/200 feet", "stone or lead bullet", "Crossbow bolts are incompatible"]],
                        ["f42cefbb6b7fa991", ["25/100 feet", "spearhead or the blowgun", "Sap in melee or Vex at range"]],
                        ["b16543f5215b2d18", ["30 feet from you", "remove the head", "Strength save"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara polearms show reviewed attacks and distinct legacy conversions': '''(async () => {
                    for (const [id, terms] of [
                        ["c6df5079d8c48f5a", ["1d10 Slashing", "10 feet melee", "Ready action", "Hook or disarm"]],
                        ["3faa02cee5307086", ["1d10 Piercing", "Topple", "Ready action"]],
                        ["2af052841ed88951", ["1d6 Piercing", "Push", "Spontoon"]],
                        ["1da98ab1459ee023", ["1d8 Bludgeoning", "blunt, double-ended head", "PDF p. 3"]],
                        ["b93711e98661a11f", ["1d10 Slashing", "Graze", "legacy flat +2 damage"]],
                    ]) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Mystara lamellar and partial armor show playable Gazetteer conversions': '''(async () => {
                    for (const [id, terms] of [
                        ["gazetteer-equipment-reference:84c7f61c8e7a856c",
                            ["14 + Dex modifier (max +2)", "descending AC 4", "Starting Equipment Table"]],
                        ["gazetteer-publisher-preview-reference:07c3838050aebc33",
                            ["coverage bonus", "divide by 10", "170.75 gp", "22.25 lb", "printed p. 44", "+2 AC separately"]],
                    ]) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault weapon cards show curse, swallowing, shove, and ritual rules': '''(async () => {
                    for (const [id, terms] of [
                        ["bludgeon-of-nightmares", ["Morningstar variant", "Intelligence 5", "Exhaustion", "Remove Curse"]],
                        ["consuming-rod", ["8 charges", "DC 15 Dexterity", "Total Cover", "falls Prone"]],
                        ["labrys-of-the-raging-bull-battleaxe", ["Topple", "two sizes larger", "Unarmed Strike"]],
                        ["labrys-of-the-raging-bull-greataxe", ["Cleave", "two sizes larger", "Disadvantage"]],
                        ["sacrificial-knife", ["Spellcasting Focus", "Nick"]],
                        ["ceremonial-sacrificial-knife", ["Short Rest", "level 1 spell slot", "level 2 spell slot"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault armor uses item-specific Dexterity caps, charges, and forms': '''(async () => {
                    for (const [id, terms] of [
                        ["agile-plate", ["18 + Dex modifier (max +1)", "negative modifier"]],
                        ["agile-breastplate", ["14 + Dex modifier (max +3)"]],
                        ["molten-hellfire-splint", ["1d4 Fire", "3 charges", "Strength 15"]],
                        ["hide-armor-of-the-leaf", ["Ranger", "2d8 Slashing", "without this suit"]],
                        ["brawn-armor", ["initial save", "Unarmed Strike", "AttunementRequired"]],
                        ["serpents-scales", ["Giant Venomous Snake", "11 Temporary Hit Points", "AttunementRequired"]],
                        ["longbow-of-accuracy", ["300/600 feet", "Long range is unchanged"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault Bloodfuel, Bloodthirsty, and Warding keep their distinct triggers': '''(async () => {
                    for (const [id, terms] of [
                        ["bloodfuel-crossbow-hand", ["30/120 feet", "Hit Point Dice", "extra Necrotic damage", "Vex"]],
                        ["bloodfuel-dagger", ["before rolling the attack", "Nick"]],
                        ["bloodthirsty-greatsword", ["1 minute", "miss against it", "DC 15 Wisdom", "Graze"]],
                        ["plate-of-warding-3", ["Armor class18", "+3 to the listed AC only", "Strength 15"]],
                        ["padded-armor-of-warding-1", ["11 + Dex modifier", "+1 to the listed AC only", "Ward types"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault of Magic restores four omitted item families and their variants': '''(async () => {
                    for (const [id, terms] of [
                        ["whip-of-the-blue-wyrm-plus-1", ["Uncommon", "1d6 Lightning"]],
                        ["whip-of-the-blue-wyrm-plus-2", ["Rare", "1d4 Slashing"]],
                        ["whip-of-the-blue-wyrm-plus-3", ["Very Rare", "modifier + 3"]],
                        ["whirlwind-bolas", ["5/15 feet", "DC 15 Strength", "No damage from the attack"]],
                        ["witchs-circle", ["1d6 Slashing", "20/60 feet", "Moonbeam at level 6"]],
                        ["witch-hunters-half-plate-armor", ["16 + Dex modifier", "against spells", "until dawn"]],
                        ["witch-hunters-plate-armor", ["Armor class19", "Strength 15"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault of Magic shows aquatic armor, shield penalties, and paired ammunition': '''(async () => {
                    for (const [id, terms] of [
                        ["undine-plate", ["Swim Speed of 40 feet", "Fire Resistance", "AttunementRequired"]],
                        ["verses-of-vengeance", ["Armor class bonus+3", "Cleric or Paladin", "1d4 Radiant"]],
                        ["void-touched-buckler", ["DC 17 Wisdom", "gains Advantage"]],
                        ["white-ape-hide", ["14 + Dex modifier", "Arcane Wasting", "Lesser Restoration"]],
                        ["wolf-brush", ["1d6 Piercing", "Halberd variant", "Wall of Thorns"]],
                        ["web-arrows", ["20-foot Cube", "DC 13 Dexterity", "2d4 Fire"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault of Magic shows dragon rituals, shield colors, cursed blades, and trident rules': '''(async () => {
                    for (const [id, terms] of [
                        ["greatsword-of-fallen-saints", ["Graze", "Gentle Repose"]],
                        ["longsword-of-volsung", ["Fighter or Paladin", "Dragon Heart Ritual", "1d4 + 1 hours"]],
                        ["tarian-graddfeydd-ddraig", ["Armor class bonus+4", "30-foot Cone", "6 Shadow"]],
                        ["thirsting-scalpel", ["1d4 Slashing", "DC 11 Wisdom", "Banishment"]],
                        ["troll-skin-hide", ["13 + Dex modifier", "become Stable", "AttunementRequired"]],
                        ["trident-of-the-yearning-tide", ["Topple", "save DC 17", "water-breathing beasts"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault of Magic restores shield reactions, armor requirements, and the planted standard': '''(async () => {
                    for (const [id, terms] of [
                        ["spearbiter", ["Armor class bonus+2", "Reaction", "recharges at dawn", "AttunementRequired"]],
                        ["adamantine-spearbiter", ["Roll with Advantage", "Reaction available"]],
                        ["spectral-blade", ["Rare", "1d10 Force damage", "Difficult Terrain"]],
                        ["standard-of-divinity-halberd", ["Cleric or Paladin", "Cleave"]],
                        ["swarmfoe-hide", ["13 + Dex modifier", "1d4 + Strength modifier", "AttunementRequired"]],
                        ["sweet-nature", ["24 hours", "within 30 feet", "Advantage on saving throws"]]
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await Promise.all([itemDetails, bg3WeaponRules]);
                        const missing = terms.filter(term => !inspection.textContent.includes(term));
                        if (missing.length) throw new Error(id + " missing " + missing.join(", "));
                    }
                    dismissInspection(false);
                    return true;
                })()''',
                'Vault of Magic restores curses, ammunition, and smoke effects': '''(async () => {
                    for (const [id, terms] of [
                        ["spear-of-the-stilled-heart", ["at dusk", "3d6 Necrotic", "DC 12 Constitution", "Remove Curse"]],
                        ["spear-of-the-north", ["pair of skis", "40 feet", "1d6 Cold"]],
                        ["smoking-plate-of-heithmir", ["Armor class21", "30-foot Cone", "DC 17 Constitution", "AttunementRequired"]],
                        ["slimeblade-rapier", ["Vex", "Oozes", "2d4 Poison", "1 hour"]],
                        ["slipshod-hammer", ["Smith’s Tools", "cumulative −2", "Uncommon"]],
                        ["sickle-of-thorns", ["5 feet melee", "60 feet away", "1 inch"]],
                        ["siege-arrow", ["80/320 feet", "double the hit’s damage"]],
                        ["signaling-ammunition", ["1 mile", "DC 13 Dexterity", "Invisible condition"]],
                        ["sling-stone-of-screeching", ["5-foot-wide Line", "2d8 Thunder", "3d8 Thunder"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return JSON.parse(Armory.item("open5e-vom:vom_slimeblade-rapier")).rarity === "rare";
                })()''',
                'Vault of Magic restores wind strike, shark form, and shield triggers': '''(async () => {
                    for (const [id, terms] of [
                        ["scimitar-of-the-desert-winds", ["150°F", "DC 15 Strength", "15 feet away"]],
                        ["scourge-of-devotion", ["1d8 Slashing", "2d8", "Concentration"]],
                        ["sea-witchs-blade", ["Very Rare", "DC 15 Wisdom", "each prior attempt since dawn"]],
                        ["searing-whip", ["5-foot-wide Line", "30 feet", "Daylight"]],
                        ["sharkskin-vest", ["12 + Dex modifier", "Reef Shark", "Temporary Hit Points"]],
                        ["shepherds-flail", ["Crook of the Flock", "3d6 Bludgeoning", "24 hours"]],
                        ["shield-of-gnawing", ["Armor class bonus+3", "Barbarian", "DC 8 +"]],
                        ["shield-of-missile-reversal", ["Armor class bonus+3", "Reaction", "original attacker"]],
                        ["shield-of-the-fallen", ["Armor class bonus+2", "Floating Disk", "1d12 hours"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    const scourge = JSON.parse(Armory.item("open5e-vom:vom_scourge-of-devotion"));
                    return scourge.rarity === "rare" && scourge.tags.includes("damage:slashing");
                })()''',
                'Vault of Magic shows retaliation, corrosion and water-specific attacks': '''(async () => {
                    for (const [id, terms] of [
                        ["retribution-armor", ["15 + Dex modifier", "Retributive Resurrection", "1 Hit Point", "1,000 feet", "True Resurrection"]],
                        ["rust-monster-shell", ["15 + Dex modifier", "cumulative −1", "At −5", "AttunementRequired"]],
                        ["sand-suit", ["12 + Dex modifier", "nonmagical, unworked earth", "Fiend", "1d12"]],
                        ["ravagers-axe", ["Critical Hit", "natural 20", "1d10 Cold", "1d10 Necrotic"]],
                        ["reef-splitter", ["4d6 Fire", "underwater", "2d6 Fire"]],
                        ["rowdys-club", ["Rowdy’s Ring", "DC 13 Wisdom", "three times per dawn"]],
                        ["ruby-crusher", ["DC 17 Constitution", "30 feet away", "per full 10 feet"]],
                        ["sand-arrow", ["80/320 feet", "DC 11 Constitution", "metal armor"]],
                        ["sanguine-lance", ["unless mounted", "1d6 Necrotic", "rounded down"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic separates quiet armor, weapon riders, and recovery saves': '''(async () => {
                    for (const [id, terms] of [
                        ["muffled-plate", ["Armor class18", "Stealth disadvantageNo", "15. Below"]],
                        ["muffled-half-plate", ["15 + Dex modifier", "Stealth disadvantageNo"]],
                        ["pestilent-spear", ["DC 13 Constitution", "Daily at dawn", "DC 11 Constitution", "1d4 days"]],
                        ["mutineers-blade", ["modifier + 2", "nearest ally", "natural 20"]],
                        ["phidjetz-spinner", ["Monk", "30 feet for the spinning attack", "1d6 Lightning and Paralyzed"]],
                        ["pick-of-ice-breaking", ["Damage Threshold", "2d8 Piercing"]],
                        ["pistol-of-the-umbral-court", ["30/120 feet", "DC 15 Strength", "1d6 Bludgeoning"]],
                        ["poison-strand", ["DC 17 Dexterity", "DC 17 Strength", "1 minute of total restraint"]],
                        ["primordial-scale", ["Darkvision to 60 feet", "AttunementRequired", "agents of gods"]],
                        ["rain-of-chaos", ["150/600 feet", "8 Thunder"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || (id.startsWith("muffled") && inspection.textContent.includes("Stealth disadvantageYes"))) {
                            throw new Error("Missing or conflicting fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic restores alternate attack modes and armor limits': '''(async () => {
                    for (const [id, terms] of [
                        ["manticores-tail", ["5 feet melee", "100/200 feet", "ten regrow at dawn", "Bludgeoning"]],
                        ["mail-of-the-sword-master", ["15 + Dex modifier (max +4)", "+2 to damage rolls", "AttunementRequired"]],
                        ["living-juggernaut", ["Armor class19", "when you Dash", "DC 15 Dexterity", "Opportunity Attack"]],
                        ["meteoric-plate", ["Armor class18", "halve your falling damage", "20-foot-radius Sphere"]],
                        ["mordant-halberd", ["Cleave", "2d6 Acid damage", "Bonus Action"]],
                        ["moonsteel-rapier", ["DC 13 Charisma", "true form", "1d6 Radiant"]],
                        ["mountaineers-heavy-crossbow", ["100/400 feet", "1,000 lb", "20 Hit Points", "24 hours"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || (id === "mail-of-the-sword-master" && inspection.textContent.includes("max +2"))) {
                            throw new Error("Missing or conflicting fields on " + id);
                        }
                    }
                    const manticore = JSON.parse(Armory.item("open5e-vom:vom_manticores-tail"));
                    return manticore.mechanics.weapon.name === "Morningstar" && !manticore.tags.includes("property:reach");
                })()''',
                'Vault of Magic distinguishes conditional barding and embedded weapon damage': '''(async () => {
                    for (const [id, terms] of [
                        ["ghost-barding-plate", ["Armor class18", "1 lb", "only against attacks made by Undead", "A Beast"]],
                        ["ghost-barding-half-plate", ["15 + Dex modifier (max +2)", "Stealth disadvantageNo"]],
                        ["impaling-pike", ["1d10 Piercing", "10 feet melee", "DC 13 Strength", "wall or solid object"]],
                        ["impaling-warpick", ["1d10 if the embedding hit used two hands", "Sap"]],
                        ["knockabout-billet", ["Once per hour", "DC 8 +", "normal damage"]],
                        ["kyshaarths-fang", ["2d6 Necrotic", "Dim Light or Darkness", "rounded down"]],
                        ["leaf-bladed-rapier", ["1d8 Piercing damage", "Barkskin", "AC to 17"]],
                        ["larkmail", ["Armor class17", "DC 15 Charisma", "AttunementRequired"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || (id.startsWith("ghost-barding") && inspection.textContent.includes("Armor statistics"))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic restores Iceblink powers and shield reactions': '''(async () => {
                    for (const [id, terms] of [
                        ["iceblink-greatsword", ["2d6 Slashing", "Freeze Water", "60-foot radius", "Snowblind", "DC 15 Constitution"]],
                        ["grasping-shield", ["Armor class bonus+3", "escape DC 13", "no AC bonus"]],
                        ["grim-escutcheon", ["DC 13", "30-foot Cone", "dusk"]],
                        ["grave-ward-plate", ["Armor class18", "1 Hit Point", "without Concentration", "AttunementRequired"]],
                        ["hammer-of-throwing", ["20/60 feet", "end of your turn", "Nick"]],
                        ["hexen-blade", ["5 charges", "Hypnotic Pattern (3)", "Adamantine"]],
                        ["hidden-armament", ["tattoo on your palm", "2024 Dagger example"]],
                        ["impact-club", ["DC 9 +", "up to 10 feet", "Disadvantage"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return !JSON.parse(Armory.item("open5e-vom:vom_hidden-armament")).mechanics.weapon;
                })()''',
                'Vault of Magic preserves Fountmail, self-loading crossbow and fire effects': '''(async () => {
                    for (const [id, terms] of [
                        ["fellforged-armor", ["Armor class19", "Speak with Dead", "cannot remove the armor"]],
                        ["fountmail", ["Armor class19", "Chain Mail (+3)", "13. Below", "55 lb", "Necrotic Resistance"]],
                        ["forgefire-warhammer", ["Push", "1d6 Fire damage", "1d4 Fire damage"]],
                        ["golden-bolt", ["1d10 Piercing", "100/400 feet", "no Loading property"]],
                        ["goblin-shield", ["Armor class bonus+2", "Shield training", "2d4 Piercing"]],
                        ["gorgon-scale", ["DC 15 Constitution", "Greater Restoration", "Petrified"]],
                        ["gale-javelin", ["30/120 feet", "DC 13 Strength", "15 feet away"]],
                        ["gnawing-spear", ["2d6 Piercing", "Grappled", "DC 15 Strength"]],
                        ["fog-stone", ["30/120 feet", "20-foot-radius", "10 minutes"]],
                        ["flash-bullet", ["DC 11 Constitution", "Sunlight Sensitivity"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    const tags = JSON.parse(Armory.item("open5e-vom:vom_golden-bolt")).tags;
                    return !tags.includes("property:loading") && !tags.includes("property:ammunition")
                        && tags.includes("property:heavy");
                })()''',
                'Vault of Magic shows net escape, lineage and armor aura rules': '''(async () => {
                    for (const [id, terms] of [
                        ["dimensional-net", ["15 feet", "DC 9 +", "DC 30 Strength", "cannot teleport", "30 Hit Points"]],
                        ["dirgeblade", ["Bardic Inspiration", "DC 15 Wisdom", "2d6 hours"]],
                        ["dragonstooth-blade", ["1d8 Slashing", "Greatsword form", "2d6 Slashing", "6 Necrotic"]],
                        ["entrenching-mattock", ["War Pick", "30 feet long", "Half Cover"]],
                        ["exsanguinating-blade", ["maximum of 1", "2d8 Hit Points", "2d8 Necrotic"]],
                        ["encouraging-padded-armor", ["12 + Dex modifier", "Aura of Courage", "10 feet"]],
                        ["encouraging-plate", ["Armor class19", "reduce Speed by 10 feet", "AttunementRequired"]],
                        ["enraging-ammunition", ["DC 13 Wisdom", "most direct safe route"]],
                        ["ensnaring-ammunition", ["Half the attack", "DC 13 Strength", "5 Hit Points"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic distinguishes transformed weapons, spell focus and special arrows': '''(async () => {
                    for (const [id, terms] of [
                        ["clockwork-mace-of-divinity", ["1d6 Bludgeoning", "1d8 Piercing", "20/60 feet", "1d6 Radiant"]],
                        ["commanders-plate", ["Armor class18", "300 feet", "Long Rest"]],
                        ["crusaders-shield", ["Armor class bonus+2", "Cleric, Druid, or Paladin", "DC 10 Intelligence"]],
                        ["constant-dagger", ["natural 20", "Immunity becomes Resistance", "three times"]],
                        ["dagger-of-the-barbed-devil", ["DC 15 Dexterity", "DC 15 Constitution", "1d4 Piercing"]],
                        ["dawn-shard-scimitar", ["Nick", "2d6", "20-foot radius"]],
                        ["crimson-starfall-arrow", ["Hit Point Dice", "10 feet", "Necrotic damage"]],
                        ["deadfall-arrow", ["80/320 feet", "3d6 Bludgeoning", "DC 15 Strength"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic retains axe powers and Chillblain curses': '''(async () => {
                    for (const [id, terms] of [
                        ["candied-axe", ["save DC 15", "immune to Poison", "120 feet", "After 7 days", "Remove Curse"]],
                        ["chieftains-axe", ["Reaction", "Silvered", "Hostile"]],
                        ["chainbreaker-greatsword", ["2d6 Slashing", "Graze", "metal object currently restraining"]],
                        ["cephalopod-breastplate", ["15 + Dex modifier", "20-foot-radius", "significant current"]],
                        ["chillblain-chain-shirt", ["14 + Dex modifier", "DC 15 Constitution", "Fire Vulnerability"]],
                        ["chillblain-plate", ["Armor class19", "Critical Hit", "shatters it"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic distinguishes Buzzing weapons, barriers and marked arrows': '''(async () => {
                    for (const [id, terms] of [
                        ["buzzing-greataxe", ["1d12 Slashing", "Cleave", "2d6 Thunder damage"]],
                        ["buzzing-handaxe", ["20/60 feet", "Vex", "100 feet"]],
                        ["breaker-lance", ["1d10 Piercing", "unless mounted", "DC 10 + the spell"]],
                        ["bone-whip", ["DC 17 Constitution", "5 Temporary Hit Points"]],
                        ["bonebreaker-mace", ["Vulnerable", "1d6 Radiant damage"]],
                        ["brazen-bulwark", ["Armor class bonus+3", "attunement"]],
                        ["bullseye-arrow", ["None on the initial hit", "80/320 feet", "19 or 20"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) {
                            throw new Error("Missing fields on " + id);
                        }
                    }
                    return true;
                })()''',
                'Vault of Magic preserves Bloodprice reactions and weapon triggers': '''(async () => {
                    for (const [id, terms] of [
                        ["bloodprice-padded", ["11 + Dex modifier", "+1 to +10", "5 Hit Points"]],
                        ["bloodprice-plate", ["Armor class18", "reduce Speed by 10 feet"]],
                        ["blood-soaked-hide", ["13 + Dex modifier", "DC 15 Constitution", "3d6 Hit Points"]],
                        ["bloodbow", ["150/600 feet", "DC 15 Wisdom", "1d3"]],
                        ["blade-of-the-temple-guardian", ["Heightened Focus", "1 expended Focus Point"]],
                        ["blade-of-the-dervish", ["Each full 10 feet", "+3 and 3d6", "another 2d6 Slashing"]],
                    ]) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Vault of Magic cards use the published bases and distinct powers': '''(async () => {
                    const cases = [
                        ["anointing-mace", ["2d6 Bludgeoning", "Topple", "whether it hits or misses"]],
                        ["asps-kiss", ["1d6 Piercing", "Spike attack", "DC 17 Constitution"]],
                        ["anchor-of-striking", ["1d8 Piercing", "50 feet", "DC 15 Strength or Dexterity"]],
                        ["blackguards-handaxe", ["Axe of the Ancients", "Thaumaturgy"]],
                        ["blackguards-shortsword", ["Vex", "none of its allies"]],
                        ["animated-chain-mail", ["your AC drops to 15", "10 feet", "DC 8 + your Strength"]],
                        ["armor-of-cushioning", ["11 + Dex modifier", "twice your level"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("open5e-vom:vom_" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara named weapons show their distinct attack and curse rules': '''(async () => {
                    const cases = [
                        ["11060c62afa7bba1", ["modifier − 2", "DC 16 Charisma", "2d20 days"]],
                        ["a7357dd4d93de2ac", ["1d6 Slashing", "immediate physical hazard"]],
                        ["347d7e378f221449", ["threshold that starts at 1", "doubled if thrown"]],
                        ["b5eefc05864d274a", ["2d6 Piercing damage", "thrown attack misses", "Zargon’s Suit Plate"]],
                        ["63fcb17bbb121f22", ["Bonus Action", "Scimitar of Speed"]],
                        ["5871b95d01aa3d6a", ["150/600 feet", "Against a gnoll"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Mystara fitted armor and accessories show their conditions': '''(async () => {
                    const cases = [
                        ["e8e59de85438a4d3", ["Armor class16", "110 lb", "600 gp"]],
                        ["42eb6c621aea3f60", ["AC 18", "24 hours", "11 + Dexterity modifier"]],
                        ["164e1066311bbc90", ["11 + Dex modifier", "mustelids", "+1 to that check"]],
                        ["620634f4e71c946a", ["+2 to AC and saving throws", "Ring or Cloak of Protection"]],
                        ["cd6737f0971c746e", ["+1 AC", "Studded Leather Armor"]],
                        ["cef13e8b5f42db06", ["Armor class18", "+2 to saving throws", "Fire damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara powered armor displays separate charge and protection modes': '''(async () => {
                    const cases = [
                        ["e39c83175ba9bbe5", ["Armor class16", "18 lb", "including firearms"]],
                        ["eec9086b6ea6971f", ["Armor class18", "32.5 lb"]],
                        ["cd731ae7e0420a14", ["24 hours", "11 + Dexterity modifier", "1 additional charge per hour"]],
                        ["eb2eeed3f8a7560d", ["AC 16", "seven days", "5 per charge"]],
                        ["83d1901e62478a5e", ["no AC bonus", "12 saved appearances", "1 charge for 1 minute"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara energy shields show distinct power and defense rules': '''(async () => {
                    const cases = [
                        ["1234f6e04adc22c7", ["Armor class bonus+2", "30 gp equivalent"]],
                        ["3dc513d3fbfc4ff7", ["1 charge", "1 hour", "projector arm free"]],
                        ["1df87f84a7708fbc", ["Required by an Octospider", "non-technological weapons"]],
                        ["038a02ad91d4a944", ["no AC bonus", "roll 4d6", "next dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara shield weapons trade AC for attacks and suit armor has limits': '''(async () => {
                    const cases = [
                        ["734a41738507c81c", ["Armor class bonus+2", "1d4 Piercing", "Light property", "AC bonus is suspended"]],
                        ["5e641272e171775a", ["1d4 + 1 Slashing", "natural 1", "Smith’s Tools"]],
                        ["58a5d5652c949bec", ["1d6 Slashing", "part of the Attack action"]],
                        ["cf20b1d571a58e39", ["hold the shield with both hands", "additional shield attack"]],
                        ["4c327a8ed72facfb", ["Armor class18", "reduce that damage by your Proficiency Bonus", "Speed is reduced by 10 feet"]],
                        ["886325bf46e94f01", ["14 + Dex modifier (max +2)", "Medium armor"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara relic armor shows set, charge, and unarmored rules': '''(async () => {
                    const cases = [
                        ["36239dd6321abd67", ["Armor class21", "Adamantart"]],
                        ["66cb001e2f200102", ["Wisdom (Survival)", "Speed becomes 0"]],
                        ["a98b34cf26f57884", ["Cold Resistance", "Dominate Beast"]],
                        ["d902941b2073d753", ["Armor class bonus+3", "40 feet straight", "Strength 15"]],
                        ["27c6247de31ff179", ["Dark absorption", "1d4 rounds", "DM-controlled Undead"]],
                        ["33d0de9244d90ce6", ["Swim Speed", "returning spear"]],
                        ["a6a5ba9e66ed8dad", ["matching helm", "AC 19", "Immunity to Radiant"]],
                        ["b982c4e680a34a68", ["14 + Dex modifier", "Arcane memories", "three times per dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara named suits show transformations, curses, and reactive armor': '''(async () => {
                    const cases = [
                        ["5975fca564494668", ["14 + Dex modifier", "Faceless hood", "Truesight"]],
                        ["379270195a6ca0b4", ["13 + Dex modifier", "2d12 hours", "one adaptation"]],
                        ["3c9ced9d5313943d", ["Armor class21", "emerald holds five charges", "level 1 spell"]],
                        ["890d98f62dfc20a7", ["8 + Dex modifier", "3d6 + 2 HP", "Clan Feadiel"]],
                        ["79f6d72b6ca1159c", ["17 + Dex modifier (max +2)", "Young Blue Dragon", "seven dawns"]],
                        ["b997e66a0271ce6a", ["silver Lion", "one year", "Remove Curse"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Mystara fan armor retains distinct wards, drawbacks, and AC': '''(async () => {
                    const cases = [
                        ["0dc6a22af269958e", ["Armor class bonus+5", "DC 17 Wisdom", "Once per new moon"]],
                        ["fccb909cde95bd38", ["200,000 gp", "roll 1d4", "random-encounter die"]],
                        ["50d31b7b990d80d6", ["two independent saves", "Zone of Truth"]],
                        ["79b1b547e5df71e2", ["Armor class18", "including an ally", "1d6 + 1 Hit Points"]],
                        ["875f1a4b7ad7d424", ["Armor class20", "Resistance to Necrotic", "Bright Light within 60 feet"]],
                        ["4eb4e221f8c114eb", ["Armor class21", "breathe underwater", "weaponize water"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("mystara-fan-names-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'GAZ13 staves and Firnafel’s bolts show activation and limits': '''(async () => {
                    const cases = [
                        ["70e65a05072c0b10", ["Dominate Beast (4 charges)", "Falanen"]],
                        ["ec0e000992956c3b", ["Dispel Magic", "1d4 rounds", "2d20 charges"]],
                        ["b898e726f24ac264", ["Fire Resistance", "Summon Elemental (fire only"]],
                        ["796af5c6071b7cf7", ["1d6 + 1 Hit Points", "once between dawns"]],
                        ["3027c54efba36159", ["DC 15 Strength", "20 Hit Points", "No class restriction"]],
                        ["5b6454c14c1cbf25", ["six bolts", "Add 3 to the attack roll", "nonmagical after it hits"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("gaz13-online-adaptation-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Shadow Elf weapons show named powers and modern attack profiles': '''(async () => {
                    const cases = [
                        ["28134d4d8c9af5f8", ["1d8 Slashing", "At level 11, add Magic Jar", "Illusion ward"]],
                        ["8784b39a7e2becfa", ["100-foot Line", "12d6 Lightning", "Blinded condition"]],
                        ["e6086ad25a84ae4b", ["25 Hit Points or fewer", "DC 16 Constitution", "gnoll"]],
                        ["4a3eca691ea4f84b", ["2d6 Slashing", "extra 14 Slashing", "Exhaustion"]],
                        ["0214e5642767ac14", ["80/320 feet", "100/400 feet"]],
                        ["5931ec582be5b594", ["1d8 Bludgeoning", "Zindar"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("gaz13-online-adaptation-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Shadow Elf armor preserves Garafaele’s shield powers and source context': '''(async () => {
                    const cases = [
                        ["96fc2dbf2becea08", ["Armor class17", "Maflarel; Zindar"]],
                        ["a9b88d9954fb92b7", ["Armor class19", "Tanadaleyo; Telemon"]],
                        ["8eb482f403643244", ["Armor class19", "legacy +5", "Garafaele"]],
                        ["a8063aed55ecc7f7", ["14 + Dex modifier", "Firnafel"]],
                        ["b63cba2265dfd8db", ["Armor class bonus+5", "cast Fly on yourself at will", "roll 1d10", "3d8 Necrotic", "Long Rest"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("gaz13-online-adaptation-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Karameikos named armor uses its source enhancement and published AC': '''(async () => {
                    const cases = [
                        ["633570fe6b27d9ae", ["Armor class19", "printed p. 45", "55 lb"]],
                        ["c4fd50d0c207a130", ["Armor class20", "black-enamelled", "Strength requirement15"]],
                        ["8892fffbb4ab25b8", ["Armor class bonus+4", "Shield training"]],
                        ["db1d03bdc5184881", ["13 + Dex modifier", "Light armor"]],
                        ["218a24f4bdb2b26b", ["+2 to AC", "wear no armor and use no Shield", "descending AC 2"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("gaz1-karameikos-local:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D 2e armor shows verified charge counts and conditional AC': '''(async () => {
                    const cases = [
                        ["5003ee3a0bd2f04d", ["21 with 6–20 charges", "20 with 1–5 charges", "19 with 0 charges"]],
                        ["9f0e259e0ad010e7", ["2d12 charges", "1d4 + 1 rounds", "30-foot Emanation"]],
                        ["e030cf575bdcef9b", ["+3, +2, or +1 respectively", "broken suit provides no AC"]],
                        ["2423313ed73a2e69", ["+5 AC total", "On 1–2, negate the darts"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D 2e weapon forms show 2024 comparisons and exceptions': '''(async () => {
                    const cases = [
                        ["bf016630ca2480a2", ["1d10 Piercing", "Heavy, Reach, Two-Handed"]],
                        ["21011df4c0480cf7", ["80/320 feet", "Hand crossbow", "Heavy crossbow"]],
                        ["d93b9fbc38c2896c", ["Shortbow 1d6 Piercing", "modifier + 1"]],
                        ["8a77dbeb8b3cc1df", ["Strength rating to 13, 15, or 17", "Dexterity 13"]],
                        ["8aed65824ac012b0", ["1d4 Bludgeoning", "1 Hit Point"]],
                        ["45ff7a025f063d67", ["40 feet maximum", "automatically miss underwater"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D 2e named swords retain their distinctive rules': '''(async () => {
                    const cases = [
                        ["610bfbead9f30de4", ["Dancing range", "four more attack turns"]],
                        ["4f291977ed5d9c72", ["15 Necrotic damage", "regain Hit Points"]],
                        ["2610b2f0eb7a4bd0", ["14 Slashing damage", "1 level of Exhaustion"]],
                        ["b24a7315a54efc33", ["1 Necrotic damage per open wound", "Wish can also restore"]],
                        ["b507dafb230edb84", ["defense pool of 4", "held weapon"]],
                        ["690b4323e8b76f65", ["defense pool of 5", "held weapon"]],
                        ["0537659b1f48eb52", ["10 Radiant damage", "Dispel Magic"]],
                        ["0bbcfcfcc1eb2787", ["Astral or Ethereal", "+3 to hit and +4 to damage"]],
                        ["f5f4d19a393a9ebf", ["1d6 Piercing", "Advantage on Initiative"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D 2e staves show class gates, charges, and variant powers': '''(async () => {
                    const cases = [
                        ["a6b9d4b636ef424c", ["Only a Cleric can cast Speak with Plants", "only a mammal"]],
                        ["3ff0ffaa35076c4a", ["3d6 + 3 Hit Points", "twice between dawns"]],
                        ["6d0145af91b7734b", ["01–60 Python", "3d6 Poison"]],
                        ["07d526d9484a7bff", ["Only a Druid", "60/180 feet", "3d10 + 3"]],
                        ["749cd4586909c31f", ["Thunderclap (2 charges)", "both saves"]],
                        ["ac6c9d3b58abfb16", ["Age and Wither", "Ageless creatures"]],
                        ["587f6cb1b007440f", ["Animate Tree (4 charges)", "Barkskin", "Tree Shape"]],
                        ["835170a4e73f22fd", ["modifier + 4", "plus 3"]],
                        ["028a1524a53d4bc4", ["Great mace form", "Maul proficiency"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D 2e cursed weapons and tridents show triggers and remedies': '''(async () => {
                    const cases = [
                        ["4e377c4455cc3052", ["Dash toward the nearest one", "Remove Curse is cast on you"]],
                        ["aa290b3199d71e42", ["at least 1 damage", "Only Wish"]],
                        ["e0ebea512c48ab29", ["nearest such creature", "including an ally"]],
                        ["124740dbbcbe3db3", ["doubled if you threw it", "+2 or +3 variant"]],
                        ["d0abf009ae95029a", ["DC 15 Wisdom", "cannot make attacks", "1d4 + 16"]],
                        ["e1c7abdf4ab3ae28", ["240-foot hemisphere", "scan again", "1d6 + 18"]],
                        ["eb120e2d883e2270", ["fully submerged", "Water Breathing", "Wish ends the binding"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D slayer swords keep the target-specific rules': '''(async () => {
                    const cases = [
                        ["fa0baa196a077ad0", ["Roll 1d10", "3d6 Slashing instead of 1d6"]],
                        ["8907cfee6f377022", ["Black Dragons of any age", "3d6 Slashing"]],
                        ["b405cd23f3e669b2", ["Red Dragons of any age", "Drakes and wyverns do not qualify"]],
                        ["9c1e2f19d62d3f0e", ["Casting only through a magic item does not qualify"]],
                        ["0b1fe89e96af163a", ["currently transformed by a spell"]],
                        ["5f951a6839ca5999", ["active Regeneration trait", "Ring of Regeneration"]],
                        ["3e3ae57dab4d520a", ["+3 to attack and +4 to damage", "hydras"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D concealment, speed, and ranged variants show their specific rules': '''(async () => {
                    const cases = [
                        ["84001f0403e8996e", ["modifier + 5", "plus 3", "Bonus Action"]],
                        ["c1088795455a5ab9", ["ornamental buckle", "DC 15 Intelligence", "Roll 1d10"]],
                        ["e3414df00bf81bc8", ["20/60 feet thrown", "concealed release", "usually +1 or +2"]],
                        ["f7455ab938618946", ["1d6 Slashing", "usually +2 or +3"]],
                        ["ef118c1af6ae8609", ["60 feet in any direction", "hit or miss", "roll 2d4"]],
                        ["31ba46f9904b6a56", ["30/120 feet", "counts as +1", "+2 on attack and damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D throwing weapons and crossbows preserve distinct enchantments': '''(async () => {
                    const cases = [
                        ["d247d4f988f69957", ["Roll 1d20", "2d6 Slashing", "hits or misses"]],
                        ["c0a1e23077d7acf1", ["2d6 Slashing", "+5", "plus 3"]],
                        ["ccd1a997803b69b0", ["Roll 1d100", "2d4 Piercing", "Retrieve the dagger normally"]],
                        ["c4427703cb9e533c", ["plus 3", "no damage bonus", "no Disadvantage for distance"]],
                        ["cd91d030bb55dadc", ["200/800 feet", "10%"]],
                        ["c0eeba477af6f9c2", ["Ignore the Loading property", "Bonus Action"]],
                        ["ab37563d783fe63c", ["wooden or stone object", "Shortsword form uses 1d6"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'AD&D arrows distinguish slaying targets from exploration magic': '''(async () => {
                    const cases = [
                        ["1df79b6358449dde", ["6d10 Force", "DC 17 Constitution", "150/600 feet", "becomes nonmagical"]],
                        ["4da74b5edc5fa2cc", ["Thief subclass", "6d10 Force"]],
                        ["b1d4242f7f299690", ["native to the sea", "6d10 Force"]],
                        ["eda855574bac5128", ["Choose or roll d100", "6d10 Force"]],
                        ["9f8517036dbe3769", ["1,000-foot detection radius", "seven more queries", "next dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D siege engines and arquebus show their operating rules': '''(async () => {
                    const cases = [
                        ["535dc1def22a4aec", ["5d10 Bludgeoning", "200/800 feet", "two Utilize actions to load"]],
                        ["7f783c42164d6267", ["3d10 Bludgeoning", "+8 melee attack", "Total Cover"]],
                        ["4615e9a1ab567a11", ["3d10 Bludgeoning", "minimum 40 feet", "one Utilize action to load"]],
                        ["c1cb26fc97262afd", ["3d10 Piercing", "only targets stationary objects", "damage threshold"]],
                        ["1b3c5866a7f42776", ["1d10 Piercing", "two different turns", "natural 1 or 2"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-2e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const card = inspection.textContent.toLowerCase();
                        if (!terms.every(term => card.includes(term.toLowerCase()))
                            || card.includes("2024 provisional profile")) return false;
                    }
                    return true;
                })()''',
                'Final AD&D 1e weapon profiles distinguish form and enhancement': '''(async () => {
                    const cases = [
                        ["a920b880cce165eb", ["Longsword default", "Shortsword uses 1d6 Piercing"]],
                        ["fcb845cabca57466", ["+2 to attack rolls and +2 to damage rolls"]],
                        ["4aa5ba6d9f0a3bb3", ["+3 to attack rolls and +3 to damage rolls"]],
                        ["dee13ef43efdabe8", ["+3 to attack rolls and +4 to damage rolls"]],
                        ["fdc9a08b72736178", ["+3 to attack rolls and +5 to damage rolls"]],
                        ["e452f5db83175211", ["57–60", "Unearthed Arcana", "Omit the +1 from thrown damage"]],
                        ["b3ef23ee32508ee3", ["1d4 + 1 Wish charges", "charges never return"]],
                        ["4a50847bd4f974d2", ["attuned Paladin", "10 Radiant", "one target within 5 feet"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D magic staves retain their variants, charges, and spell effects': '''(async () => {
                    const cases = [
                        ["09d3dbf87ab6d8c3", ["Only a Cleric can cast Speak with Plants", "only a mammal"]],
                        ["6fd3f5457047b0b2", ["3d6 + 3 Hit Points", "twice between dawns", "only once between dawns"]],
                        ["5f4b7de783af3b00", ["Guarding Shield", "Paralyzing Cone", "Retributive Strike", "20 maximum"]],
                        ["5560d44119e052f1", ["Spell Absorption is its only recharge", "25 charges", "Whirlwind", "Hold Portal"]],
                        ["5dd72f5cad6aced0", ["spend 1–3 charges", "1d6 Force damage per charge"]],
                        ["061b888dc3dbe1c6", ["Treasure category", "On 1–60 use the Python", "On 61–100 use the Adder"]],
                        ["2cba28cc52c00f67", ["20 Hit Points", "3d6 Poison", "Cleric of evil alignment"]],
                        ["9c28e4c27f784e0f", ["Giant Constrictor Snake", "shares your Initiative", "staff is destroyed"]],
                        ["6c098d10142f9b48", ["Age (2 charges)", "Wither (3 charges)", "Exhaustion"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="Dungeon%20Masters%20Guide"]')) return false;
                    }
                    return true;
                })()''',
                'AD&D cursed and defensive swords show their limits and triggers': '''(async () => {
                    const cases = [
                        ["c5dbe9879aab6cd4", ["cannot drop or stow", "binding persists until Remove Curse"]],
                        ["616a28c5152d9ed9", ["at least 1 damage", "Wish can end the binding", "Subtract 2"]],
                        ["5a7b32d6e4f87288", ["enter a frenzy", "including an ally", "Remove Curse or Wish"]],
                        ["0b1fc58846b16ed0", ["+3 to attack and +4 to damage", "next three turns", "cannot make Opportunity Attacks"]],
                        ["41a012dcad4cfd95", ["15 Necrotic damage", "regain Hit Points"]],
                        ["b53683ab23e39c6c", ["14 Slashing", "level of Exhaustion", "Bright Light to 30 feet"]],
                        ["57f2fe239052b91a", ["1 Necrotic damage per open wound", "10 rounds", "DC 15 Wisdom (Medicine)"]],
                        ["2020ed63c7378e48", ["natural 20", "30 Slashing damage", "Legendary Resistance"]],
                        ["d43e82bbfddd7932", ["defense pool of 4", "melee attacks made with a held weapon"]],
                        ["27a7f5a1ccdc35bc", ["defense pool of 5", "capped at +3", "start of your next turn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="Dungeon%20Masters%20Guide"]')) return false;
                    }
                    return true;
                })()''',
                'AD&D slayer swords display their distinct target rules': '''(async () => {
                    const cases = [
                        ["b6170aed662ecfed", ["can cast spells using its own traits", "solely from an item"]],
                        ["e0e2b7d79de32223", ["Use +3 instead of +1", "lycanthropes", "Polymorph"]],
                        ["483d49f441fa939d", ["active Regeneration trait", "Ring of Regeneration"]],
                        ["b7746e441378574a", ["+3 to attack and +4 to damage", "wyverns"]],
                        ["6e2b805a2d8ba48d", ["true dragon", "chosen kind", "3d6 Slashing instead"]],
                        ["90be83f0bb1155f8", ["hill, stone, frost, fire, cloud, or storm giant", "ettins"]],
                        ["9ef73101e2dc1e04", ["1d6 Fire", "2d6 Fire", "3d6 Fire against an Undead"]],
                        ["169aa923a4716a96", ["Resistance to Fire", "roll a d20", "Wall of Fire"]],
                        ["e78e0738b8db7ece", ["9 charges and never regains", "fewer than 100 Hit Points", "spend no charge"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="Dungeon%20Masters%20Guide"]')) return false;
                    }
                    return true;
                })()''',
                'AD&D axes, hammers and bows retain their source distinctions': '''(async () => {
                    const cases = [
                        ["9c8b9917c926080f", ["Handaxe", "Omit the +1 from thrown damage"]],
                        ["c87ac3f00dff23d9", ["Omit the +2 from thrown damage", "Vex"]],
                        ["9cb257537606a013", ["Omit the +3 from thrown damage", "20/60 feet"]],
                        ["0ced01bd2ed7898b", ["Battleaxe", "Versatile (1d10)", "Topple"]],
                        ["d93b9fbc38c2896c", ["Shortbow 80/320 feet", "longbow 150/600 feet", "separately enchanted arrow"]],
                        ["5951496537fdc6a0", ["Light Hammer", "roll 61–62", "Nick"]],
                        ["1741233deaf7c1fe", ["1d8 Piercing + Strength modifier + 1", "Sap"]],
                        ["f365c467d111a4ca", ["+4 to damage", "+3 to attack rolls"]],
                        ["31ba46f9904b6a56", ["bullet counts as +1", "+2 on attack and damage rolls"]],
                        ["6bfed38d98ae256c", ["dormant +2", "awaken", "2d8 against a Giant"]],
                        ["f3e3aa8bc9a5c8f4", ["5 charges", "both a Belt of Giant Strength", "DC 17 Constitution"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="Dungeon%20Masters%20Guide"]')) return false;
                    }
                    return true;
                })()''',
                'AD&D weapon variants display range, size, and curse mechanics': '''(async () => {
                    const cases = [
                        ["c4427703cb9e533c", ["80/320 feet (light form)", "100/400 feet (heavy form)", "solely from range"]],
                        ["cd91d030bb55dadc", ["160/640 feet", "200/800 feet", "10%"]],
                        ["c0eeba477af6f9c2", ["Ignore the Loading property", "Bonus Action", "Advantage"]],
                        ["331efaa34e0b2cbe", ["Small or Tiny", "normal +1"]],
                        ["db44fbeec9c8c94b", ["Large, Huge, or Gargantuan", "normal +2"]],
                        ["7e27d95426bd4024", ["60/120 feet thrown", "attacks and damage"]],
                        ["124740dbbcbe3db3", ["threshold by 1", "doubled if you threw it", "Remove Curse"]],
                        ["dc1f27dbe6e1a12f", ["military fork 10 feet melee", "speak its command word"]],
                        ["ef118c1af6ae8609", ["activation 60 feet", "hit or miss", "normal javelin"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-1e-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="Dungeon%20Masters%20Guide"]')) return false;
                    }
                    return true;
                })()''',
                'AD&D magic weapons preserve edition-specific effects and verified enhancements': '''(async () => {
                    const cases = [
                        ["dmg-1e-reference:06a83e6ccff9f80d", ["Verified 2024 enhancement mapping", "1d8 Bludgeoning + Strength modifier + 1", "Sap"]],
                        ["dmg-1e-reference:0abe8105e39030c4", ["1d6 Piercing + Strength modifier + 2", "30/120 feet thrown"]],
                        ["dmg-1e-reference:3e57f62d36ca845e", ["1d6 Slashing", "printed +2 result", "Nick"]],
                        ["dmg-1e-reference:102858a5fccc7369", ["1d6 Piercing + Strength modifier + 3", "Versatile (1d8)"]],
                        ["dmg-1e-reference:cdf3a960d6197493", ["natural 20", "6 charges", "DC 15 Constitution"]],
                        ["dmg-1e-reference:f8a8e5b015a4ef82", ["4d8 Lightning", "back toward you", "javelin is consumed"]],
                        ["dmg-1e-reference:37a68cb7f7ccdf98", ["2d6 Radiant", "25 Hit Points or fewer", "evil alignment"]],
                        ["dmg-2e-reference:388cabf7634222a0", ["Advantage on Initiative", "Bonus Action"]],
                        ["dmg-2e-reference:49c267962d618915", ["2d8 Radiant", "60 feet", "Dim Light for 1 minute"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || inspection.textContent.includes("Same name and item type in the 2024 SRD")) return false;
                    }
                    return true;
                })()''',
                '3.5 ranged weapon references open the verified 2024 rules': '''(async () => {
                    const cases = [
                        ["730153223c036a0c", ["1d6 Piercing", "30/120 feet", "Light, Loading", "Vex", "free hand"]],
                        ["8575418a34b70216", ["1d10 Piercing", "100/400 feet", "Heavy, Loading, Two-Handed", "Push"]],
                        ["981442a7630f5c28", ["1d8 Piercing", "80/320 feet", "Simple ranged weapon", "Slow"]],
                        ["4b95e69131ad7b6a", ["1d8 Piercing", "150/600 feet", "Ammunition (Arrows)", "Slow"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const text = inspection.textContent;
                        if (!terms.every(term => text.includes(term))
                            || !text.includes("Verified 2024 equipment mapping")
                            || !inspection.querySelector('a[href*="br-2024/equipment#Weapons"]')) return false;
                    }
                    Array.from(inspection.querySelectorAll("button"))
                        .find(button => button.textContent === "Open published 2024 Longbow").click();
                    await itemDetails;
                    return inspection.querySelector("h2").textContent === "Longbow"
                        && inspection.textContent.includes("2024 weapon rules");
                })()''',
                'Remaining 3.5 DMG weapons distinguish combat rules from the adventure hook': '''(async () => {
                    const cases = [
                        ["7ff74e3ff671bbb8", ["1d10 Piercing", "30/90 feet", "Loading"]],
                        ["f1563d0c12ac1437", ["2d6 Piercing", "50/150 feet", "Reload (15)"]],
                        ["4252ac8fc27ea59f", ["3d6 Radiant", "40/120 feet", "Reload (50)"]],
                        ["09a0d55cd70e0162", ["Longsword equivalency", "1d8 Piercing", "gives no attack bonus"]],
                        ["94c9fd086322f7d5", ["Adventure hook involving an ancient sword", "supplies no sword type"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy magic staves display spell lists and charge rules': '''(async () => {
                    const cases = [
                        ["52563a8190068a46", ["Globe of Invulnerability (6 charges)", "Antilife Shell (5 charges)"]],
                        ["1954e64d2ffb22dd", ["Conjure Animals (3 charges)", "Creation (5 charges)"]],
                        ["259134c0461237c1", ["Warding Bond (2 charges)", "rings specified in the spell"]],
                        ["2cd040464d2c1fe8", ["concealed doors within 30 feet", "Arcane Eye (4 charges)"]],
                        ["7584c2117c70b124", ["Passwall (5 charges)", "Move Earth (6 charges)"]],
                        ["b7d6e2e2c1c3e28f", ["Mind Fog", "20-foot-radius Sphere", "Mass Suggestion (6 charges)"]],
                        ["ae1c20ffe5cb17d1", ["Fireball (3 charges)", "Chain Lightning (6 charges)"]],
                        ["194d8923e09c6796", ["Color Spray (1 charge)", "Sunburst (8 charges)"]],
                        ["9a2cf5d8bafbb698", ["Major Image (level 6) (6 charges)", "Hypnotic Pattern (3 charges)"]],
                        ["4498c7be9077c482", ["Raise Dead (5 charges)", "diamond worth at least 500 gp"]],
                        ["2eb0fcb4dc94fedf", ["Halt Undead", "three Undead", "Paralyzed"]],
                        ["6891fd64c4c53a03", ["Astral Projection (9 charges)", "jacinth and silver bar"]],
                        ["a7d07fe49281dfa7", ["Enlarge/Reduce (2 charges)", "Group Alteration"]],
                        ["aa881e71fa73e961", ["Polymorph (4 charges)", "Disintegrate (6 charges)"]],
                        ["86094b00ebd32f88", ["6 maximum", "Disintegrate (6 charges)", "cautionary example"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const text = inspection.textContent;
                        if (!terms.every(term => text.includes(term)) || !text.includes("expended charges daily at dawn")
                            || !inspection.querySelector('a[href*="SRD_CC_v5.2.1.pdf"]')) return false;
                    }
                    return true;
                })()''',
                'Legacy double weapons and named variants show their actual rules': '''(async () => {
                    const cases = [
                        ["fbc00d78ce1aa528", ["1d8 Bludgeoning with either head", "Bonus Action"]],
                        ["9b9fdf7a35a0cf87", ["1d8 Bludgeoning with the hammer", "1d6 Piercing with the hook"]],
                        ["beb59f6d82784010", ["1d8 Slashing with either head", "Cleave"]],
                        ["d4785ad25488639c", ["1d8 Slashing with either blade", "Vex"]],
                        ["07a52fd4e907fe4d", ["five bolts", "Utilize action", "80/320 feet"]],
                        ["1c1577ad5247e343", ["treat the hit as a Critical Hit", "objects only"]],
                        ["e1c7abdf4ab3ae28", ["680-foot radius", "aquatic predators", "+2 trident"]],
                        ["cece92789ac9d6b0", ["natural 20", "Legendary Resistance", "30 Slashing"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy masterwork weapons and composite bows display reviewed profiles': '''(async () => {
                    const cases = [
                        ["518abfeb772f1ba6", ["1d10 Piercing", "100/400 feet", "Masterwork quality affects appraisal"]],
                        ["a4a069a849e75818", ["1d10 Bludgeoning", "Heavy, Two-Handed", "Sap"]],
                        ["5485d110016652bf", ["cannot be used for a thrown attack", "Finesse, Light"]],
                        ["e9863270c96918e6", ["1d6 Slashing", "Shortsword comparison"]],
                        ["891e5eaa3589b49b", ["1d8 Piercing + Dexterity modifier + 2", "Strength rating +4", "150/600 feet"]],
                        ["db4ca38955dae998", ["Strength rating +1", "capped at +1", "80/320 feet"]],
                        ["0c97db6e503ed2fd", ["counts as silvered", "Nick"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="d20srd.org/srd/equipment/weapons.htm"]')) return false;
                    }
                    return true;
                })()''',
                'Named 3.5 weapons apply their distinctive effects': '''(async () => {
                    const cases = [
                        ["8f0d838e9c9ad461", ["1d6 Piercing + Dexterity modifier + 2", "2d6 Psychic", "lawful creature"]],
                        ["b128df25f1b1d5d0", ["+6 effective price equivalent", "one additional attack", "Haste"]],
                        ["78180b71c8ae7402", ["Choose one head", "+1 flaming and +3 disruption heads", "DC 15 Wisdom"]],
                        ["c52a41064271c6d4", ["Death Strike by 1", "does not grant Death Strike"]],
                        ["f5ae11166c98bb77", ["Spend 1 of 3 charges", "Hit Point maximum", "regains all charges at dawn"]],
                        ["0bbcfcfcc1eb2787", ["Use +2 on an Elemental Plane", "Use only the highest applicable bonus"]],
                        ["9fc1cefd952787af", ["1d6 Piercing", "does not grant Sneak Attack", "Vex"]],
                        ["814c5fca0cbb8b75", ["Outdoors in a temperate climate", "Cleave", "Nick"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Core weapon properties retain their limits and eligible hosts': '''(async () => {
                    const cases = [
                        ["35db1798a7b1d9b6", ["No damage to Constructs, Undead, or objects", "Total Cover"]],
                        ["46dda3c33c6f7a3f", ["four attacks total per activation", "Opportunity Attacks"]],
                        ["e5ea0b181b8ef325", ["transfer to AC", "Defender comparison"]],
                        ["4a4fcda66b4fa626", ["25 Hit Points or fewer", "DC 15 Wisdom"]],
                        ["5f53fe8ecac98ee0", ["1 Hit Point and Unconscious", "ranged hits"]],
                        ["aa02577e52c43712", ["third creature within 5 feet", "Cleave mastery"]],
                        ["d942c5bd1092215a", ["exactly one creature", "original caster’s slot level", "Concentration"]],
                        ["a10f85eb2c546316", ["1d8 Thunder once", "repeat the save"]],
                        ["6b183ba229ffeecc", ["30 Slashing damage", "Legendary Resistance", "natural 20"]],
                        ["0a692c105c267419", ["1d4 Necrotic damage per wound", "DC 15 Wisdom (Medicine)"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="magicWeapons.htm"]')) return false;
                    }
                    return true;
                })()''',
                'Legacy weapon upgrades resolve on eligible host weapons': '''(async () => {
                    const cases = [
                        ["2ab96006dcaf2318", ["fixed", "extra 2d6", "host weapon"]],
                        ["8b4a65edfcd3074c", ["Dragon type", "2024 Kobold Warrior", "Published 2024 Dragon Slayer comparison"]],
                        ["c02757d54356fd8a", ["gnoll", "Fiend"]],
                        ["24e5ac222422f19d", ["goblin, hobgoblin, or bugbear", "Fey"]],
                        ["177ada4c7961b108", ["Kobold Warrior qualifies", "Dragon"]],
                        ["0078a61a48c0f616", ["extra 1d6 Fire", "Bonus Action"]],
                        ["dd452c5b796c7fab", ["1d10 Fire damage once", "even if the property is inactive"]],
                        ["91f0eb16d4163442", ["1d10 Cold damage once", "roll the extra 1d6 twice"]],
                        ["19d518ba7c27cd1a", ["extra 1d6 Lightning", "1d10 Lightning damage once"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.querySelector('a[href*="magicWeapons.htm#"]')
                            || inspection.textContent.includes("upgrade’s item-specific 2024 rules still require review")) return false;
                    }
                    return true;
                })()''',
                'Optional DMG weapons show their conversion and source': '''(async () => {
                    const cases = [
                        ["1afb17b336476ec4", ["40/120 feet", "6 bullets", "Sap"]],
                        ["b1546608e4e26fcf", ["2d10 Piercing", "5 bullets", "Slow"]],
                        ["b3c91a6efc64bea4", ["Burst Fire", "10-foot Cube", "DC 15 Dexterity"]],
                        ["890e8d957e12136a", ["30/90 feet", "2 shells", "Push"]],
                        ["23e9278077b663f0", ["6d8 Necrotic", "120/360 feet"]],
                        ["10c616daf88b8fd2", ["3d8 Radiant", "30 shots per energy cell"]],
                        ["f6203078fe4978ea", ["2d6 Fire", "5-foot-radius Sphere"]],
                        ["73a78a0ace29b929", ["second turn after activation", "Heavily Obscured"]],
                        ["ada327d6e5996886", ["2d6 Bludgeoning", "conflicts with the 3d6 table row"]],
                        ["595b55ea73cb5cbe", ["4d6 Slashing", "20-foot-radius Sphere", "Grenade Launcher"]],
                        ["ffba257c6a185446", ["start of your next turn", "Heavily Obscured", "Grenade Launcher"]],
                        ["e0e2349bf59417fe", ["70 feet", "Fragmentation Grenade or Smoke Grenade"]],
                        ["4b9028fe8cffb94b", ["3d6 Fire", "200-foot Line", "once per turn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))
                            || !inspection.textContent.includes("D&D 2024 adaptation")
                            || !inspection.querySelector('a[href^="https://www.dndbeyond.com/"]')) return false;
                    }
                    return true;
                })()''',
                'Legacy martial weapons and treasure categories show their respective uses': '''(async () => {
                    const cases = [
                        ["dmg-35-reference:f7e1ad58f819727d", ["1d6 Slashing + Strength modifier + 1", "Topple"]],
                        ["dmg-35-reference:7753bc0c55462ecb", ["1d6 Slashing + Strength modifier + 3"]],
                        ["dmg-35-reference:90249fd63791fd55", ["10 feet, including adjacent targets", "forgo the hit’s damage"]],
                        ["dmg-35-reference:5e12c800e8dee80a", ["1d6 Bludgeoning", "knock it out"]],
                        ["dmg-35-reference:3769003d428a358b", ["2d6 Necrotic", "separately specified enhancement"]],
                        ["dmg-2e-reference:07bdcc4aa293a4ae", ["1d4 Bludgeoning", "Unarmed Strike"]],
                        ["dmg-2e-reference:304fdfbd05f233c3", ["Only captures Medium creatures", "Grappled and Restrained", "1d2 Piercing"]],
                        ["dmg-2e-reference:b93711e98661a11f", ["1d10 Slashing", "cleaver-headed polearm", "Cleave"]],
                        ["dmg-35-reference:105afc5f4ed2b075", ["Provenance and shop category", "smith mark identifies its origin"]],
                        ["dmg-2e-reference:de2bcb3f7fd9932d", ["Random treasure weapon category", "Glaive, Halberd, or Pike"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'D&D 3.5 named weapons display sentience and their signature powers': '''(async () => {
                    const cases = [
                        ["7393feb7a0a98bfa", ["Zone of Truth, Clairvoyance, or Slow", "19 or 20", "Blindsight out to 120 feet"]],
                        ["95e92154610a27b3", ["Bless or Hold Person", "opinionated poet"]],
                        ["58d7fabaf3e6f04b", ["2d6 extra damage", "Only Giants in its area", "Jomnoth’s consent"]],
                        ["959727f61926ff11", ["blocks spells of level 3 or lower", "2d6 extra Radiant"]],
                        ["e2ca74501c285620", ["three nonrenewable Wish charges", "If Vesac consents"]],
                        ["6085ecfc99f2cf2b", ["2d6 extra Necrotic", "reduce your Hit Point maximum by 1d6"]],
                        ["3cd49976e07d063a", ["sundering strike", "including a held weapon", "+4 total"]],
                        ["83cd5cec312379a6", ["both ends are silvered", "DC 15 Wisdom", "original form"]],
                        ["cb19c4a4af46d927", ["20 gp in Thorris", "1d8 Slashing"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("dmg-35-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Legacy military picks and masterwork weapons show playable equipment rules': '''(async () => {
                    const cases = [
                        ["dmg-1e-reference:c09325a7645ffe53", ["1d8 Piercing", "Strength modifier + 1", "Table III.H"]],
                        ["dmg-2e-reference:026d051b073114b5", ["War Pick", "separately determined enhancement"]],
                        ["dmg-35-reference:13e0a18b0fed4bf5", ["1d8 Slashing (axe) or 1d6 Piercing (spike)", "Bonus Action"]],
                        ["dmg-35-reference:d445c700bdf6e407", ["1d4 Slashing", "Finesse, Light", "MasteryNick"]],
                        ["dmg-35-reference:6300be7ebfae1aa4", ["2d4 Piercing", "10 feet", "forgo hit damage"]],
                        ["dmg-35-reference:dfc0f41a24ce7cf1", ["1d6 Piercing", "20/60 feet thrown", "no extra attack bonus"]],
                        ["dmg-35-reference:4a1b67cf5b664fd4", ["No direct damage", "DC 10 Strength", "AC 10, 5 Hit Points"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'AD&D nets and concealed or returning weapons show their distinct rules': '''(async () => {
                    const cases = [
                        ["dmg-1e-reference:c1d5cf24c5644133", ["10-foot square", "5-foot cube", "DC 20 Strength", "7500 gp"]],
                        ["dmg-2e-reference:c1d5cf24c5644133", ["DC 15 Dexterity", "hanging it overhead", "AC 19"]],
                        ["dmg-1e-reference:14b6a1738975af4e", ["30 feet underwater", "no magical effect out of water", "6000 gp"]],
                        ["dmg-2e-reference:14b6a1738975af4e", ["speak its command word", "Destroying it frees everyone"]],
                        ["dmg-2e-reference:49f814d47541be34", ["1d6 Piercing", "40/120 feet", "After a miss it permanently becomes"]],
                        ["dmg-2e-reference:55e6b768e5d06354", ["scimitar 1d6 Slashing", "20/60 feet", "Scimitar variants are +2 or +3"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault late upgrades display relocation and ongoing effects': '''(async () => {
                    const cases = [
                        ["08047318633f9e93", ["original DC", "transfers to the target with its remaining duration"]],
                        ["96f1220f44b3a7bc", ["DC 16 Charisma", "simultaneously teleport"]],
                        ["4c2464e31315f131", ["even if the creature stays within your reach", "halve its Speed"]],
                        ["f2b4a7688dcf0775", ["Blinded, Prone, Restrained, or Unconscious", "also falls Prone"]],
                        ["dc7df0c7d01bf938", ["normal hit damage becomes Necrotic", "extra damage after applying the target’s defenses"]],
                        ["22561f12cd1f016c", ["10 feet straight toward", "each ally within 50 feet"]],
                        ["e5297a2efb6586bb", ["Bloodied before the hit", "attacks you make with this weapon", "official 4e errata"]],
                        ["3fddf25f85a518ab", ["extradimensional space", "within 15 feet of you"]],
                        ["89c7193ebeacfec4", ["normal surface range rules", "Swim Speed or can breathe underwater"]],
                        ["2f3cf054f3b31323", ["cumulative −1 penalty", "up to −3", "entire penalty ends"]],
                        ["da0dbe46397588c7", ["5 damage of the weapon’s type", "DC 15 Constitution saving throw with a −1 penalty"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault upgrades show ranged exceptions and recharge': '''(async () => {
                    const cases = [
                        ["4d1ff22c9f50f3d2", ["within 25 feet", "5 Acid damage"]],
                        ["51d834902c24bacf", ["halve its Fly Speed", "50 feet straight down"]],
                        ["0592834c055b7cb9", ["no long-range Disadvantage", "Wisdom modifier"]],
                        ["ec0a714df768be4f", ["within 5 feet of the first target", "1 plus your Dexterity modifier"]],
                        ["9808dc1180daf57c", ["increase that distance by 5 feet", "falls Prone"]],
                        ["4f8d906e5c9e29ce", ["within 50 feet", "takes 2 Lightning damage"]],
                        ["611c0bdab63ff4c5", ["Constitution saving throw", "weapon’s normal hit damage"]],
                        ["cedba87e3380b6f5", ["reduce your outgoing weapon damage"]],
                        ["ab3fcc35628d3472", ["attack roll with Advantage", "official 4e errata"]],
                        ["cb70d035ae46259a", ["ignores its Loading property", "recharges at dawn"]],
                        ["e61a73b904193288", ["give yourself Advantage", "Short or Long Rest"]],
                        ["e5e63d1825c8ac28", ["Sleight of Hand", "Passive Perception"]],
                        ["bf48c70cca6aa548", ["yes-or-no question", "Wisdom saving throw"]],
                        ["c2e55f1ed0434e79", ["within 50 feet of the first target", "no additional ammunition"]],
                        ["9d51976a0f2accb2", ["10 feet straight toward", "1d6 extra Thunder damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault paired, ranged, and critical weapon effects are displayed': '''(async () => {
                    const cases = [
                        ["c373e34ca3739e92", ["split it into two identical weapons", "share one attunement"]],
                        ["4427038bbf0d4071", ["make its Speed 0", "more than 5 feet apart"]],
                        ["44fe30b4e845aec3", ["ignore the Disadvantage caused solely", "Short or Long Rest"]],
                        ["820b17a20c0a8822", ["5 Poison damage", "deals half damage"]],
                        ["33bf0554e6cd4df9", ["within 25 feet", "attack rolls that do not target you"]],
                        ["47b93b69c5d7251f", ["no ally is closer"]],
                        ["885926ac94d30a54", ["one additional attack", "normal range, ammunition, and loading rules"]],
                        ["a97e432343a391de", ["normal damage type and Radiant", "2 extra Radiant damage"]],
                        ["64343a86f87544c8", ["−2 penalty to your AC", "official 4e errata"]],
                        ["b4af69a23f4615fe", ["Once per turn", "cannot trigger another attack"]],
                        ["863a62c4bcc0a9cc", ["−2 penalty to attack rolls", "DC 15 Wisdom"]],
                        ["329e0263748699d6", ["scores a Critical Hit against you", "1d6 extra damage"]],
                        ["781908b219585023", ["within 10 feet of the first target", "same piece of ammunition"]],
                        ["8fef4f4bd924e074", ["cannot take Bonus Actions or Reactions", "alignment is evil"]],
                        ["a8c638f8caa977b8", ["expend one unspent Hit Point Die", "deals half damage"]],
                        ["025c13dc8738330d", ["1d20 extra damage if the target is a reptile"]],
                        ["524e4d8a4fbac7b4", ["DC 15 Strength", "Speed is 0"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault upgrades display reactions and hit effects': '''(async () => {
                    const cases = [
                        ["fb5fd130405630e0", ["Allies within 5 feet", "add 1 to their damage rolls"]],
                        ["4a1dc756fd1c08b1", ["19 or 20", "10 damage", "official errata"]],
                        ["be1331192cd39f3c", ["deals half damage", "cannot take Bonus Actions or Reactions"]],
                        ["636b9510488fe1a6", ["take one additional action", "cannot take the Magic action"]],
                        ["12a77fbf8aab183a", ["first repeat fails", "falls Unconscious"]],
                        ["69d9257636c8f2c2", ["proficient with Simple weapons", "regain one expended Superiority Die"]],
                        ["ebb0a931605a05b7", ["first 5 feet of that movement", "Construct or object"]],
                        ["a4819e0982d6d97c", ["within 50 feet", "expires after 1 minute"]],
                        ["5f8f55e0bfd90b74", ["half its hit damage", "Wisdom saving throw"]],
                        ["8da201e62b887e91", ["worship Moradin", "10-foot Emanation", "falls Prone"]],
                        ["c6016cb3c2fa2dd8", ["10 extra Necrotic damage", "next time"]],
                        ["a0640ce68fb8470c", ["as part of that Reaction", "1d12 if the hit is an Opportunity Attack"]],
                        ["47f7b870d6f6ffeb", ["15 feet melee, 5 feet for Opportunity Attacks"]],
                        ["ba7e502687cbb81c", ["Speed is 0", "immune to Poison damage"]],
                        ["9e1b79efff38ff44", ["exceeds the triggering attack roll", "parry roll deals no damage"]],
                        ["f30f2bb2483bf10d", ["1 plus your Dexterity modifier", "DC 15 Constitution"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault upgrades display altered forms and distances': '''(async () => {
                    const cases = [
                        ["3fb45c92542b03d4", ["175/650 feet", "25 feet to the weapon’s normal range"]],
                        ["8287f5f8bc2373f1", ["−1 penalty to AC, saving throws, and ability checks"]],
                        ["a50600e56e0b86fa", ["another Simple or Martial melee weapon", "reverts after 1 minute"]],
                        ["4a5ffc11309879b0", ["normal ammunition and loading requirements", "additional +2"]],
                        ["054bab2b7123d9ec", ["up to 25 feet away", "does not grant extra attacks"]],
                        ["955a1ef365ab3c41", ["cannot teleport until the end of your next turn"]],
                        ["4c132cda032ebed5", ["non-Incapacitated ally", "within 5 feet of it"]],
                        ["1662b1a58ac3bfe3", ["DC 15 Strength", "Elementals associated with earth subtract 5"]],
                        ["ba98af93896fb34d", ["teleports to a space within 5 feet", "DC 16 Charisma"]],
                        ["821caf7b8270887a", ["normal type and Force", "up to 5 feet"]],
                        ["751905495de77b1f", ["push that creature up to 5 feet", "choose either that push"]],
                        ["283dcfee946cda60", ["roll 1d6 and subtract 3", "including a negative result"]],
                        ["643494eaa7efa6c8", ["pull it up to 15 feet", "Short or Long Rest"]],
                        ["899607f3ff62393c", ["after its attack resolves", "Dexterity modifier"]],
                        ["6b8cba6775d4ae03", ["pull it up to 5 feet", "official 4e errata"]],
                        ["cfb55718964dd8ec", ["Healing Word", "5 plus your Wisdom modifier"]],
                        ["ffec670af5fda118", ["Once per round", "within 5 feet of the first target"]],
                        ["bc1888bb6a17a3b0", ["within 100 feet", "unspent Hit Point Die"]],
                        ["783d7304bfe817e0", ["bonus ends if you hit", "do not increase the bonus beyond +1"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault upgrades display movement, saves and damage limits': '''(async () => {
                    const cases = [
                        ["e4e402d11ba5c84e", ["Bloodied before the attack", "2 extra damage"]],
                        ["a427426381491d45", ["up to the unresisted amount", "variable Resistance"]],
                        ["0326e52d7e2ca1d4", ["The first hit makes the weapon visible", "Short or Long Rest"]],
                        ["73752cbc463faac6", ["Speed becomes 0", "Fey", "1d10 extra damage"]],
                        ["828bf08595e9fc18", ["within 25 feet", "before the result is announced"]],
                        ["efdc6a18b41d226c", ["10 feet melee", "increase the distance by 5 feet"]],
                        ["687348412bcd0a46", ["rounded down, becomes Radiant", "expended use of your Channel Divinity"]],
                        ["064dceea5ce0969c", ["first repeated save", "official 4e errata"]],
                        ["d386a3d39d62d2e2", ["5 Necrotic damage", "DC 15 Constitution"]],
                        ["40a250f113d8956e", ["Intelligence, Wisdom, and Charisma saving throws", "penalties do not stack"]],
                        ["820bf9143308dc74", ["Dodge action", "Second Wind"]],
                        ["a78a5772fa29752c", ["gain +5 on the roll", "Immunity still applies"]],
                        ["93f50d0a9a94d2a8", ["maximum penalty of −3", "without this penalty"]],
                        ["6f0d5982f8ea2f46", ["5 feet times the higher", "repeat the thrown attack", "returns to your hand"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault pact weapons and early upgrades display source rules': '''(async () => {
                    const cases = [
                        ["1258914b58aaf463", ["1 additional Hit Point", "Base cost4005 gp"]],
                        ["d85019bb2e131e33", ["Dwarf with Pact Magic", "errata removes"]],
                        ["1f673b4a1b7ac866", ["your Hex spell", "Charisma saving throw", "teleport it up to 10 feet"]],
                        ["635a308df1acf9c3", ["add 2 damage of that type after the reduction", "Immunity"]],
                        ["2ee24c05b16c7240", ["5 Poison damage", "does not halve Speed"]],
                        ["fa5bc8f7e3d0b569", ["15-foot Cone", "separate melee attack roll"]],
                        ["f78861ff73dbd0d6", ["While Bloodied", "lose Hit Points equal to half your level"]],
                        ["626ab71239f79fa6", ["recover one expended Superiority Die"]],
                        ["87f59e6353f2e5dc", ["At the start of your next turn", "damage it actually took"]],
                        ["26ff6d54f903815e", ["reduces a hostile creature to 0 Hit Points", "1d8 Temporary Hit Points"]],
                        ["fce2e73fe26a4bdd", ["Each hit with it deals 2 extra damage"]],
                        ["8d5743f75c806ca1", ["lose 1 Hit Point", "Short or Long Rest", "official 4e errata"]],
                        ["77510604cf6dd4f2", ["delayed damage uses a fresh 1d10 roll"]],
                        ["f4276be51570cc24", ["25-foot radius", "Dexterity saving throw", "as Radiant damage"]],
                        ["1cac57a1a959c90a", ["Half Cover", "native to the Shadowfell"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault staffs retain spell damage, range, and targeting rules': '''(async () => {
                    const cases = [
                        ["4cf1e3385708dd6c", ["Fire damage dealt by spells cast through it to Acid"]],
                        ["aeea4daa7b94db22", ["extra 1d6 Acid damage", "must use the new result"]],
                        ["1e58435aa5365faf", ["within 10 feet", "including against the triggering damage"]],
                        ["4e6d7ba5336fe75c", ["halve all damage", "+10 damage"]],
                        ["d369958b422dec8a", ["Light cantrip", "1 Radiant damage"]],
                        ["584d8fb564f75a0b", ["one additional dart", "exactly two creatures within 25 feet"]],
                        ["9d0e4924b4960f33", ["one damage roll per casting", "1d10 extra damage"]],
                        ["fd47ffe30df1c326", ["recurring Fire damage", "5 extra Fire damage"]],
                        ["7757ce6d0bfe0388", ["up to two hands", "10-pound carrying limit"]],
                        ["abcc6341f8dd8ca9", ["within 25 feet", "normal save and DC"]],
                        ["061b888dc3dbe1c6", ["extra 1d6 Poison damage", "DC 15 Constitution"]],
                        ["e2585ec93a87ac0d", ["willing ally", "closest unoccupied space outside it"]],
                        ["1b0624e09f1b5a46", ["cast Shield", "add 1 to the AC bonus"]],
                        ["e562b1cf2bd81d68", ["increase that range by 5 feet", "does not change the area’s dimensions"]],
                        ["90fa8a7e5e547dc6", ["neither deals damage nor calls for an attack roll or saving throw"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!["1d6 Bludgeoning", "Topple", "draft conversion plus 2024 Quarterstaff cost", ...terms].every(term => details.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault staffs show separate melee and spell rules': '''(async () => {
                    const cases = [
                        ["051dc26c9d98c71d", ["contiguous 5-foot section", "one 5-foot section stays in place"]],
                        ["5eb13f9bcb99e37d", ["Dexterity, Constitution, and Wisdom saving throws", "+1 AC"]],
                        ["b53907765f92a63d", ["Hit Point Die", "take one additional action"]],
                        ["79ae3c1eeffbe108", ["−1 penalty", "Restrained condition"]],
                        ["c516510eead17f11", ["stinging insects", "without expending the activation"]],
                        ["e6aff2438b13108c", ["move its target up to 5 feet", "1d6 extra Force damage"]],
                        ["007f5c5dd65211fe", ["prepared Wizard spell", "level 3 or lower"]],
                        ["51f19239e6c3940c", ["cast one cantrip", "usual targeting, components"]],
                        ["fc2dd9a8ad5943b2", ["every attack from that casting missed", "regain the expended slot"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        const details = inspection.textContent;
                        if (!["1d6 Bludgeoning", "Spell attack rolls", "Topple", "draft conversion plus 2024 Quarterstaff cost", ...terms].every(term => details.includes(term))) return false;
                    }
                    inspect("adventurers-vault-1-reference:536e100318df89f1", grid.firstElementChild);
                    await itemDetails;
                    return inspection.textContent.includes("Base cost40015 gp");
                })()''',
                'Adventurer’s Vault named weapons replace improvised rules': '''(async () => {
                    const cases = [
                        ["db75c41d745a12cf", ["1d6 Piercing", "Holy Symbol", "reroll it"]],
                        ["536e100318df89f1", ["25-foot Cone", "Dexterity saving throw", "Wisdom modifier plus"]],
                        ["7758c394773d988b", ["10-foot Emanation", "Heavily Obscured", "Blinded condition"]],
                        ["3a134deb66ca2057", ["next attack roll", "Short or Long Rest"]],
                        ["7698edd888a06c3e", ["Rogue’s Sneak Attack", "Charisma modifier"]],
                        ["852768bbf1909a79", ["must use the second result", "1d8 extra"]],
                        ["fdafbf5466fdecdc", ["natural 1", "up to 6 charges"]],
                        ["1549cdca122da82b", ["sworn foe", "1d10 if the target"]],
                        ["30a62439e0fa782c", ["20/60 feet thrown", "gain the Invisible condition"]],
                        ["024bafbdda5d59eb", ["DC 15 Constitution", "1d12 if the target is currently transformed"]],
                        ["187e2a059ef1cb3b", ["100-foot radius", "5-foot Emanation", "1d8 Radiant"]],
                        ["4eeb7421819f92e6", ["1d6 Piercing per gauntlet hit", "one melee attack with each gauntlet", "Recharges at dawn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["D&D 2024 weapon adaptation", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault early armor displays source-specific powers': '''(async () => {
                    const cases = [
                        ["4f2cf91bdf63cccd", ["5 Poison damage", "5 feet without provoking"]],
                        ["740905e22bea8a12", ["above half your Hit Point maximum", "maximum additional bonus of +1"]],
                        ["9b087796f132cee6", ["cracks at least 1 inch wide", "lose 5 Hit Points"]],
                        ["b948ebe6560f451b", ["ally within 25 feet", "become the target instead"]],
                        ["71a78a016f228a15", ["add 2 to saving throws", "recurring damage"]],
                        ["83f3fc36dc8d2630", ["spend a Hit Point Die", "1 extra Hit Point"]],
                        ["7e5db28ca839252d", ["Battle Master", "Use a d8", "usual trigger and action cost"]],
                        ["5035f6f54e4e1713", ["successful saving throw", "take no damage"]],
                        ["c6837ebdb0dda2b2", ["Resistance to Radiant", "does not provoke Opportunity Attacks"]],
                        ["cc43106a64cbdc9d", ["fixed when it is created", "Fire, Force, Lightning"]],
                        ["c5f6f04ccbd2a48f", ["transfer it to yourself", "within 25 feet"]],
                        ["385c37ab5174e31e", ["Opportunity Attack", "DC 16 Constitution"]],
                        ["226f415befc6bbc7", ["surprised does not impose Disadvantage"]],
                        ["4fcb3810b7ed293c", ["DC 15 Wisdom", "normally after this first save"]],
                        ["3dd0516105e844fb", ["10 feet straight toward", "+2 bonus to the attack roll"]],
                        ["21140b6d043dd3cb", ["takes 2 Fire damage", "allies as well as enemies"]],
                        ["af51e57c0ead66b7", ["+2 AC against attack rolls made by that creature"]],
                        ["b5071444afe8ab08", ["leaves you Bloodied", "Necrotic damage equal to that amount"]],
                        ["6fdd1cb2fae8a9de", ["Fighter’s Second Wind", "within 60 feet"]],
                        ["7cab1704d49a3cce", ["Resistance to Necrotic and Poison", "Remove Curse"]],
                        ["fff2942ee4ed4828", ["teleport up to 15 feet", "at most 10 feet thick", "expend the use"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault armor displays movement, saving throws, and errata': '''(async () => {
                    const cases = [
                        ["32ee1c7a74c2337d", ["blur your position for 1 minute", "attack rolls against you have Disadvantage"]],
                        ["c242f4e4906e49cb", ["Wisdom saving throw", "cannot take Bonus Actions or Reactions"]],
                        ["1a2cc4b6ed4c999a", ["Dim Light within 25 feet", "more than 25 feet"]],
                        ["a9f9f17c4ba5b005", ["Resistance to Psychic", "within 10 feet", "rounding each half up"]],
                        ["1d90857c8c82a5ee", ["Strength requirementNone", "Stealth disadvantageNo", "halve the damage"]],
                        ["fe209ba4afcc6b0c", ["because you took the Hide action", "attack-roll benefits"]],
                        ["56e62f7f531fbd6b", ["5 Temporary Hit Points", "Short or Long Rest"]],
                        ["4e788d770a373169", ["Studded Leather Armor", "Splint Armor", "both bonuses fall to +1"]],
                        ["9ba2329383fda9b4", ["flexible mode", "Heavy armor training"]],
                        ["ddab9ccd7d1a1f34", ["Death Saving Throws", "replace the d20 result with 20"]],
                        ["6dc08550778dd3fe", ["Fighter’s Action Surge", "errata", "removed the printed daily power"]],
                        ["2b64f7c211aaf85d", ["DC 16 Constitution", "halve all damage dealt by that weapon", "10 Force damage"]],
                        ["c258fd6342322787", ["within 10 feet", "DC 15 Strength", "nearest unoccupied space"]],
                        ["4e0f78cb17f1a6cc", ["outdoors, Difficult Terrain costs you no extra movement"]],
                        ["2b3a0bdfd94b8e2b", ["Undead hits you with a melee attack", "1 Radiant damage"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault robes display distinct reactions and daily powers': '''(async () => {
                    const cases = [
                        ["7dc3af729b56fac4", ["subsequent attack rolls", "do not stack the penalty"]],
                        ["0db8777263115fdf", ["moves into a space within 5 feet", "push it 5 feet"]],
                        ["de40a706ab2eb5c7", ["made with Advantage", "1 Radiant damage", "Armor class19"]],
                        ["a671a6db3d11a029", ["within 50 feet", "unoccupied space it occupied", "Short or Long Rest"]],
                        ["cb185b4ca04493c8", ["Bloodied", "teleport up to 30 feet", "Hit Point Die"]],
                        ["8d7136a60c68a4c0", ["take no Fire damage", "Speed by 10 feet"]],
                        ["6a197142cadbd4a6", ["take no Cold damage", "gain +1 AC"]],
                        ["8756dbc2e48751ab", ["Resistance to Lightning and Thunder", "+1 on attack rolls"]],
                        ["4be0ccee9c36526c", ["immunity to the Blinded condition", "Wisdom (Perception)"]],
                        ["cf641797c3fe6f00", ["subtracts 1 from its attack rolls", "ends early if you make an attack roll"]],
                        ["884f939262902281", ["1d6 Piercing damage", "DC 15 Constitution"]],
                        ["beec86d262a20f34", ["first success reduces", "second success ends both"]],
                        ["30a69cf3370d5a0a", ["20-foot radius", "10-foot Emanation", "Intelligence or Charisma"]],
                        ["5d97413c7d116a7c", ["including during the triggering attack", "DC 16 Constitution"]],
                        ["baa3f5d2df844824", ["telepathic command", "force a new save", "Total duration cannot exceed 1 minute"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault armor displays its saves, transformations and stacking limits': '''(async () => {
                    const cases = [
                        ["9cb56e59b7f76040", ["Intelligence, Wisdom, or Charisma", "must use the new result", "Studded Leather Armor", "Splint Armor"]],
                        ["364350cb65d6106f", ["within 50 feet", "soil or sand", "DC 15 Strength"]],
                        ["7c8a91c0c166612c", ["2d6 Necrotic damage", "Strength and Constitution saving throws"]],
                        ["f9cdb5b2afa0846d", ["While Bloodied", "20 minus your number of unspent Hit Point Dice"]],
                        ["a0bf4a42b16a4917", ["including against the triggering attack", "do not stack"]],
                        ["bbf1c166276ae6c1", ["second combat encounter", "fourth such combat", "returns to +1"]],
                        ["6ee9861683df5c29", ["within 25 feet", "original range and targeting rules"]],
                        ["c6fd247e0baaadee", ["Resistance to Fire and Radiant"]],
                        ["05982260952338ee", ["Tiny rat", "Climb Speed of 20 feet", "up to 1 hour total", "cannot attack, speak, or cast"]],
                        ["172f6f0dc6d92175", ["AC contribution minus 10", "exclude bonuses from shields"]],
                        ["d601df76f8fb1afd", ["+1 AC and +1 on saving throws", "start of your next turn"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault defensive armor keeps each equipment variant and trigger': '''(async () => {
                    const cases = [
                        ["22b6eb6e1f0a8316", ["Armor class17", "Armor class19", "Armor class15 + Dex modifier (max +2)", "recurring Acid damage"]],
                        ["f8211a37f5f4a946", ["Armor class19", "16–20", "normal hit"]],
                        ["c33ce70e5e819db3", ["Armor class19", "within 25 feet", "Cold or Fire Resistance"]],
                        ["75814016103cc2dd", ["Cold damage", "reduce its Speed to 0"]],
                        ["67ed50e8e31a7248", ["Armor class12 + Dex modifier", "10 feet without provoking Opportunity Attacks"]],
                        ["deb9b38ed4cf5af0", ["Frightened condition", "Second Wind", "3 Temporary Hit Points"]],
                        ["fe97a1e2f68b3d2a", ["recurring Poison damage", "including the Poisoned condition"]],
                        ["e103d0bcf92e8233", ["Armor class17", "Armor class19", "ordinary-looking clothing", "Charisma (Deception)"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault chromatic armor keeps distinct resistances and powers': '''(async () => {
                    const cases = [
                        ["5ec193393b794d38", ["Resistance to Acid", "attack rolls against you have Disadvantage", "1d6"]],
                        ["f0b8e04c763c2f08", ["Resistance to Lightning", "two other creatures", "within 25 feet", "1d8"]],
                        ["bb2b1f54c42efe91", ["Resistance to Poison", "10-foot Emanation", "Constitution saving throw", "half as much damage"]],
                        ["fd201a63831513bd", ["Resistance to Fire", "Speed is 0", "5 plus your Constitution modifier", "end of each of those turns"]],
                        ["7851171cdef9967f", ["Resistance to Cold", "its allies within 5 feet", "1d4"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["Armor class15 + Dex modifier (max +2)", "Base cost40050 gp", "Once per dawn", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault shields show charge, volleys, and redirected attacks': '''(async () => {
                    const cases = [
                        ["8266a9c12c0eae85", ["Opportunity Attack", "10 feet straight", "cannot be pushed or pulled"]],
                        ["7dcb40e164948b4f", ["15-foot Cube", "within 50 feet", "Strength modifier Piercing", "4e errata"]],
                        ["67d799b006450b31", ["attacker takes 2 Radiant damage"]],
                        ["052de1adeb3be409", ["all allies within 5 feet", "Short or Long Rest"]],
                        ["d5aa073f3631525a", ["Fire or Radiant damage on a hit", "2 extra Radiant damage"]],
                        ["23cf02c2d5017c07", ["Slashing damage", "1d8 plus your Constitution modifier"]],
                        ["0eca938df8db99f9", ["DC 15 Strength", "Prone condition"]],
                        ["93f3c73f6195f783", ["new d20", "against its own AC", "Base cost40010 gp"]],
                        ["a27ee4ef903a3a52", ["different creature within 50 feet", "applying cover from your position"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["Armor class bonus+2", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault shields show healing, Bloodied and critical-hit rules': '''(async () => {
                    const cases = [
                        ["9efffeae699af78a", ["after resolving that attack", "+1 AC for 1 minute"]],
                        ["dd50ce9ec628e1d7", ["unspent Hit Point Die", "Constitution modifier"]],
                        ["6c2c535e80909584", ["Critical Hit", "by 5", "before applying Resistance"]],
                        ["3b996bea3158d5bc", ["The chosen creature must be Bloodied", "by 5"]],
                        ["423e623b4d24e3b8", ["by 2", "cease to be Bloodied"]],
                        ["6880aabf814a9294", ["Intelligence, Wisdom, or Charisma", "Add 4"]],
                        ["4002bbf4a5fa758a", ["additional +1 AC", "first round of combat"]],
                        ["ea358717dc8cd707", ["Strength or Constitution", "Add 4"]],
                        ["263216006fc71340", ["DC 15 Constitution", "Blinded"]],
                        ["159304cfa86cac3f", ["Swim Speed", "while swimming on the surface"]],
                        ["a5a5c31e3a514dae", ["within 60 feet", "rolled their maximum"]],
                        ["603a066e2f2f8a36", ["DC 15 Wisdom", "end of each of its turns"]],
                        ["d1c2564d442ac200", ["Resistance to Fire", "including against the triggering damage"]],
                        ["51a18e8f85fb50b5", ["Critical Hit", "turn it into a normal hit", "Base cost410 gp"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["Armor class bonus+2", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Draft magic armor and shield prices include only the mundane base': '''(async () => {
                    const cases = [
                        ["adventurers-vault-1-reference:64292fadc3c1368f", ["Base cost410 gp", "Base buy1025 gp", "Base sell164 gp", "Uncommon draft conversion plus 2024 Shield cost"]],
                        ["adventurers-vault-1-reference:ccce738f9a38793f", ["Base cost4010 gp", "Rare draft conversion plus 2024 Shield cost"]],
                        ["adventurers-vault-1-reference:ffa51a050b229967", ["Base cost40010 gp", "Very Rare draft conversion plus 2024 Shield cost"]],
                        ["adventurers-vault-1-reference:82aa9792b6fd9c06", ["Base cost5500 gp", "Rare draft conversion plus 2024 Plate Armor cost"]],
                        ["open5e-srd-2024:srd-2024_shield", ["Base cost10 gp"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect(id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault shields show area defense, wall statistics and attacks': '''(async () => {
                    const cases = [
                        ["ccce738f9a38793f", ["saving throws against the same area effect", "Resolve the effect against you"]],
                        ["0e951b5fa08ec77b", ["25 feet", "AC 17, 40 Hit Points", "1 hour without Concentration"]],
                        ["ffa51a050b229967", ["Resistance to Lightning and Thunder", "1d6 Lightning damage and 1d6 Thunder"]],
                        ["4418f96ed9129769", ["add 2 to the saving throw DC", "push the target 10 feet"]],
                        ["64292fadc3c1368f", ["50 feet", "1d8 + your Strength modifier Bludgeoning", "push it 5 feet"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["Armor class bonus+2", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault shields distinguish base AC from triggered defenses': '''(async () => {
                    const cases = [
                        ["57c91b4becb53a37", ["Disadvantage", "Short or Long Rest"]],
                        ["aedb8743a16da5b6", ["each melee attack by 5", "1 minute"]],
                        ["dfb978019e260ff7", ["additional +2 AC against Opportunity Attacks", "flanking rule"]],
                        ["481151e1269435b9", ["one ally within 5 feet", "+1 AC for 1 minute"]],
                        ["81fdc9dd112bf01e", ["Reaction", "+4 AC against that attack", "turning the hit into a miss"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!["Armor class bonus+2", ...terms].every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault tactical and transformation armor shows its limits': '''(async () => {
                    const cases = [
                        ["b73a33894e7e865b", ["Armor class19", "Intelligence modifier", "other than an attack roll"]],
                        ["96b933e0f32db536", ["Padded Armor", "Fly Speed of 30 feet", "lose 5 Hit Points", "up to 1 minute"]],
                        ["e3dbecff318dbc4d", ["Armor class19", "Radiant Resistance returns", "Fire, Lightning, or Thunder"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault defensive armor shows its triggers and targets': '''(async () => {
                    const cases = [
                        ["02d1e62551e106b0", ["Armor class21", "25-foot Emanation", "DC 17 Wisdom", "end of each of its turns"]],
                        ["49af94add999cbf6", ["Armor class20", "extradimensional space", "wearing no armor", "fully donned"]],
                        ["7722f819b919e2ba", ["Padded Armor", "willing ally within 25 feet", "other effects of the hit"]],
                        ["8f0f4a85196892d8", ["Armor class20", "Lightning or Thunder", "10-foot Emanation", "No saving throw"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault elemental armor shows ally protection and healing': '''(async () => {
                    const cases = [
                        ["e76e25c0dbae2266", ["Armor class20", "Radiant healing", "Hit Point Die", "10-foot Emanation"]],
                        ["76a0330e105ccc61", ["Armor class21", "Necrotic and Psychic", "unspent Hit Point Dice"]],
                        ["47e3391c01934a31", ["Armor class18", "ally within 25 feet", "immune to those types"]],
                        ["1d3e1a8fcb2bd0da", ["Armor class21", "ally within 50 feet", "hits you instead"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault armor shows jump escape poison and temporary HP rules': '''(async () => {
                    const cases = [
                        ["f7e25d7df13456d8", ["Padded Armor", "exceed your remaining movement", "Short or Long Rest"]],
                        ["9dbc574a433a4b9e", ["Hide Armor", "+2 to Dexterity (Acrobatics)", "escape a grapple"]],
                        ["8ec14ff314d86eb6", ["Resistance to Poison", "DC 15 Constitution", "5 Poison damage"]],
                        ["82aa9792b6fd9c06", ["Armor class19", "10 + your Constitution modifier", "Long Rest"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault movement and retaliation armor shows its limits': '''(async () => {
                    const cases = [
                        ["b5f750576f0c162e", ["Leather Armor", "Hide Armor", "15 feet", "unoccupied space"]],
                        ["287096c8ad3294a5", ["Armor class19", "10 damage per instance", "cannot trigger another"]],
                        ["38aa0dc168f1b370", ["Armor class21", "misses you with a melee attack", "equal to your character level"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
                })()''',
                'Adventurer’s Vault reactive armor shows its timing and AC': '''(async () => {
                    const cases = [
                        ["e5244b228b352ee0", ["before the damage is applied", "Armor class20", "Armor class13 + Dex modifier"]],
                        ["db59cd695311078f", ["could legally target", "rerolls the attack", "Armor class21"]],
                        ["cce4b1b7fac85111", ["Intimidation", "−2 penalty", "Short or Long Rest"]],
                        ["b9b38abdcd656689", ["Padded Armor", "Armor class12 + Dex modifier", "solely because of its proximity"]],
                    ];
                    for (const [id, terms] of cases) {
                        inspect("adventurers-vault-1-reference:" + id, grid.firstElementChild);
                        await itemDetails;
                        if (!terms.every(term => inspection.textContent.includes(term))) return false;
                    }
                    return true;
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
                    return ethereal.includes("21 with 6–20 charges") && ethereal.includes("level 7 spell")
                        && cursed.includes("Identify reports that apparent bonus") && cursed.includes("broken suit provides no AC")
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
                'Six merchants expose priced staples, daily finds, and category tabs': '''(async () => {
                    const choose = id => {
                        const picker = byId("merchant-choice");
                        picker.value = id;
                        picker.dispatchEvent(new Event("change"));
                    };
                    const tab = category => byId("merchant-categories").querySelector('[data-category="' + category + '"]');
                    const offers = () => Array.from(byId("merchant-stock").querySelectorAll("button.card"));
                    const offer = slug => offers().find(card => card.dataset.id.endsWith("_" + slug));
                    byId("open-merchants").click();
                    try {
                        for (const [id, slug, copper] of [["bildrath","rope",1000],["budget","dagger",180],
                            ["standard","shield",1000],["premium","plate-armor",187500],
                            ["threshold","spear",100],["vallaki","dagger",300]]) {
                            choose(id);
                            const cards = offers();
                            const core = cards.filter(card => card.dataset.featured === "false");
                            if (core.length !== merchantShops[id].staples.length || core.length < 20 || core.length > 40
                                || Number(offer(slug).dataset.copper) !== copper
                                || byId("merchant-source").hidden !== (id !== "bildrath")) throw new Error(id + " stock/price: " + core.length + ", " + offer(slug).dataset.copper);
                            tab("featured").click();
                            if (tab("featured").getAttribute("aria-pressed") !== "true" ||
                                offers().length < 1 || offers().length > 3 ||
                                offers().some(card => card.dataset.featured !== "true")) throw new Error(id + " daily finds tab");
                            tab("weapon").click();
                            if (id === "bildrath" ? offers().length !== 0 :
                                !offers().length || offers().some(card => card.dataset.category !== "weapon")) throw new Error(id + " weapons tab: " + offers().map(card => card.dataset.id).join(", "));
                            tab("armor").click();
                            if (id === "bildrath" ? offers().length !== 0 :
                                !offer("shield") || offers().some(card => card.dataset.category !== "armor")) throw new Error(id + " armor tab");
                        }
                        choose("bildrath");
                        if (Number(offer("torch").dataset.copper) !== 10
                            || merchantPrice({originalPrices:{test:2500}}, "test", {}) !== null) throw new Error("Merchant scenario failed");
                        offer("rope").click();
                        await itemDetails;
                        if (!inspection.textContent.includes("Shop price · 10 gp")) throw new Error("Inspection shop price");
                        if (!window.closeInspection() || byId("merchants").hidden) throw new Error("Merchant scenario failed");
                        return window.closeInspection() && byId("merchants").hidden && !byId("catalog-shelf").hidden;
                    } finally {
                        closeMerchants();
                    }
                })()''',
                'Merchant surprises resolve and rotate on adjacent device dates': '''(() => {
                    return Object.entries(merchantShops).every(([id, shop]) => {
                        const valid = slug => {
                            const item = JSON.parse(Armory.item("open5e-srd-2024:srd-2024_" + slug));
                            return item.name && merchantPrice(shop, slug, item) > 0;
                        };
                        const stock = shop.staples.concat(shop.surprises);
                        if (new Set(stock).size !== stock.length || !stock.every(valid)) return false;
                        const counts = new Set();
                        for (let offset = 0; offset < 14; offset++) {
                            const first = merchantDailyFinds(id, new Date(2026, 11, 28 + offset, 1));
                            const same = merchantDailyFinds(id, new Date(2026, 11, 28 + offset, 23));
                            const next = merchantDailyFinds(id, new Date(2026, 11, 29 + offset));
                            counts.add(first.length);
                            if (first.join() !== same.join() || first.slice().sort().join() === next.slice().sort().join()
                                || first.some(slug => shop.staples.includes(slug))
                                || new Set(first).size !== first.length) return false;
                        }
                        return [1, 2, 3].every(count => counts.has(count));
                    });
                })()''',
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
                dev.eval('if (typeof armoryQA !== "undefined") armoryQA.restore(); true')
            finally:
                socket.close()
    finally:
        subprocess.run([*adb, 'forward', '--remove', 'tcp:' + port], check=True)
    print(f'{total - len(failures)}/{total} checks passed')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
