"""Attach selected original-page checks to existing records without duplicating them."""
import hashlib,json
from functools import lru_cache
@lru_cache(maxsize=None)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def apply_local_verifications(items,root):
 path=root/'catalog/settings/mystara/local-pdf-verifications.json'
 if not path.exists():return items
 for patch in json.loads(path.read_text())['patches']:
  matches=[i for i in items if i['source_id']==patch['source_id'] and i['name'].casefold()==patch['name'].casefold()]
  if len(matches)!=1:raise ValueError('Local verification target missing or ambiguous: '+patch['name'])
  item=matches[0];ev=patch['evidence'];pdf=root/ev['local_file']
  if pdf.exists() and digest(pdf)!=ev['file_sha256']:raise ValueError('Verified source PDF changed: '+ev['local_file'])
  item.setdefault('source_verifications',[]).append({**ev,'note':patch['note']})
  item['provenance'].update(original_publication_verified=True,legacy_page_verified=True,verified_fields=ev['verified_fields'],verification_scope=ev['verification_scope'])
  if patch.get('legacy_facts'):item['mechanics']['verified_legacy_facts']=patch['legacy_facts']
  if patch.get('aliases'):
   item['aliases']=sorted(set(item.get('aliases',[]))|set(patch['aliases']));item['tags']=sorted(set(item['tags'])|{'alias:'+s.casefold() for s in patch['aliases']})
 return items
