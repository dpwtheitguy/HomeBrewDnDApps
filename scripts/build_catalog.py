#!/usr/bin/env python3
"""Build offline item packs, YAML exports, search indexes and coverage reports.
No network calls. Requires PyYAML for YAML output (available on this host).
"""
import collections, hashlib, json, re, shutil, sqlite3, subprocess, unicodedata, urllib.parse
from pathlib import Path
import yaml
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"shared"))
from item_enrichment import enrich
from bg3_search_tags import tag_bg3_item
from resource_ledger import compile_resources, write_resource_tables, save_resource_report
from record_context import attach_context
from local_pdf_verifications import apply_local_verifications
from research_packs import build_research_packs
from mystara_pack import build_mystara
from adventure_packs import build_adventure_packs, merge_entities
from catalog_taxonomy import Taxonomy, associate
from build_core_magic_weapon_families import RULES, is_ranged_weapon
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'catalog'
UP=ROOT/'.cache/upstream/open5e'
ICONS=ROOT/'.cache/upstream/game-icons'

def read(path): return json.loads(path.read_text())
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def slug(text):
    text=unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','-',text).strip('-') or 'unknown'
def normal_name(text): return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()
def revision(path): return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def copyfile(src,dst): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)

ICON_FILES={
 'dagger':'lorc/broad-dagger.svg','sword':'delapouite/two-handed-sword.svg',
 'axe':'delapouite/war-axe.svg','hammer':'delapouite/warhammer.svg',
 'spear':'lorc/stone-spear.svg','bow':'lorc/pocket-bow.svg','crossbow':'carl-olsen/crossbow.svg',
 'flail':'delapouite/flail.svg','staff':'lorc/wizard-staff.svg',
 'weapon':'delapouite/two-handed-sword.svg','armor':'delapouite/chest-armor.svg',
 'light-armor':'delapouite/leather-armor.svg','medium-armor':'willdabeast/chain-mail.svg',
 'heavy-armor':'delapouite/chest-armor.svg','shield':'willdabeast/round-shield.svg',
 'potion':'delapouite/health-potion.svg','ring':'lorc/engagement-ring.svg',
 'amulet':'lorc/gem-necklace.svg','wand':'lorc/crystal-wand.svg',
 'rod':'willdabeast/orb-wand.svg','scroll':'lorc/tied-scroll.svg',
 'boots':'lorc/boots.svg','gloves':'delapouite/gloves.svg','cloak':'lucasms/cloak.svg',
 'helmet':'sbed/helmet.svg','gem':'lorc/gems.svg','book':'willdabeast/white-book.svg',
 'key':'sbed/key.svg','torch':'delapouite/torch.svg','currency':'delapouite/coins.svg',
 'tools':'delapouite/toolbox.svg','container':'delapouite/backpack.svg',
 'instrument':'delapouite/flute.svg','food':'delapouite/meal.svg',
 'ammunition':'lorc/arrow-cluster.svg','gear':'delapouite/backpack.svg',
 'clothing':'lorc/robe.svg','poison':'lorc/poison-bottle.svg',
 'alchemy':'lorc/cauldron.svg','dye':'delapouite/powder-bag.svg',
 'land-vehicle':'delapouite/old-wagon.svg','waterborne-vehicle':'pierre-leducq/small-fishing-sailboat.svg',
 'mount':'delapouite/horse-head.svg','rope':'delapouite/jumping-rope.svg',
 'lantern':'lorc/lantern.svg','belt':'lucasms/belt.svg',
}

def classify(name, category, subtype=''):
    n=normal_name(name); c=slug(category); s=normal_name(subtype); text=f'{n} {s}'
    # Explicit source categories outrank incidental words in magic item names.
    if c in ('armor','armour') or 'armor' in c or 'armour' in c or c=='shields':
        if 'shield' in text or c=='shields': return 'armor','shield'
        for weight in ('light','medium','heavy'):
            if weight in c or weight in s: return 'armor',weight+'-armor'
        if any(x in text for x in ('plate','splint','ring mail')): return 'armor','heavy-armor'
        if any(x in text for x in ('breastplate','scale mail','chain shirt','hide')): return 'armor','medium-armor'
        if any(x in text for x in ('leather','padded')): return 'armor','light-armor'
        return 'armor','armor'
    if c in ('weapon','weapons') or 'weapon' in c or c in ('simple','martial'):
        for terms,kind in [(['dagger','knife','sickle'],'dagger'),(['crossbow'],'crossbow'),(['longbow','shortbow'],'bow'),(['sword','rapier','scimitar'],'sword'),(['axe'],'axe'),(['hammer','maul','mace','club','morningstar'],'hammer'),(['spear','pike','halberd','glaive','javelin','trident','lance'],'spear'),(['flail','whip'],'flail'),(['staff'],'staff')]:
            if any(t in text for t in terms): return 'weapon',kind
        return 'weapon','weapon'
    for cats,kind in [(['clothing','camp-clothing','camp-clothes','underwear','undergarments'],'clothing'),(['poison','poisons'],'poison'),(['alchemy-ingredients','alchemy-extracts'],'alchemy'),(['dyes'],'dye'),(['containers','equipment-pack'],'container'),(['slates'],'book'),(['land-vehicle'],'land-vehicle'),(['waterborne-vehicle'],'waterborne-vehicle'),(['mount'],'mount'),(['potion','potions','elixirs','coatings','grenades'],'potion'),(['ring','rings'],'ring'),(['amulets','amulet'],'amulet'),(['wand','wands'],'wand'),(['rod','rods'],'rod'),(['staff','staves'],'staff'),(['scroll','scrolls'],'scroll'),(['boots','camp-shoes'],'boots'),(['gloves'],'gloves'),(['cloak','cloaks'],'cloak'),(['helmets','helmet'],'helmet'),(['book','books','notes'],'book'),(['key','keys'],'key'),(['ammunition','arrows'],'ammunition'),(['tools','tool'],'tools'),(['musical-instruments'],'instrument'),(['food','drinks','camp-supplies'],'food')]:
        if c in cats: return kind,kind
    for token,kind in [('potion','potion'),('elixir','potion'),('scroll','scroll'),('amulet','amulet'),('necklace','amulet'),('boots','boots'),('gloves','gloves'),('gauntlets','gloves'),('cloak','cloak'),('helmet','helmet'),('helm','helmet'),('wand','wand'),('ring','ring'),('gem','gem'),('book','book'),('key','key'),('torch','torch'),('backpack','container'),('rope','rope'),('lantern','lantern'),('belt','belt')]:
        if re.search(r'\b'+token+r'\b',n): return c or 'gear',kind
    return c if c!='unknown' else 'gear','gear'


def install_icons():
    manifest={}
    for kind,rel in ICON_FILES.items():
        src=ICONS/rel
        if not src.exists():
            # Fallback stays explicit rather than silently omitting an image.
            rel='delapouite/backpack.svg'; src=ICONS/rel
        dst=CAT/'images/types'/f'{kind}.svg'; copyfile(src,dst)
        author=rel.split('/')[0]
        manifest[kind]={'path':str(dst.relative_to(CAT)),'kind':'generic-type-icon',
            'author':author,'license':'CC-BY-3.0',
            'source_url':'https://github.com/game-icons/icons/blob/'+revision(ICONS)+'/'+rel,
            'credit':f'Icon made by {author}, Game-icons.net',
            'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'modified':False}
    copyfile(ICONS/'license.txt',CAT/'licenses/game-icons.txt')
    write(CAT/'images/manifest.json',{'upstream_commit':revision(ICONS),'icons':manifest})
    return manifest


def main():
    icons=install_icons(); items=[]; sources=[]; warnings=[]
    commit=revision(UP)
    copyfile(UP/'LICENSE.md',CAT/'licenses/open5e-repository.md')
    copyfile(UP/'data/v2/License.json',CAT/'licenses/open5e-content-licenses.json')
    # Prefer V2; do not add the same source's V1 data on top of it.
    selections=[('v2','wizards-of-the-coast/srd-2014','dnd-2014'),
                ('v2','wizards-of-the-coast/srd-2024','dnd-2024'),
                ('v2','kobold-press/vom','third-party-5e'),
                ('v1','a5e','a5e'),('v1','toh','third-party-5e'),('v1','taldorei','third-party-5e')]
    v2root=UP/'data/v2'
    weapon_lookup={}; armor_lookup={}; prop_lookup={}; prop_assign=collections.defaultdict(list)
    for p in v2root.rglob('*.json'):
        if p.name not in ('Weapon.json','Armor.json','WeaponProperty.json','WeaponPropertyAssignment.json'): continue
        for r in read(p):
            if p.name=='Weapon.json': weapon_lookup[r['pk']]=r['fields']
            elif p.name=='Armor.json': armor_lookup[r['pk']]=r['fields']
            elif p.name=='WeaponProperty.json': prop_lookup[r['pk']]=r['fields']
            else:
                f=r['fields']; prop_assign[f.get('weapon')].append(f)
    armor_facts = read(CAT/'supplements/published-2024-armor-facts.json')
    vault_pages = {
        'vom_akaasit-blade': 11,
        'vom_black-and-white-daggers': 14,
        'vom_blackguards-dagger': 14,
        'vom_blackguards-shortsword': 14,
        'vom_animated-chain-mail': 12,
        'vom_armor-of-cushioning': 12,
        'vom_badger-hide': 14,
        'vom_armor-of-the-ngobou': 13,
        'vom_blade-of-petals': 14,
        'vom_blade-of-the-dervish': 15,
        'vom_blade-of-the-temple-guardian': 15,
        'vom_bloodbow': 15,
        'vom_blooddrinker-spear': 15,
        'vom_blood-soaked-hide': 16,
        'vom_bone-whip': 16,
        'vom_bonebreaker-mace': 17,
        'vom_brazen-bulwark': 17,
        'vom_breaker-lance': 17,
        'vom_bullseye-arrow': 17,
        'vom_candied-axe': 18,
        'vom_cephalopod-breastplate': 18,
        'vom_chieftains-axe': 18,
        'vom_clockwork-mace-of-divinity': 19,
        'vom_commanders-plate': 19,
        'vom_constant-dagger': 20,
        'vom_crimson-starfall-arrow': 20,
        'vom_crusaders-shield': 20,
        'vom_dagger-of-the-barbed-devil': 21,
        'vom_deadfall-arrow': 21,
        'vom_dimensional-net': 21,
        'vom_dirgeblade': 21,
        'vom_dirk-of-daring': 22,
        'vom_dragonstooth-blade': 22,
        'vom_enraging-ammunition': 22,
        'vom_ensnaring-ammunition': 22,
        'vom_entrenching-mattock': 22,
        'vom_exsanguinating-blade': 22,
    }
    vault_weapon_corrections = {
        'vom_anchor-of-striking': ('Anchor of Striking', 'srd_war-pick', 11),
        'vom_anointing-mace': ('Anointing Mace', 'srd_maul', 12),
        'vom_asps-kiss': ("Asp's Kiss", 'srd_shortsword', 13),
        'vom_blackguards-handaxe': ('Axe of the Ancients', 'srd_handaxe', 14),
    }
    for ver,rel,ruleset in selections:
        base=UP/'data'/ver/rel; doc=read(base/'Document.json')[0]; df=doc['fields']
        key='open5e-'+slug(rel.split('/')[-1]); start=len(items)
        rawdir=CAT/'raw/open5e'/ver/rel
        selected_names=['Document.json','MagicItem.json','Item.json','Weapon.json','Armor.json','WeaponProperty.json','WeaponPropertyAssignment.json','ItemCategory.json']
        for fn in selected_names:
            if (base/fn).exists(): copyfile(base/fn,rawdir/fn)
        filenames=['Item.json','MagicItem.json'] if ver=='v2' else ['MagicItem.json','Weapon.json','Armor.json']
        for fn in filenames:
            if not (base/fn).exists(): continue
            for raw in read(base/fn):
                f=raw['fields']; ismagic=fn=='MagicItem.json'; iid=key+':'+str(raw['pk'])
                vault_page = None
                if key == 'open5e-vom' and ismagic:
                    vault_page = vault_pages.get(raw['pk'])
                    if correction := vault_weapon_corrections.get(raw['pk']):
                        corrected_name, corrected_weapon, vault_page = correction
                        f = {**f, 'name': corrected_name, 'weapon': corrected_weapon}
                    if raw['pk'].startswith('vom_bloodprice-'):
                        vault_page = 16
                    if raw['pk'].startswith('vom_buzzing-'):
                        vault_page = 17
                    if raw['pk'].startswith(('vom_chainbreaker-', 'vom_chillblain-')):
                        vault_page = 18
                    if raw['pk'].startswith('vom_dawn-shard-'):
                        vault_page = 21
                    if raw['pk'].startswith('vom_encouraging-'):
                        vault_page = 22
                    if (raw['pk'] in ('vom_animated-chain-mail', 'vom_blood-soaked-hide', 'vom_brazen-bulwark',
                                      'vom_crusaders-shield')
                            or raw['pk'].startswith(('vom_bloodprice-', 'vom_chillblain-', 'vom_encouraging-'))):
                        f = {**f, 'requires_attunement': True}
                category=f.get('category') or f.get('type') or ('armor' if fn=='Armor.json' else 'weapon' if fn=='Weapon.json' else 'gear')
                weapon=weapon_lookup.get(f.get('weapon'),{}) if ver=='v2' else (f if fn=='Weapon.json' else {})
                armor=armor_lookup.get(f.get('armor'),{}) if ver=='v2' else (f if fn=='Armor.json' else {})
                armor_fact = armor_facts['records'].get(iid)
                if armor_fact:
                    armor=armor_lookup[armor_fact['base_id'].split(':',1)[1]]
                mithral_half_plate = iid == 'open5e-srd-2014:srd_mithral-armor-half-plate'
                if mithral_half_plate:
                    armor = armor_lookup['srd_half-plate']
                    category = 'medium-armor'
                typ,icon=classify(f['name'],category,weapon.get('name','')+' '+armor.get('name',''))
                properties=[]
                for a in prop_assign.get(f.get('weapon'),[]):
                    p=prop_lookup.get(a.get('property') or a.get('weapon_property'),{})
                    properties.append({'assignment':a,'property':p})
                if key == 'open5e-srd-2024' and ismagic and weapon:
                    melee_family = next((family for prefix, family in
                        (('Defender (', 'Defender'), ('Flame Tongue ', 'FlameTongue'))
                        if f['name'].startswith(prefix)), None)
                    if melee_family and is_ranged_weapon({'weapon': weapon, 'properties': properties}):
                        warnings.append({'id': iid, 'issue': 'Excluded ranged variant of a melee-only magic weapon',
                                         'source': RULES + '#' + melee_family})
                        continue
                if ver=='v1' and f.get('properties_json'):
                    try: properties=json.loads(f['properties_json'])
                    except ValueError: warnings.append({'id':iid,'issue':'invalid properties_json'})
                attune=f.get('requires_attunement')
                if isinstance(attune,str): attune=bool(attune.strip()) and attune.lower() not in ('no','false','none')
                armor_attunement_correction = (key == 'open5e-srd-2024' and ismagic and armor
                        and f['name'].startswith(('Armor of Resistance (', 'Armor of Vulnerability ('))
                        and 'Resistance to one' in (f.get('desc') or '') and attune is not True)
                if armor_attunement_correction:
                    attune = True
                tags={f'ruleset:{ruleset}',f'source:{key}',f'type:{typ}',f'icon-type:{icon}',f'category:{slug(category)}','magic' if ismagic else 'mundane'}
                rarity=f.get('rarity')
                enhanced_armor = re.search(r' \(\+([123])\)$',f['name']) if armor else None
                if (key=='open5e-srd-2024' and ismagic and armor.get('name')!='Shield' and enhanced_armor
                        and 'bonus to Armor Class' in (f.get('desc') or '')):
                    rarity=('rare','very-rare','legendary')[int(enhanced_armor[1])-1]
                if rarity: tags.add('rarity:'+slug(rarity))
                if attune: tags.add('attunement:required')
                if weapon.get('damage_type'): tags.add('damage:'+slug(weapon['damage_type']))
                for prop in ('finesse','light','heavy','versatile','reach','thrown','loading','two-handed'):
                    if re.search(r'\b'+re.escape(prop)+r'\b',json.dumps([p.get('property',{}).get('name','') if isinstance(p,dict) else p for p in properties]).lower()): tags.add('property:'+prop)
                item={'id':iid,'name':f['name'],'name_key':normal_name(f['name']),'source_id':key,'ruleset':ruleset,
                      'category':slug(category),'type':typ,'tags':sorted(tags),'magic':ismagic,'rarity':rarity,
                      'requires_attunement':attune,'description':f.get('desc') or None,
                      'mechanics':{'source_fields':{k:v for k,v in f.items() if k not in ('name','desc','document')},'weapon':weapon or None,'armor':armor or None,'properties':properties},
                      'provenance':{'provider':'Open5e','repository_commit':commit,'file':str((rawdir/fn).relative_to(CAT)),'upstream_pk':raw['pk'],'upstream_model':raw['model']},
                      'content_status':'source-transcription-unverified','tabletop_status':'native-source-rules' if ruleset in ('dnd-2014','dnd-2024') else 'supplement-review-required',
                      'image':{**icons[icon],'specific_art':None}}
                if vault_page:
                    item['provenance'].update({
                        'source_url': 'https://koboldpress.com/kpstore/product/vault-of-magic-for-5th-edition/',
                        'locator': {'book': 'Vault of Magic', 'printed_page': vault_page},
                        'original_publication_verified': True,
                    })
                    if f['name'] != raw['fields']['name']:
                        item['mechanics']['reference_metadata'] = {'aliases': [raw['fields']['name']]}
                    if f.get('weapon') != raw['fields'].get('weapon'):
                        item['mechanics']['source_fields']['upstream_weapon'] = raw['fields'].get('weapon')
                if armor_fact:
                    item['provenance']['base_rules_id']=armor_fact['base_id']
                    item['provenance']['source_url']=armor_facts['source']
                elif rarity!=f.get('rarity'):
                    item['provenance']['rarity_correction_source']='https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z#Armor12or3'
                if mithral_half_plate:
                    item['provenance']['base_rules_id'] = 'open5e-srd-2014:srd_half-plate'
                    item['provenance']['classification_correction_source'] = (
                        'https://www.dndbeyond.com/sources/dnd/basic-rules-2014/magic-items#MithralArmor')
                if armor_attunement_correction:
                    item['provenance']['attunement_correction_source']='https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z#' + f['name'].split(' (',1)[0].replace(' ','')
                if ver=='v2' and typ=='weapon' and not weapon:
                    warnings.append({'id':iid,'issue':'weapon-category item has no resolved weapon relation; no mechanics inferred'})
                items.append(item)
        source={'id':key,'name':df.get('name',df.get('title')),'ruleset':ruleset,'provider':'Open5e',
                'publisher':df.get('publisher',df.get('organization')),'author':df.get('author'),
                'upstream_document':doc,'upstream_commit':commit,
                'source_url':df.get('permalink',df.get('url')),
                'license_ids':df.get('licenses',[df.get('license')]),
                'copyright_notice':df.get('copyright'),
                'record_count':len(items)-start,
                'coverage':'Only item data available in this pinned Open5e source. Not the entire published book.',
                'distribution_status':'attribution-required' if key in ('open5e-srd-2014','open5e-srd-2024','open5e-a5e') else 'preserve-ogl-notices-and-review-before-shipping'}
        if ver=='v2':
            old={'srd-2014':'wotc-srd','vom':'vom'}.get(rel.split('/')[-1])
            oldpath=UP/'data/v1'/old/'Document.json' if old else None
            if oldpath and oldpath.exists():
                source['legacy_document_notice']=read(oldpath)
                copyfile(oldpath,rawdir/'legacy-document-notice.json')
        sources.append(source)
    bgfile=CAT/'raw/bg3-wiki/items.json'
    if bgfile.exists():
        weapons_path = CAT/'supplements/bg3-weapon-rules.json'
        details_path = CAT/'supplements/bg3-item-rules.json'
        bg3_weapons = read(weapons_path)['weapons'] if weapons_path.exists() else {}
        bg3_details = read(details_path)['records'] if details_path.exists() else {}
        start=len(items)
        redirect_audit = CAT/'research/bg3-index-crosscheck.json'
        aliases_by_page = collections.defaultdict(list)
        if redirect_audit.exists():
            for redirect in read(redirect_audit)['redirects']:
                aliases_by_page[redirect['page_id']].append(redirect['title'])
        for page in read(bgfile):
            templates=page['templates']
            if not templates:
                warnings.append({'pageid':page['pageid'],'issue':'transcluding page has no literal item template; excluded'})
                continue
            first=templates[0]; f=first['facts']; iid='bg3-wiki:'+str(page['pageid'])
            cat=f.get('type') or ('weapon' if 'weapon' in page['kinds'] else f.get('category') or 'gear')
            # Weapon type (Daggers etc.) is a subtype rather than top-level category.
            broad='weapon' if 'weapon' in page['kinds'] else cat
            typ,icon=classify(page['title'],broad,f.get('type',''))
            title=page['title']; name=f.get('name',title)
            # Keep raw template markup as facts; use clean page titles for reliable display/search.
            if any(x in name for x in ('{{','[[','<')): name=title
            url='https://bg3.wiki/wiki/'+urllib.parse.quote(title.replace(' ','_'),safe='')
            tags={'ruleset:bg3','source:bg3-wiki',f'type:{typ}',f'category:{slug(cat)}',f'icon-type:{icon}','tabletop:adaptation-needed'}
            for prop in ('finesse','light','heavy','versatile','reach','thrown','loading','two-handed'):
                if f.get(prop,'').lower()=='yes': tags.add('property:'+prop)
            if f.get('rarity'): tags.add('rarity:'+slug(f['rarity']))
            variant_fields=[]
            for t in templates:
                variant_fields.append({'template':t['template'],'facts':t['facts']})
            artwork=[]
            for t in templates:
                for field in ('icon','image','controller icon'):
                    filename=t['facts'].get(field)
                    if filename:
                        ref={'file_title':'File:'+filename,'kind':field,'source_page':url,'status':'reference-only-not-cleared-for-app-use'}
                        if ref not in artwork: artwork.append(ref)
            mechanics = {'bg3_template_variants': variant_fields}
            if page['pageid'] in aliases_by_page:
                mechanics['reference_metadata'] = {'aliases': aliases_by_page[page['pageid']]}
            items.append({'id':iid,'name':name,'name_key':normal_name(name),'source_id':'bg3-wiki','ruleset':'bg3',
                          'category':slug(cat),'type':typ,'tags':sorted(tags),'magic':None,'rarity':f.get('rarity'),
                          'requires_attunement':None,'description':None,
                          'mechanics':mechanics,
                          'provenance':{'provider':'bg3.wiki','pageid':page['pageid'],'revision_id':page['revid'],
                                        'revision_timestamp':page['timestamp'],'source_url':url,
                                        'permanent_url':f'https://bg3.wiki/w/index.php?oldid={page["revid"]}'},
                          'content_status':'factual-metadata-only','tabletop_status':'adaptation-needed',
                          'image':{**icons[icon],'specific_art':None,'bg3_art_references':artwork}})
            tag_bg3_item(items[-1], bg3_weapons, bg3_details)
        sources.append({'id':'bg3-wiki','name':"Baldur’s Gate 3 wiki item facts",'ruleset':'bg3','provider':'bg3.wiki',
                        'source_url':'https://bg3.wiki/wiki/Equipment','license_ids':['mixed-see-policy'],
                        'policy_url':'https://bg3.wiki/wiki/bg3wiki:Copyrights',
                        'record_count':len(items)-start,'coverage':'Pages transcluding weapon, equipment or misc item templates; one record per page with template variants preserved. Not all internal game objects.',
                        'distribution_status':'research-metadata-only; game artwork and descriptive text not included'})
    ddbfile=CAT/'raw/dndbeyond-public-index/items.json'
    if ddbfile.exists():
        start=len(items)
        for r in read(ddbfile):
            typ,icon=classify(r['name'],r.get('type') or 'gear',r.get('subtype') or '')
            tags={'source:dndbeyond-public-index','ruleset:dnd-edition-unverified',f'type:{typ}','magic','content:metadata-only'}
            if r.get('rarity'): tags.add('rarity:'+slug(r['rarity']))
            if r.get('requires_attunement'): tags.add('attunement:required')
            items.append({'id':'dndbeyond:'+r['slug'].split('-')[0],'name':r['name'],'name_key':normal_name(r['name']),
                'source_id':'dndbeyond-public-index','ruleset':'dnd-edition-unverified','category':slug(r.get('type') or 'gear'),'type':typ,
                'tags':sorted(tags),'magic':True,'rarity':r.get('rarity'),'requires_attunement':r.get('requires_attunement'),
                'description':None,'mechanics':{'subtype':r.get('subtype')},
                'provenance':{'provider':'D&D Beyond public item index','source_url':r['url'],'book':None,'edition':None},
                'content_status':'factual-metadata-only','tabletop_status':'full-source-mechanics-needed',
                'image':{**icons[icon],'specific_art':None,'art_reference_urls':r.get('image_reference_urls',[])}})
        sources.append({'id':'dndbeyond-public-index','name':'D&D Beyond public magic-item index','ruleset':'dnd-edition-unverified',
            'provider':'D&D Beyond','source_url':'https://www.dndbeyond.com/magic-items?filter-partnered-content=f',
            'license_ids':['metadata-only-no-content-license-claimed'],'record_count':len(items)-start,
            'coverage':'Public listing cards only. Books and editions are not exposed by these cards. Reprints and SRD overlap remain separate records.',
            'distribution_status':'research-metadata; descriptions, mechanics and artwork not included'})
    if (CAT/'settings/mystara/conversion-inputs.json').exists():
        mystara_items,mystara_source=build_mystara(items,icons,ROOT)
        items.extend(mystara_items); sources.append(mystara_source)
    adventure_items,adventure_sources=build_adventure_packs(items,icons,ROOT)
    items.extend(adventure_items); sources.extend(adventure_sources)
    research_items,research_sources=build_research_packs(items,icons,ROOT)
    items.extend(research_items); sources.extend(research_sources)
    merge_entities(ROOT)
    association_path=CAT/'settings/mystara/item-associations.json'
    extra_associations=read(association_path) if association_path.exists() else {}
    for item in items:
        if item['id'] in extra_associations:item.setdefault('associations',[]).extend(extra_associations[item['id']])
    items=apply_local_verifications(items,ROOT)
    taxonomy=Taxonomy(CAT/'taxonomy/entities.json')
    items=[associate(enrich(i),taxonomy) for i in items]
    resource_rows,resource_links=compile_resources(items,ROOT)
    save_resource_report(resource_rows,ROOT)
    source_map={s['id']:s for s in sources}
    event_path=CAT/'changes/editorial-events.json'
    events=read(event_path) if event_path.exists() else []
    items=[attach_context(i,source_map[i['source_id']],ROOT,events) for i in items]
    items.sort(key=lambda x:x['id'])
    if len({i['id'] for i in items})!=len(items): raise ValueError('Duplicate IDs')
    for i in items:
        if not (CAT/i['image']['path']).is_file(): raise ValueError('Missing image '+i['id'])
    bysource=collections.defaultdict(lambda:collections.defaultdict(list))
    for i in items: bysource[i['source_id']][i['type']].append(i)
    packroot=CAT/'normalized'
    # Only generated outputs are replaced. Raw snapshots and source files are retained.
    for p in packroot.rglob('*.json'): p.unlink()
    for p in packroot.rglob('*.yaml'): p.unlink()
    for source,categories in bysource.items():
        ruleset=next(i['ruleset'] for rows in categories.values() for i in rows)
        for typ,rows in categories.items():
            path=packroot/ruleset/source/(slug(typ)+'.json')
            write(path,rows)
            path.with_suffix('.yaml').write_text(yaml.safe_dump(rows,allow_unicode=True,sort_keys=False,width=110))
    write(CAT/'sources.json',sources)
    with (CAT/'items.jsonl').open('w') as out:
        for i in items: out.write(json.dumps(i,ensure_ascii=False)+'\n')
    names=collections.defaultdict(list); tags=collections.defaultdict(list)
    for i in items:
        names[i['name_key']].append(i['id'])
        for tag in i['tags']: tags[tag].append(i['id'])
    write(CAT/'indexes/tags.json',dict(sorted(tags.items())))
    write(CAT/'indexes/same-name-groups.json',{k:v for k,v in names.items() if len(v)>1})
    dbpath=CAT/'indexes/items.sqlite3'
    staging_dbpath=dbpath.with_suffix('.sqlite3.tmp')
    staging_dbpath.unlink(missing_ok=True)
    db=sqlite3.connect(staging_dbpath)
    db.executescript('''CREATE TABLE items(id TEXT PRIMARY KEY,name TEXT,name_key TEXT,source_id TEXT,ruleset TEXT,type TEXT,rarity TEXT,image_path TEXT,data_json TEXT);
        CREATE INDEX items_source ON items(source_id); CREATE INDEX items_type ON items(type); CREATE INDEX items_ruleset ON items(ruleset);
        CREATE TABLE tags(item_id TEXT REFERENCES items(id),tag TEXT,PRIMARY KEY(item_id,tag)); CREATE INDEX tags_tag ON tags(tag);
        CREATE TABLE associations(item_id TEXT REFERENCES items(id),entity_id TEXT,role TEXT,evidence_json TEXT,PRIMARY KEY(item_id,entity_id,role));
        CREATE INDEX associations_entity ON associations(entity_id,role);
        CREATE VIRTUAL TABLE item_search USING fts5(id UNINDEXED,name,tags,description);''')
    for i in items:
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?)',(i['id'],i['name'],i['name_key'],i['source_id'],i['ruleset'],i['type'],i['rarity'],i['image']['path'],json.dumps(i,ensure_ascii=False)))
        db.executemany('INSERT INTO tags VALUES(?,?)',[(i['id'],t) for t in i['tags']])
        db.executemany('INSERT INTO associations VALUES(?,?,?,?)',[(i['id'],a['entity_id'],a['role'],json.dumps(a,ensure_ascii=False)) for a in i['associations']])
        aliases = i['mechanics'].get('reference_metadata', {}).get('aliases', [])
        search_name = ' '.join([i['name'], *aliases])
        db.execute('INSERT INTO item_search VALUES(?,?,?,?)',(i['id'],search_name,' '.join(i['tags']),i['description'] or ''))
    write_resource_tables(db,resource_rows,resource_links)
    db.commit(); db.close()
    staging_dbpath.replace(dbpath)
    stats={'source_records':len(items),'distinct_normalized_names':len(names),
           'construction_records':sum(i.get('record_kind') in ('structure','construction-component') for i in items),
           'trade_category_records':sum(i.get('record_kind')=='trade-category' for i in items),
           'construction_proposals':sum(i.get('record_kind')=='structure' for i in items),
           'vehicle_proposals':sum(i.get('record_kind')=='vehicle' for i in items),
           'by_ruleset':dict(collections.Counter(i['ruleset'] for i in items)),
           'by_source':{s['id']:s['record_count'] for s in sources},
           'by_type':dict(collections.Counter(i['type'] for i in items)),
           'generic_image_coverage':sum(bool(i['image']['path']) for i in items),'unique_generic_icons':len(icons),
           'specific_art_included':0,'bg3_records_with_art_references':sum(bool(i['image'].get('bg3_art_references')) for i in items),
           'records_with_description':sum(bool(i['description']) for i in items),
           'attributed_records':sum(bool(i['associations']) for i in items),'quality_warning_count':len(warnings),'records_with_base_value':sum(bool(i['valuation']['base_values']) for i in items),
           'counting_notes':['Source records keep editions and books separate.','Distinct names are a simple comparison aid, not semantic deduplication.','Magic variants already expanded upstream are retained; no generated combinations are added.','BG3 uses one record per wiki page; UUID/template variants do not inflate the record count.','V1 copies of sources already represented by V2 are not counted.','Armor and weapon relation rows are not counted again as items.','Trade merchandise categories remain broad source categories, not generated individual creatures, variants or ready-to-use inventory definitions.','Construction plans and building-piece references are included in the overall catalog and reported separately; they are not portable equipment or completed world-builder functionality.']}
    write(CAT/'reports/counts.json',stats)
    write(CAT/'reports/quality-warnings.json',warnings)
    lines=['# Collected item catalog','',f"{len(items):,} source records; {len(names):,} distinct normalized names.",'', '| Source | Records |','|---|---:|']
    lines += [f'| {s["name"]} | {s["record_count"]:,} |' for s in sources]
    lines += ['',f'Generic icons: {stats["generic_image_coverage"]:,}/{len(items):,} records using {len(icons)} reusable type icons. Item-specific artwork included: 0.',
              '',f'Quality warnings: {len(warnings)}. See `quality-warnings.json`; these records are not verified executable tabletop mechanics.',
              '', f'Construction domain: {stats["construction_records"]:,} records ({stats["construction_proposals"]} original proposals plus reference components); original skyship/vehicle proposals: {stats["vehicle_proposals"]}. These are not portable inventory items.', '', 'This is an initial collected catalog, not every item published for D&D. See catalog/README.md for coverage, source notices and remaining work.']
    (CAT/'reports/COUNTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(stats,indent=2))

if __name__=='__main__':
    import urllib.parse
    main()
