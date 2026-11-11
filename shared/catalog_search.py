"""Composable SQLite search with named profiles, typed aliases and relation facets."""
import json
from pathlib import Path
from catalog_taxonomy import Taxonomy

def search(db,catalog_dir,query='',profile='all-research',rulesets=None,sources=None,types=None,tags=None,
           settings=None,regions=None,cultures=None,origins=None,relationship=None,include_unattributed=False,
           sort='name',limit=20,rarities=None,magic=None,attunement=None,min_value=None,max_value=None,value_economy=None,peoples=None,resources=None):
    root=Path(catalog_dir);tx=Taxonomy(root/'taxonomy/entities.json')
    profiles={p['id']:p['filters'] for p in json.loads((root/'filters/presets.json').read_text())['profiles']}
    if profile not in profiles: raise ValueError('Unknown saved profile: '+profile)
    defaults=profiles[profile]
    rulesets=rulesets if rulesets is not None else defaults.get('rulesets')
    settings=settings if settings is not None else defaults.get('settings')
    sources=sources if sources is not None else defaults.get('sources')
    tags=tags if tags is not None else defaults.get('tags')
    clauses=[];params=[];join=''
    if query.strip():
        join=' JOIN item_search ON item_search.id=i.id'
        # Prefix matching without treating user input as executable FTS syntax.
        clauses.append('item_search MATCH ?')
        params.append(' AND '.join('"'+w.replace('"','""')+'"*' for w in query.split()))
    for col,values in [('ruleset',rulesets),('source_id',sources),('type',types)]:
        if values:clauses.append(f'i.{col} IN ('+','.join('?' for _ in values)+')');params.extend(values)
    if rarities:
        values=[r.casefold().replace('-',' ') for r in rarities]
        clauses.append("replace(lower(i.rarity),'-',' ') IN ("+','.join('?' for _ in values)+')');params.extend(values)
    for field,mode in [('magic',magic),('requires_attunement',attunement)]:
        if mode in (None,'any'):continue
        expr="json_extract(i.data_json,'$."+field+"')"
        if mode=='unknown':clauses.append(expr+' IS NULL')
        elif mode in ('yes','no'):clauses.append(expr+' = ?');params.append(1 if mode=='yes' else 0)
        else:raise ValueError('Boolean facet must be any, yes, no or unknown')
    if min_value is not None or max_value is not None or sort=='value':
        if not value_economy:raise ValueError('Choose --value-economy before comparing prices from different source economies')
        import math
        lo=float(min_value) if min_value is not None else None;hi=float(max_value) if max_value is not None else None
        if any(v is not None and (not math.isfinite(v) or v<0) for v in (lo,hi)):raise ValueError('Price bounds must be finite and nonnegative')
        if lo is not None and hi is not None and lo>hi:raise ValueError('Minimum value exceeds maximum value')
        clauses.append("json_extract(i.data_json,'$.valuation.base_values[0].economy_id') = ?");params.append(value_economy)
        value_expr="CAST(json_extract(i.data_json,'$.valuation.base_values[0].amount_gp') AS REAL)"
        if lo is not None:clauses.append(value_expr+' >= ?');params.append(lo)
        if hi is not None:clauses.append(value_expr+' <= ?');params.append(hi)
    if resources:
        registry={r['id']:r for r in json.loads((root/'resources/requested-resources.json').read_text())['resources']}
        from catalog_taxonomy import key
        selected=set()
        def descend(rid):
            if rid in selected:return
            selected.add(rid)
            for child in registry[rid]['child_resource_ids']:descend(child)
        for value in resources:
            hits=[r['id'] for r in registry.values() if key(value) in {key(r['id']),key(r['label']),*(key(a) for a in r['aliases'])}]
            if len(hits)!=1:raise ValueError('Unknown or ambiguous resource: '+value)
            descend(hits[0])
        clauses.append("EXISTS(SELECT 1 FROM resource_items ri WHERE ri.item_id=i.id AND ri.basis!='regional-context-only' AND ri.resource_id IN ("+','.join('?' for _ in selected)+'))')
        params.extend(sorted(selected))
    excluded=defaults.get('exclude_content_statuses',[])
    if excluded:
        clauses.append("json_extract(i.data_json,'$.content_status') NOT IN ("+','.join('?' for _ in excluded)+')');params.extend(excluded)
    for tag in tags or []:
        clauses.append('EXISTS(SELECT 1 FROM tags t WHERE t.item_id=i.id AND t.tag=?)');params.append(tag)
    if relationship and relationship not in ('setting','cultural-association','origin','available-in','used-by','found-in','inspired-by'):raise ValueError('Unknown association role')
    for values,kind in [(settings,'setting'),(regions,'region'),(cultures,'culture'),(origins,None),(peoples,'people')]:
        if not values:continue
        ids=set()
        for value in values:ids|=tx.descendants(tx.resolve(value,kind))
        # Settings compare only setting assertions. Other facets default to origin/cultural association.
        roles=['setting'] if kind=='setting' else [relationship] if relationship else ['origin','cultural-association','found-in']+(['used-by'] if kind=='people' else [])
        entity_sql=','.join('?' for _ in ids);role_sql=','.join('?' for _ in roles)
        clause=f'EXISTS(SELECT 1 FROM associations a WHERE a.item_id=i.id AND a.entity_id IN ({entity_sql}) AND a.role IN ({role_sql}))'
        params.extend(sorted(ids));params.extend(roles)
        if include_unattributed:
            unknown="NOT EXISTS(SELECT 1 FROM associations u WHERE u.item_id=i.id AND u.entity_id LIKE ? AND u.role IN ("+role_sql+'))'
            params.append((kind+':%') if kind else '%');params.extend(roles)
            clause='('+clause+' OR '+unknown+')'
        clauses.append(clause)
    orders={'name':'i.name COLLATE NOCASE,i.ruleset,i.id','rarity':'CASE lower(i.rarity) WHEN \'common\' THEN 1 WHEN \'uncommon\' THEN 2 WHEN \'rare\' THEN 3 WHEN \'very rare\' THEN 4 WHEN \'very-rare\' THEN 4 WHEN \'legendary\' THEN 5 WHEN \'artifact\' THEN 6 ELSE 7 END,i.name COLLATE NOCASE',
            'value':"CAST(json_extract(i.data_json,'$.valuation.base_values[0].amount_gp') AS REAL),i.name COLLATE NOCASE",
            'relevance':'bm25(item_search),i.name COLLATE NOCASE' if join else 'i.name COLLATE NOCASE'}
    if sort not in orders:raise ValueError('Unknown sort order')
    sql='SELECT i.* FROM items i'+join+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY '+orders[sort]+' LIMIT ?'
    return db.execute(sql,params+[max(1,min(limit,1000))]).fetchall()
