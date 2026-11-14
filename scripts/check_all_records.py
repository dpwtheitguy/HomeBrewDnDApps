#!/usr/bin/env python3
"""Audit a packaged release and optionally capture every Android item card."""
import argparse
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

from audit_armory_release_db import audit

ROOT = Path(__file__).resolve().parents[1]


def capture(serial, inventory, output, screenshot_count=0, packaged_rules=None):
    spec = importlib.util.spec_from_file_location(
        'armory_filter_matrix', ROOT / 'apps/arms-and-equipment/tests/filter_matrix.py')
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    adb = ['adb', '-s', serial]
    pid = subprocess.check_output(adb + ['shell', 'pidof', qa.PACKAGE], text=True).strip()
    port = subprocess.check_output(adb + ['forward', 'tcp:0', f'localabstract:webview_devtools_remote_{pid}'],
                                   text=True).strip()
    try:
        with urlopen(f'http://127.0.0.1:{port}/json', timeout=10) as response:
            page = json.load(response)[0]
        ws = qa.create_connection(page['webSocketDebuggerUrl'], suppress_origin=True, timeout=15)
        try:
            dev = qa.DevTools(ws)
            viewport = dev.eval('({release:JSON.parse(Armory.metadata()).manifest.content_version,width:innerWidth,height:innerHeight})')
            if viewport['release'] != inventory['release']:
                raise ValueError(f'Installed release differs: {viewport}')
            dev.eval("""new Promise((resolve, reject) => {
                const deadline = Date.now() + 8000;
                const check = () => {
                    if (typeof byId === 'function' && typeof receiveSearch === 'function' &&
                        document.getElementById('search')) {
                        resolve(true);
                    } else if (Date.now() > deadline) {
                        reject(Error('Armory search did not initialize'));
                    } else {
                        setTimeout(check, 50);
                    }
                };
                check();
            })""")
            dev.eval(qa.SETUP)
            failures = 0
            records = inventory['records']
            # Spread captures across the sorted inventory while the intended card is open.
            screenshot_count = min(screenshot_count, len(records))
            screenshot_indices = {
                index * (len(records) - 1) // max(1, screenshot_count - 1)
                for index in range(screenshot_count)
            }
            screenshots = output.parent / 'screenshots'
            if screenshot_indices:
                screenshots.mkdir(exist_ok=True)
            try:
                with output.open('w', encoding='utf-8', buffering=1) as out:
                    print(json.dumps(viewport), file=out)
                    for index, item in enumerate(records):
                        options = {'term': item['name'], 'facets': {'scope': 'exact'}}
                        dev.eval('armoryQA.run(' + json.dumps(options) + ')')
                        result = dev.result()
                        expected = json.dumps(item['id'])
                        fields = json.dumps((packaged_rules or {}).get(item['id'], {}))
                        screen = dev.eval('''(async () => {
                            const id = ''' + expected + ''';
                            const fields = ''' + fields + ''';
                            const card = Array.from(grid.querySelectorAll("[data-id]")).find(node => node.dataset.id === id);
                            if (!card) return null;
                            card.click();
                            await itemDetails;
                            const rules = Array.from(inspection.querySelectorAll("details")).find(
                                details => details.firstElementChild.textContent === "Baldur’s Gate 3 rules");
                            const rendered = new Map(Array.from(rules ? rules.querySelectorAll("dt") : [], label => [
                                label.textContent, label.nextElementSibling.textContent
                            ]));
                            return {id: selected, title: inspection.querySelector("h2").textContent,
                                text: inspection.innerText, overflow: inspection.scrollWidth - inspection.clientWidth,
                                mismatchedRules: Object.entries(fields).filter(([label, value]) =>
                                    rendered.get(label) !== feetText(value)).map(([label]) => label),
                                links: Array.from(inspection.querySelectorAll("a"), a => a.href)};
                        })()''')
                        ok = screen and screen['id'] == item['id'] and screen['title'] == item['name']
                        failures += not ok
                        print(json.dumps({'expected': item['id'], 'name': item['name'],
                                          'matches': result['total'], 'screen': screen},
                                         ensure_ascii=False), file=out)
                        if ok and index in screenshot_indices:
                            dev.eval('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                            file_id = re.sub(r'[^a-zA-Z0-9-]', '-', item['id'])
                            image = subprocess.check_output(adb + ['exec-out', 'screencap', '-p'])
                            (screenshots / f'{serial}-{file_id}.png').write_bytes(image)
                        dev.eval('dismissInspection(false)')
            finally:
                dev.eval('armoryQA.restore();true')
        finally:
            ws.close()
    finally:
        subprocess.run(adb + ['forward', '--remove', 'tcp:' + port], check=True)
    return failures


def check_visual(path, records):
    expected = {row['id'] for row in records}
    with path.open(encoding='utf-8') as stream:
        viewport = json.loads(next(stream))
        rows = [json.loads(line) for line in stream]
    actual = {row['expected'] for row in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError('Android capture does not cover the release inventory exactly once')
    findings = []
    for row in rows:
        screen = row['screen']
        if not screen:
            continue
        markup = re.findall(r'\\[*_]|\*\*|\{\{', screen['text'])
        # The metadata line sits immediately after the title, before the rules.
        lines = [line for line in screen['text'].splitlines() if line.strip()]
        title_index = lines.index(screen['title']) if screen['title'] in lines else -1
        if 0 <= title_index < len(lines) - 1:
            metadata = lines[title_index + 1].split(' · ')
            if len(metadata) == 3 and '*' in metadata[1]:
                markup.append(f'Rarity annotation: {metadata[1]}')
        if screen['overflow'] > 0 or markup:
            findings.append({'id': row['expected'], 'name': row['name'],
                             'overflow': screen['overflow'], 'markup': markup})
    return {'viewport': viewport, 'checked': len(rows), 'findings': findings}


def check_bg3_panels(path, links_by_id, assertions):
    findings = []
    checked = 0
    with path.open(encoding='utf-8') as stream:
        next(stream)
        for line in stream:
            row = json.loads(line)
            item_id = row['expected']
            if item_id not in links_by_id:
                continue
            checked += 1
            screen = row['screen'] or {'text': '', 'links': []}
            text = screen['text']
            missing = set(links_by_id[item_id]) - set(screen['links'])
            if 'Baldur’s Gate 3 rules' not in text or missing:
                findings.append({'id': item_id, 'issue': 'Missing native rules panel or pinned links',
                                 'missing_links': sorted(missing)})
            for label in screen.get('mismatchedRules', []):
                findings.append({'id': item_id, 'issue': f'{label} differs from the packaged rule'})
            for label, patterns in assertions.get(item_id, {}).items():
                visible = text if label == 'Summary' else '\n'.join(
                    re.findall(r'^' + re.escape(label) + r'\n([^\n]+)', text, re.MULTILINE))
                for pattern in patterns:
                    if not re.search(pattern, visible, re.IGNORECASE):
                        findings.append({'id': item_id, 'issue': f'{label} lacks {pattern}'})
    return {'checked': checked, 'findings': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serial')
    parser.add_argument('--screenshots', type=int, default=0,
                        help='Capture this many representative inspected cards per device')
    parser.add_argument('--batch-inventory', type=Path,
                        help='Limit the report and Android capture to imported IDs in this batch')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = audit(args.archive, args.apk)
    if args.batch_inventory:
        batch = json.loads(args.batch_inventory.read_text(encoding='utf-8'))
        requested = {row['id'] for row in batch['candidates'] if row['status'] == 'imported'}
        excluded = {row['id'] for row in batch['candidates'] if row['status'] == 'excluded'}
        exposed = excluded.intersection(row['id'] for row in inventory['records'])
        if exposed:
            inventory['global_issues'].append(f'Excluded batch IDs shipped: {sorted(exposed)}')
        inventory['records'] = [row for row in inventory['records'] if row['id'] in requested]
        if {row['id'] for row in inventory['records']} != requested or not requested:
            parser.error('Batch contains no imported IDs or an imported ID is absent from the release')
        inventory['scope'] = batch.get('letters') or [batch['prefix']]
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=args.output, delete=False) as temp:
        json.dump(inventory, temp, ensure_ascii=False, indent=2)
        temp.write('\n')
    Path(temp.name).replace(args.output / 'database.json')
    failed = bool(inventory['global_issues'] or any(row['issues'] for row in inventory['records']))
    print(f"{inventory['release']}: {len(inventory['records'])} records, database {'findings' if failed else 'pass'}")
    if args.serial:
        capture_path = args.output / f'{args.serial}.jsonl'
        with ZipFile(args.archive) as archive:
            member = 'catalog/supplements/curated-item-details.json'
            details = json.loads(archive.read(member)) if member in archive.namelist() else {'records': {}}
        rules = {item_id: row['fields'] for item_id, rows in details['records'].items()
                 for row in rows if row['status'] == 'reviewed-bg3-rules'}
        failures = capture(args.serial, inventory, capture_path, args.screenshots, rules)
        visual = check_visual(capture_path, inventory['records'])
        (args.output / f'{args.serial}-visual.json').write_text(json.dumps(visual, indent=2) + '\n')
        assertions = json.loads((ROOT / 'scripts/bg3_rule_assertions.json').read_text())
        gameplay = check_bg3_panels(capture_path, {row['id']: row['pinned_links']
                                                 for row in inventory['records'] if 'pinned_links' in row},
                                    assertions)
        (args.output / f'{args.serial}-bg3.json').write_text(json.dumps(gameplay, indent=2) + '\n')
        print(f"Visual candidates: {len(visual['findings'])}")
        print(f"BG3 panel candidates: {len(gameplay['findings'])}")
        print(f'Android navigation failures: {failures}')
        failed |= bool(failures or visual['findings'] or gameplay['findings'])
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
