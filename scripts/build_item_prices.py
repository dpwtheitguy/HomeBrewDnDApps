#!/usr/bin/env python3
"""Generate the shared price index and verify full catalog coverage."""
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
from item_pricing import price_catalog

CATALOG = ROOT / 'catalog'
with sqlite3.connect(CATALOG / 'indexes/items.sqlite3') as db:
    items = [json.loads(row[0]) for row in db.execute('SELECT data_json FROM items ORDER BY id')]
prices = price_catalog(items)
assert len(prices['records']) == len(items)
for price in prices['records'].values():
    cost, buy, sell = (Decimal(price[field]) for field in ('base_cost_gp', 'base_buy_gp', 'base_sell_gp'))
    assert buy >= cost >= sell > 0, price
(CATALOG / 'supplements/item-prices.json').write_text(
    json.dumps(prices, ensure_ascii=False, separators=(',', ':')) + '\n')
lines = ['# Item price coverage', '', f'**{len(items):,} of {len(items):,}** catalog records have a positive base cost, buy price, and sell price.',
         '', '| Pricing basis | Records |', '|---|---:|']
for key, count in sorted(prices['counts'].items(), key=lambda pair: -pair[1]):
    lines.append(f'| {prices["method_labels"][key]} | {count:,} |')
if prices['decoration_counts']:
    lines += ['', '## Cosmetic premiums', '', '| Price adjustment | Records |', '|---|---:|']
    for label, count in sorted(prices['decoration_counts'].items(), key=lambda pair: -pair[1]):
        lines.append(f'| {label} | {count:,} |')
    lines += ['', 'Published and already recorded item prices are preserved. Percentage premiums apply to '
              'the physical equipment value. The historical masterwork benchmark affects price only in this appraisal.']
lines += ['', 'Original prices and currencies remain in each record’s provenance. The price supplement supplies a market reference '
          'with its own economy, basis, and unit scope. Category and cross-edition comparisons are estimates.',
          '', 'Neutral merchandise quotes use +0 Persuasion, neutral attitude, and Balanced pricing. '
          'Explicit source resale amounts are retained as sell benchmarks. Construction quotes are independent appraisals. '
          'Coin display rounds to copper with a one-copper minimum. Story items, artifacts, and fixed installations have indicative numbers for DM use.',
          '', '[2024 equipment list](https://www.dndbeyond.com/sources/dnd/br-2024/equipment) · '
          '[2024 magic item value guidelines](https://www.dndbeyond.com/sources/dnd/br-2024/magic-items#MagicItemValuesbyRarity) · '
          '[BG3 trading formula](https://bg3.wiki/wiki/Trading_and_item_pricing)', '']
(CATALOG / 'reports/ITEM-PRICE-COVERAGE.md').write_text('\n'.join(lines))
print(f'Priced all {len(items):,} records. {prices["counts"]}')
