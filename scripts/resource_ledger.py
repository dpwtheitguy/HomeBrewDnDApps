"""Compile source coverage without equating registration, context and item audits."""
import collections,json,re
from pathlib import Path

def compile_resources(items,root):
    path=root/'catalog/resources/requested-resources.json'
    if not path.exists():return [],[]
    rows=json.loads(path.read_text())['resources'];links=[];byid={r['id']:r for r in rows};per_item=collections.defaultdict(set)
    for resource in rows:
        selectors=resource['selectors'];contexts=0;direct=0;drafts=0
        codes=selectors.get('reported_book_codes',[])
        for item in items:
            basis=None;assoc={a['entity_id'] for a in item.get('associations',[])}
            hit=assoc.intersection(selectors.get('entity_ids',[]))
            if hit:basis='regional-context-only' if resource['kind']=='publication' and all(e.startswith('region:') for e in hit) else 'association-or-inspiration'
            if item['source_id'] in selectors.get('source_ids',[]):basis='source-pack'
            if item['provenance'].get('local_file') in selectors.get('local_files',[]):basis='local-source-file'
            reported=' '.join([str(item['provenance'].get('reported_legacy_book') or item.get('conversion',{}).get('reported_book') or ''),*item['mechanics'].get('reference_metadata',{}).get('reported_book_codes',[])])
            if any(re.search(r'(?<![A-Za-z0-9])'+re.escape(c)+r'(?![A-Za-z0-9])',reported,re.I) for c in codes):basis='reported-book-code-unverified'
            if basis:
                contexts+=basis=='regional-context-only';direct+=basis!='regional-context-only'
                drafts+=basis!='regional-context-only' and item['content_status']=='original-conversion-draft'
                links.append({'item_id':item['id'],'resource_id':resource['id'],'basis':basis,'verification':'not-an-original-book-audit'})
                per_item[item['id']].add(resource['id'])
        resource['direct_or_inspired_records']=direct;resource['context_only_records']=contexts;resource['draft_records']=drafts
        resource['coverage_status']='selected-drafts-and-or-references' if direct else 'related-regional-context-only' if contexts else 'registered-item-audit-pending'
    # A parent series links its children’s records without creating more item definitions.
    def descendants(rid,trail=()):
        if rid in trail:raise ValueError('Resource cycle: '+rid)
        if rid not in byid:raise ValueError('Unknown child resource: '+rid)
        result={rid}
        for child in byid[rid]['child_resource_ids']:result|=descendants(child,trail+(rid,))
        return result
    for resource in rows:
        children=descendants(resource['id'])-{resource['id']}
        resource['enumerated_child_resources']=len(children)
        childlinks=[x for x in links if x['resource_id'] in children and x['basis']!='regional-context-only']
        resource['child_record_union_count']=len({x['item_id'] for x in childlinks})
        if resource['child_resource_ids']:
            resource['children_without_direct_item_links']=[r for r in sorted(children) if not byid[r]['direct_or_inspired_records']]
            resource['coverage_status']='series-partial' if childlinks else 'series-registered-audits-pending'
    for item in items:item['resource_ids']=sorted(per_item[item['id']])
    return rows,links

def write_resource_tables(db,rows,links):
    db.executescript('''CREATE TABLE resources(id TEXT PRIMARY KEY,label TEXT,kind TEXT,coverage_status TEXT,data_json TEXT);
    CREATE TABLE resource_items(item_id TEXT REFERENCES items(id),resource_id TEXT REFERENCES resources(id),basis TEXT,verification TEXT,PRIMARY KEY(item_id,resource_id));
    CREATE INDEX resource_items_source ON resource_items(resource_id,item_id);''')
    db.executemany('INSERT INTO resources VALUES(?,?,?,?,?)',[(r['id'],r['label'],r['kind'],r['coverage_status'],json.dumps(r,ensure_ascii=False)) for r in rows])
    db.executemany('INSERT INTO resource_items VALUES(?,?,?,?)',[(r['item_id'],r['resource_id'],r['basis'],r['verification']) for r in links])

def save_resource_report(rows,root):
    folder=root/'catalog/reports';summary={'registered_resources':len(rows),'original_item_audits_completed':sum(r['original_item_audit_status']=='complete' for r in rows),'by_coverage_status':dict(collections.Counter(r['coverage_status'] for r in rows)),'resources':rows}
    (folder/'resource-coverage.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines=['# Requested-source coverage','','Registration is not item-audit completion. Contextual regional gear is separate from a direct source/inspiration link.','','| Resource | Coverage | Direct/inspired records | Context only | Original audit |','|---|---|---:|---:|---|']
    lines += [f"| {r['label']} | {r['coverage_status']} | {r['direct_or_inspired_records']} | {r['context_only_records']} | {r['original_item_audit_status']} |" for r in rows]
    lines += ['', 'Series/category rows do not generate additional item definitions. Bibliography and unsupported title matches do not establish exhaustive item coverage. Open media/source categories cannot be certified complete from a finite list.']
    (folder/'RESOURCE-COVERAGE.md').write_text('\n'.join(lines)+'\n')
