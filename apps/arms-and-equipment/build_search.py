"""Prepare app-specific search indexes from the verified shared catalog."""

import json
import sqlite3
import unicodedata
from decimal import Decimal
from pathlib import Path


def title_initial(name):
    text = unicodedata.normalize('NFKD', name).casefold()
    initial = next((character for character in text if character.isalnum()), '')
    return initial if 'a' <= initial <= 'z' else '#'


def proficiency_profiles(item, base):
    if item['ruleset'] != 'dnd-2024':
        return []
    grants = {
        option
        for record in (item, base)
        for interaction in record.get('access', {}).get('proficiency_interactions', [])
        for option in interaction.get('any_of', [])
    }
    tags = set(item.get('tags', [])) | set(base.get('tags', []))
    profiles = []
    if (
        grants.intersection({'weapon-category:simple', 'armor:light'})
        or ('weapon-category:martial' in grants and tags.intersection({'property:finesse', 'property:light'}))
        or item['id'] == "open5e-srd-2024:srd-2024_thieves-tools"
    ):
        profiles.append('rogue-2024')
    if item['type'] in {'armor', 'shield'} or grants.intersection({
        'weapon-category:simple', 'weapon-category:martial', 'armor:light',
        'armor:medium', 'armor:heavy', 'shield',
    }):
        profiles.append('fighter-2024')
    return profiles


def prepare(path: Path, price_index):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE VIRTUAL TABLE android_search USING fts4(id, name, tags, description, notindexed=id, tokenize=unicode61);
            INSERT INTO android_search SELECT id, name, tags, description FROM item_search;
            DROP TABLE item_search;
            ALTER TABLE android_search RENAME TO item_search;
            CREATE TABLE item_proficiencies (profile TEXT, item_id TEXT, PRIMARY KEY(profile,item_id));
            CREATE TABLE item_cards AS
                SELECT id, name, name_key, source_id, ruleset, type, rarity, image_path,
                    lower(replace(trim(rarity), ' ', '-')) AS rarity_key,
                    '' AS name_initial, 0 AS price_copper, 0 AS buy_copper,
                    CASE WHEN ruleset='dnd-2024' THEN 0 ELSE 1 END AS edition_rank
                FROM items;
            CREATE UNIQUE INDEX item_cards_id ON item_cards(id);
            CREATE INDEX item_cards_name ON item_cards(name_key,id);
            CREATE INDEX item_cards_exact_name ON item_cards(name COLLATE NOCASE);
            CREATE INDEX item_cards_browse ON item_cards(edition_rank,name_key,id);
            CREATE TABLE item_prices (item_id TEXT PRIMARY KEY, price_json TEXT NOT NULL);
        """)
        rows = {
            item_id: json.loads(data)
            for item_id, data in db.execute("SELECT id,data_json FROM items WHERE ruleset='dnd-2024'")
        }
        db.executemany('INSERT INTO item_proficiencies VALUES (?,?)', (
            (profile, item_id)
            for item_id, item in rows.items()
            for profile in proficiency_profiles(item, rows.get(item.get('base_item_id'), {}))
        ))
        item_ids = {item_id for (item_id,) in db.execute('SELECT id FROM items')}
        prices = price_index['records']
        if prices.keys() != item_ids:
            raise ValueError('Price index and catalog contain different item IDs')
        labels = price_index['method_labels']
        db.executemany('INSERT INTO item_prices VALUES (?,?)', (
            (item_id, json.dumps({**price, 'method_label': labels[price['method']]}, ensure_ascii=False))
            for item_id, price in prices.items()
        ))
        db.executemany('UPDATE item_cards SET name_initial=?, price_copper=?, buy_copper=? WHERE id=?', (
            (title_initial(name), int(Decimal(prices[item_id]['base_cost_gp']) * 100),
             int(Decimal(prices[item_id]['base_buy_gp']) * 100), item_id)
            for item_id, name in db.execute('SELECT id,name FROM items')
        ))
        db.executescript("""
            CREATE INDEX item_cards_initial ON item_cards(name_initial,name_key,id);
            CREATE INDEX item_cards_price ON item_cards(price_copper,name_key,id);
            CREATE INDEX item_cards_buy_price ON item_cards(buy_copper);
        """)
        db.commit()
        db.execute('VACUUM')
