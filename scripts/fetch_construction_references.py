#!/usr/bin/env python3
"""Public construction-name references only; no models, art or source mechanics."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,record,save,clean
BASE='https://valheim.gaming.tools/structures/'
rows=[]
for category in ['building','stone_building','furniture','crafting','miscellaneous']:
    url=BASE+category;tree=fetch(url)
    for a in tree.xpath('//a[@href]'):
        name=a.xpath('.//span[contains(@class,"font-bold")]')
        href=a.get('href','')
        if name and '../structures/' in href:
            import urllib.parse
            rows.append(record(clean(name[0].text_content()),'construction-component',urllib.parse.urljoin(url,href),record_kind='construction-component',evidence_kind='fan-build-menu-index',source_category=category,ninja_relevance='backlog',upstream_ids=[href.rsplit('/',1)[-1]]))
save('valheim-construction-reference',rows,game_id='valheim',source_url=BASE,coverage='First public listing segment of five building categories. Same-name components collapse variant IDs. Partial snapshot only; not every piece, DLC, recipe or current patch. Material quantities and game build physics are not converted to D&D.')
