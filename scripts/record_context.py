"""Universal, reproducible source context and explicit applied-change ledger.
This describes the current projection. Historical editorial events remain separate.
"""
import hashlib,json
from functools import lru_cache

@lru_cache(maxsize=None)
def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def attach_context(item, source, root, events=()):
    provenance=item['provenance'];refs=[];seen=set()
    def add(url,kind,label=None,**extra):
        if not url:return
        key=(url,kind,json.dumps(extra.get('locator'),sort_keys=True) if kind=='reported-item-appearance' else None)
        if key in seen:return
        seen.add(key);refs.append({'url':url,'kind':kind,'label':label,**extra})
    add(provenance.get('permanent_url') or provenance.get('source_url'),'source-record',provenance.get('provider'),
        file_sha256=provenance.get('source_file_sha256'),retrieved_at=provenance.get('retrieved_at'),revision=provenance.get('revision_id') or provenance.get('upstream_commit'),revision_timestamp=provenance.get('revision_timestamp'))
    evidence=provenance.get('evidence') or {}
    add(evidence.get('url'),'research-evidence',evidence.get('label') or evidence.get('title'),evidence_kind=evidence.get('source_kind') or evidence.get('kind'),
        author=evidence.get('author'),reported_edition=evidence.get('edition'),locator=provenance.get('locator'),verification_note=evidence.get('note'))
    def snapshot(p,kind):
        rel=p.get('file');commit=p.get('repository_commit')
        if rel and commit:
            upstream='https://github.com/open5e/open5e-api/blob/'+commit+'/'+rel.replace('raw/open5e/','data/')
            add(upstream,kind,'Pinned Open5e fixture',upstream_id=p.get('upstream_pk'),revision=commit,local_file='catalog/'+rel,
                file_sha256=file_hash(root/'catalog'/rel))
    snapshot(provenance,'source-fixture');snapshot(provenance.get('base_rules_provenance') or {},'base-rules-fixture')
    add(source.get('source_url'),'source-manifest',source.get('name'),coverage=source.get('coverage'))
    for association in item.get('associations',[]):
        ev=association.get('evidence') or {}
        add(ev.get('url') or ev.get('source_url'),'association-evidence',association['entity_id'],evidence_status=association.get('status'))
    for evidence in provenance.get('additional_sources', []):
        add(evidence['url'], 'reported-item-appearance', evidence_kind=evidence['kind'],
            locator=evidence['locator'], verification_note=evidence.get('note'))
    for appearance in item.get('mechanics',{}).get('reference_metadata',{}).get('attested_appearances',[]):
        add(appearance.get('url'),'reported-item-appearance',appearance.get('npc'),
            reported_book=appearance.get('reported_book'),reported_page=appearance.get('reported_page'),
            locator=appearance.get('locator'),file_sha256=appearance.get('pdf_sha256'),
            source_rules_basis=appearance.get('source_rules_basis'),reported_source_cost=appearance.get('reported_source_cost'),
            original_page_verified=False)
    verifications=item.get('source_verifications',[])
    for v in verifications:
        add(v['url'],'user-provided-original-page',v['book_code'],local_file=v['local_file'],file_sha256=v['file_sha256'],locator=v['locator'],verified_fields=v['verified_fields'],verification_scope=v['verification_scope'])
    if provenance.get('local_file'):
        add(provenance['source_url'],'user-provided-original-page','User-provided PDF',local_file=provenance['local_file'],file_sha256=provenance.get('source_file_sha256'),locator=provenance.get('locator'),verified_fields=provenance.get('verified_fields',[]),verification_scope=provenance.get('verification_scope'))
    changes=[]
    def change(kind,description,field=None,semantic=False,**extra):
        key=item['id']+'|'+kind+'|'+description
        changes.append({'id':hashlib.sha256(key.encode()).hexdigest()[:16],'kind':kind,'field':field,'description':description,'changes_gameplay':semantic,**extra})
    change('normalization','Assigned a stable catalog ID, search name, common type and tags; source edition and status remain explicit.','id/name_key/type/tags')
    change('generic-art','Assigned the credited reusable type icon. No source-game or sourcebook artwork binary is included.','image')
    if item['content_status']=='factual-metadata-only':
        change('metadata-projection','Imported a whitelisted reference projection. Full source descriptions, flavor and unlisted mechanics were not imported; this is not an executable 2024 rules conversion.','description/mechanics')
    else:
        change('source-preservation','Original fixture or research evidence remains separately identified. The record is not a line-by-line rules verification against the original publication.','provenance')
    for verification in verifications:
        change('original-page-verification',verification['note'],'source_verifications/mechanics.verified_legacy_facts',False,source_file_sha256=verification['file_sha256'],verified_fields=verification['verified_fields'])
    conversion=item.get('conversion') or {}
    if conversion:
        kind=conversion.get('kind') or conversion.get('conversion_kind') or 'draft-reskin'
        desc=conversion.get('changes') or conversion.get('conversion_note')
        if desc:change('rules-adaptation',desc,'description/mechanics',True,adaptation_kind=kind)
        else:change('rules-reskin','Uses the explicitly linked 2024 base profile. Legacy mechanics and special bonuses were not imported; no additional power is implied by the regional name.','mechanics',True,adaptation_kind=kind)
        if item.get('base_item_id'):change('base-rules-link','Linked the selected SRD equipment profile and retained its training interactions; this is an editorial equivalence rather than a claim of identical legacy behavior.','base_item_id/access',True,base_item_id=item['base_item_id'])
        if item.get('presentation',{}).get('flavor'):change('original-flavor','Added project-authored flavor; it is not a quotation or a claim of canonical item lore.','presentation.flavor')
        if item.get('presentation',{}).get('creative_use',{}).get('text'):change('creative-suggestion','Added a project-authored creative-use suggestion. Its DM-ruling flag is explicit.','presentation.creative_use')
    statuses={v['status'] for v in item.get('valuation',{}).get('base_values',[])}
    if 'author-estimate' in statuses:change('price-estimate','Assigned an explicit project price estimate, not a source-book price or guaranteed sale price.','valuation',True)
    elif statuses:change('value-normalization','Parsed a positive numeric source/base value into its named economy. BG3-style quotes, when present, are optional contextual estimates.','valuation')
    else:change('unknown-value','No supported numeric value was assigned. Missing or placeholder-zero values are not treated as free.','valuation')
    if item.get('record_kind') in ('structure','construction-component'):
        change('construction-policy','Separated installed construction from portable gear; merchant Charisma multipliers do not automatically price land, labor or upkeep.','record_kind/structure/valuation',True)
    if item.get('associations'):change('associations','Attached setting, publication, game or cultural facets with per-association evidence/status. Associations do not grant ancestry, alignment, class access or proficiency.','associations')
    event_refs=[]
    for event in events:
        if item['id'] in event.get('item_ids',[]):
            event_refs.append(event['id']);change('editorial-correction',event['description'],event.get('field'),True,event_id=event['id'])
    fingerprint=hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    item['research_metadata']={'schema_version':1,'source_manifest_id':item['source_id'],'source_refs':refs,
        'resource_ids':item.get('resource_ids',[]),'reported_ruleset':item['ruleset'],'original_publication_verified':provenance.get('original_publication_verified',False),
        'source_page_verified':provenance.get('legacy_page_verified',False),'verification_scope':provenance.get('verification_scope'),'verified_fields':provenance.get('verified_fields',[]),
        'verification_status':item['tabletop_status'],'change_log':changes,'editorial_event_ids':event_refs,
        'record_content_sha256':fingerprint,'pipeline_version':'catalog-context-1.0.0',
        'history_note':'Change log describes transformations applied to this snapshot, not a fabricated chronological source diff. Historical editorial events are kept in catalog/changes/editorial-events.json.'}
    return item
