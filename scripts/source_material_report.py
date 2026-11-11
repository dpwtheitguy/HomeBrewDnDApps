#!/usr/bin/env python3
"""Reproducible source-pack charts and separate non-additive book coverage ledger."""
import collections,csv,html,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=ROOT/'catalog';OUT=C/'reports'
def write_csv(path,rows,fields):
 with path.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def svg_chart(path,title,rows,color):
 # Direct labels and a linear scale; no source counts inferred from visual widths.
 width=1120;left=520;right=90;top=108;step=38;height=top+step*len(rows)+60
 maximum=max([r['records'] for r in rows]+[1]);plot=width-left-right
 parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',f'<title id="title">{html.escape(title)}</title>','<desc id="desc">Source record counts. Includes references and drafts. Counts do not establish unique playable items or complete sourcebooks.</desc>',f'<rect width="{width}" height="{height}" fill="#101923"/>',f'<text x="28" y="37" fill="#f1f5f9" font-size="23" font-family="sans-serif">{html.escape(title)}</text>','<text x="28" y="65" fill="#cbd5e1" font-size="14" font-family="sans-serif">8 November 2026 · source records, including references · linear scale</text>']
 for tick in range(5):
  value=maximum*tick/4;x=left+plot*tick/4
  parts.extend([f'<line x1="{x}" x2="{x}" y1="90" y2="{height-48}" stroke="#2b3a49"/>',f'<text x="{x}" y="88" text-anchor="middle" fill="#cbd5e1" font-size="12" font-family="sans-serif">{value:,.0f}</text>'])
 for ix,row in enumerate(rows):
  y=top+step*ix;label=row['label'];bar=plot*row['records']/maximum
  parts.extend([f'<text x="{left-16}" y="{y+17}" text-anchor="end" fill="#e2e8f0" font-size="14" font-family="sans-serif">{html.escape(label)}</text>',f'<rect x="{left}" y="{y}" width="{bar:.2f}" height="25" rx="3" fill="{color}"><title>{html.escape(label)}: {row["records"]:,} records</title></rect>',f'<text x="{left+bar+9:.2f}" y="{y+18}" fill="#f8fafc" font-size="14" font-family="sans-serif">{row["records"]:,}</text>'])
 parts.append(f'<text x="28" y="{height-15}" fill="#cbd5e1" font-size="13" font-family="sans-serif">Book appearances overlap; see source-material-coverage.csv for the separate publication ledger.</text></svg>')
 path.write_text('\n'.join(parts)+'\n')
def main():
 manifest=json.loads((C/'sources.json').read_text());sources=manifest['sources'] if isinstance(manifest,dict) else manifest
 db=sqlite3.connect(C/'indexes/items.sqlite3')
 stats=collections.defaultdict(collections.Counter)
 for sid,status,count in db.execute("select source_id,json_extract(data_json,'$.content_status'),count(*) from items group by 1,2"):stats[sid][status]=count
 rows=[]
 for s in sources:
  sid=s['id'];counts=stats[sid]
  group='game' if sid=='bg3-wiki' or (C/'raw/game-reference-indexes'/f'{sid}.json').exists() else 'original-drafts' if counts['original-conversion-draft'] else 'tabletop-or-index'
  label=s['name'].removesuffix(' public item reference index').replace(' internet-research adaptations (draft 0.1.0)',' drafts')
  label={'conan-exiles':'Conan Exiles','baldurs-gate-1':'Baldur’s Gate 1','baldurs-gate-2':'Baldur’s Gate 2','diablo-1':'Diablo I','diablo-2':'Diablo II','diablo-3':'Diablo III','diablo-4':'Diablo IV','planescape-torment':'Planescape: Torment','nioh-2':'Nioh 2','valheim':'Valheim','sekiro':'Sekiro','ninja-gaiden':'Ninja Gaiden','tenchu':'Tenchu'}.get(label,label)
  rows.append({'source_id':sid,'label':label,'group':group,'records':sum(counts.values()),'reference_only':counts['factual-metadata-only'],'original_drafts':counts['original-conversion-draft'],'other_imported_records':sum(n for k,n in counts.items() if k not in ['factual-metadata-only','original-conversion-draft']),'source_url':s.get('source_url','')})
 rows.sort(key=lambda r:(-r['records'],r['label']))
 assert sum(r['records'] for r in rows)==db.execute('select count(*) from items').fetchone()[0]
 write_csv(OUT/'source-material-imports.csv',rows,list(rows[0]))
 resources=json.loads((OUT/'resource-coverage.json').read_text())['resources'];bookrows=[]
 for r in resources:
  bookrows.append({'resource_id':r['id'],'label':r['label'],'kind':r['kind'],'direct_or_inspired_records':r['direct_or_inspired_records'],'reference_only_records':db.execute("select count(*) from resource_items ri join items i on i.id=ri.item_id where ri.resource_id=? and ri.basis!='regional-context-only' and json_extract(i.data_json,'$.content_status')='factual-metadata-only'",(r['id'],)).fetchone()[0],'draft_records':r['draft_records'],'regional_context_only':r['context_only_records'],'child_record_union':r['child_record_union_count'],'coverage_status':r['coverage_status'],'original_book_audit':r['original_item_audit_status'],'bibliography_url':r['bibliography_url']})
 write_csv(OUT/'source-material-coverage.csv',bookrows,list(bookrows[0]))
 svg_chart(OUT/'tabletop-source-imports.svg','Tabletop sources and public indexes',[r for r in rows if r['group']=='tabletop-or-index'],'#50b9d2')
 svg_chart(OUT/'game-source-imports.svg','Video-game source references',[r for r in rows if r['group']=='game'],'#b494ef')
 svg_chart(OUT/'draft-source-imports.svg','Original 2024 adaptation drafts',[r for r in rows if r['group']=='original-drafts'],'#e5af56')
 lines=['# Source material imported — 8 November 2026','','Source-pack rows below are additive. Publication links in the second table overlap and must not be summed. No full original-sourcebook item audit has been certified. Unknown total item counts mean that a coverage percentage cannot yet be calculated.','','## Imported source packs','','| Source | Records | Reference only | Original drafts | Other imported |','|---|---:|---:|---:|---:|']
 lines += [f"| {r['label']} | {r['records']:,} | {r['reference_only']:,} | {r['original_drafts']:,} | {r['other_imported_records']:,} |" for r in rows]
 lines += ['', '“Other imported” includes licensed rules imports and provider-specific statuses; it does not mean validated 2024 gameplay. Zero-reference rows can still contain metadata-only records under a different provider status.', '', '## Requested resources — overlapping links', '', '| Resource | Direct/inspired | Drafts | Regional context only | Child union | Original audit |', '|---|---:|---:|---:|---:|---|']
 lines += [f"| {r['label']} | {r['direct_or_inspired_records']:,} | {r['draft_records']:,} | {r['regional_context_only']:,} | {r['child_record_union']:,} | {r['original_book_audit']} |" for r in bookrows]
 lines += ['', 'Direct/inspired includes explicit fan-reported book codes and editorial adaptations. It is not proof of original-book appearance. Series child unions describe item links in enumerated children, not extra records. Source names are credited separately from claimed geographic origins. See RECORD-PROVENANCE.md for metadata policy.']
 (OUT/'SOURCE-MATERIAL.md').write_text('\n'.join(lines)+'\n')
 (OUT/'source-material-summary.json').write_text(json.dumps({'source_records':sum(r['records'] for r in rows),'source_packs':len(rows),'nonempty_source_packs':sum(bool(r['records']) for r in rows),'registered_resources':len(bookrows),'original_audits_completed':sum(r['original_book_audit']=='complete' for r in bookrows),'rows':rows},ensure_ascii=False,indent=2)+'\n')
 db.close();print(json.dumps({'source_records':sum(r['records'] for r in rows),'source_packs':len(rows),'nonempty_source_packs':sum(bool(r['records']) for r in rows),'registered_resources':len(bookrows)}))
if __name__=='__main__':main()
