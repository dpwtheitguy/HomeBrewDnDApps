#!/usr/bin/env python3
"""Discover public item-source leads; neither crawl completion nor item import is inferred."""
import collections,datetime,json,sys,urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_ninja_references import fetch,clean
ROOT=Path(__file__).resolve().parents[1];url='https://pandius.com/items.html';tree=fetch(url)
exclude={'/index.html','/authors.html','/atlas.html','/rules.html','/resource.html','/adv_camp.html','/stories.html','/mystfaq.html','/search.html','/links.html','/items.html','/threshold.html','/TomeOfMystara.html'};rows={}
for a in tree.xpath('//a[@href]'):
 target=urllib.parse.urljoin(url,a.get('href'));p=urllib.parse.urlsplit(target);title=clean(a.text_content())
 if p.hostname not in ['pandius.com','www.pandius.com'] or not title or p.path in exclude:continue
 if a.xpath('ancestor::h1|ancestor::h2|ancestor::h3'):continue
 authors=[]
 for sibling in a.itersiblings():
  if sibling.tag=='br':break
  if sibling.tag=='a' and 'authors.html' in sibling.get('href',''):authors.append(clean(sibling.text_content()))
 section=a.xpath('preceding::h1[1]');category=a.xpath('preceding::h2[1]')
 if target not in rows:rows[target]={'url':target,'labels':[],'credited_authors':[],'index_sections':[],'status':'discovered-source-lead-not-item-import','originating_index':url}
 row=rows[target];row['labels']=sorted(set(row['labels'])|{title});row['credited_authors']=sorted(set(row['credited_authors'])|set(authors));label=' / '.join(clean(x.text_content()) for x in [*(section or []),*(category or [])])
 if label and label not in row['index_sections']:row['index_sections'].append(label)
paths={urllib.parse.urlsplit(r['url']).path for r in rows.values()}
d={'discovered_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'index_url':url,'discovered_source_links':len(rows),'distinct_document_paths':len(paths),'item_records_added':0,'scope':'One-hop discovery from the central public Items index. Linked page titles can describe collections, rules or discussions, not individual items. Not a site-wide crawl, verified content import or full sourcebook audit.','sources':sorted(rows.values(),key=lambda r:r['url'])}
p=ROOT/'catalog/research/pandius-item-discovery.json';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('Pandius item-index source links:',len(rows),'distinct document paths:',len(paths))
for r in d['sources']:
 if any('BECMI Index' in title for title in r['labels']):print(r['labels'],r['url'])
