"""Original draft 2024 mappings layered over separately credited internet evidence."""
from copy import deepcopy
import json,re
from pathlib import Path

def build_mystara(items,icons,root):
    folder=root/'catalog/settings/mystara'; inputs=json.loads((folder/'conversion-inputs.json').read_text())
    refs={r['id']:r for r in json.loads((folder/'research-sources.json').read_text())}
    extra_refs=folder/'additional-research-sources.json'
    if extra_refs.exists(): refs.update({r['id']:r for r in json.loads(extra_refs.read_text())})
    bypk={str(i['provenance'].get('upstream_pk')):i for i in items if i['source_id']=='open5e-srd-2024'}
    result=[]
    slug=lambda text: re.sub(r'[^a-z0-9]+','-',text.casefold()).strip('-')
    extra_reskins=folder/'additional-reskins.json'
    if extra_reskins.exists(): inputs.extend(json.loads(extra_reskins.read_text()))
    for row in inputs:
        base=deepcopy(bypk[row['base_item_pk']]); iid='mystara:'+slug(row['name'])
        base.update(id=iid,name=row['name'],name_key=row['name'].casefold(),source_id='mystara-draft-conversions',setting_ids=['mystara'],content_status='original-conversion-draft',tabletop_status='draft-dm-review-required')
        base['tags']=sorted({t for t in base['tags'] if not t.startswith('source:')}|{'mystara','setting:mystara','source:mystara-draft-conversions','conversion:2024-reskin'}|{'culture:'+c for c in row['culture_ids']})
        base['provenance']={'provider':'Project adaptation from internet research','evidence':refs[row['evidence_ref']],
                            'reported_legacy_book':row['reported_book'],'legacy_page_verified':False,
                            'base_rules_id':bypk[row['base_item_pk']]['id'],
                            'base_rules_provenance':bypk[row['base_item_pk']]['provenance']}
        base['conversion']={**row,'version':'0.1.0','canon_status':'fan-reported-not-book-verified','edition_target':'2024','balance_status':'not-playtested','automated_effects_implemented':False}
        base['presentation']={'tldr':f'Uses the 2024 {bypk[row["base_item_pk"]]["name"]} rules.',
                              'flavor':None,'details':row['conversion_note'],
                              'creative_use':{'text':'Use its regional craftsmanship as a conversation starter with a merchant or local artisan. Any social advantage is a DM ruling.','requires_dm_ruling':True}}
        result.append(base)
    custom=[
      {'name':'Chime of Time','ref':'chime','icon':'gear','rarity':'common','cost':'100','type':'wondrous-item',
       'tldr':'A pocket-sized magical timer for watches and coordinated plans.',
       'details':'As a Magic action, set an alarm up to 24 hours ahead. At that time it rings for 6 seconds, audible within 60 feet, unless silenced or physically muffled. Another Magic action cancels it. No charges or attunement.',
       'change':'This adaptation does not suppress or bypass Silence.',
       'creative':'Synchronize watches before two groups enter different passages. The sound can also reveal your position.'},
      {'name':'Lamp of Long Burning','ref':'lamp','icon':'lantern','rarity':'common','cost':'100','type':'wondrous-item',
       'tldr':'A lantern whose light does not consume lamp oil.',
       'details':'A Magic action lights or extinguishes it. It sheds Bright Light for 20 feet and Dim Light for 20 feet farther. It requires no fuel. Immersion in water extinguishes it, but a Magic action can relight it once dry. No charges or attunement.',
       'change':'Water temporarily extinguishes it rather than permanently removing its magic.',
       'creative':'Use it to mark a safe route. Covering the lantern conceals its light normally.'},
      {'name':'Hurricane Lamp','ref':'hurricane','icon':'lantern','rarity':'uncommon','cost':'400','type':'wondrous-item',
       'tldr':'A cursed lantern releases a sudden blast when first opened each day.',
       'details':'The first time its shutters open after dawn, each creature within 10 feet, including the holder, makes a DC 13 Strength saving throw. On a failure, it is pushed 5 feet directly away from the lamp. A creature holding the lamp drops it on a failed save and is not pushed. The burst is instantaneous. Afterward it lights as an ordinary hooded lantern. A Remove Curse spell suppresses the burst for 24 hours.',
       'change':'Replaces legacy storm tables with a bounded push effect and explicit reset; this is a new homebrew curse.',
       'creative':'With the DM’s agreement, set the closed lamp as a risky distraction. It does not distinguish allies.'},
      {'name':'Egg of Wonder (Mist)','ref':'egg','icon':'potion','rarity':'uncommon','cost':'200','type':'consumable',
       'tldr':'Break this single-use egg to release concealing mist.',
       'details':'As a Magic action, throw the egg to a point you can see within 30 feet. It breaks and you cast Fog Cloud at level 1 centered there, without a spell slot or components. You must maintain Concentration as normal, for up to 1 hour. The egg is consumed whether the spell is later ended or countered.',
       'change':'A fixed Fog Cloud version replaces random legacy spell generation.',
       'creative':'Block a sightline before a retreat. Fog also blocks your allies’ sight and requires your Concentration.'}
    ]
    extra_drafts=folder/'additional-drafts.json'
    if extra_drafts.exists(): custom.extend(json.loads(extra_drafts.read_text()))
    for r in custom:
        icon=icons[r['icon']]; name=r['name']; iid='mystara:'+slug(name)
        result.append({'id':iid,'name':name,'name_key':name.casefold(),'source_id':'mystara-draft-conversions','ruleset':'dnd-2024',
          'setting_ids':['mystara'],'category':r['type'],'type':r['type'],'tags':['mystara','setting:mystara','source:mystara-draft-conversions','conversion:homebrew','magic','rarity:'+r['rarity']],
          'magic':True,'rarity':r['rarity'],'requires_attunement':r.get('attunement',False),'description':r['details'],
          'mechanics':{'source_fields':{'cost':r['cost']},'original_adaptation_rules':r['details'],'automated_effects':[]},
          'provenance':{'provider':'Project original adaptation','evidence':refs[r['ref']],'legacy_page_verified':False},
          'content_status':'original-conversion-draft','tabletop_status':'draft-dm-review-required','image':{**icon,'specific_art':None},
          'conversion':{'kind':'original-homebrew-adaptation','version':'0.1.0','edition_target':'2024','changes':r['change'],'pricing_status':'author-estimate-not-source-price','balance_status':'not-playtested','automated_effects_implemented':False,'culture_ids':r.get('culture_ids',[]),'attunement_requirement':r.get('attunement_requirement'),'cultural_identity_ids':r.get('cultural_identity_ids',[])},
          'presentation':{'tldr':r['tldr'],'flavor':r.get('flavor'),'details':r['details'],'creative_use':{'text':r['creative'],'requires_dm_ruling':True}}})
    # Two optional tactical variants prove the parent/variant shape without buffing all reskins.
    variants=[('Claymore','Watchkeeper’s Claymore','After you hit a creature with this weapon, you can use your Reaction to gain 1d4 Temporary Hit Points. Once used, this property cannot be used again until you finish a Short or Long Rest. Temporary Hit Points follow the normal non-stacking rules.','A guard’s oath is etched along the fuller.','415'),
              ('Ethengar Lamellar','Caravan Sentinel’s Lamellar','When a ranged attack hits you while you wear this armor, you can use your Reaction to reduce the damage by 1d4, to a minimum of 0. Once used, this property cannot be used again until you finish a Short or Long Rest.','The plates carry the dust of a hundred roads.','450')]
    for parent,name,details,flavor,cost in variants:
        base=deepcopy(next(i for i in result if i['name']==parent)); parent_id=base['id']
        base.update(id='mystara:'+slug(name),name=name,name_key=name.casefold(),magic=True,rarity='uncommon',requires_attunement=True)
        base['tags']=sorted(set(base['tags'])-{'mundane'}|{'magic','rarity:uncommon','variant:bg3-inspired','attunement:required'})
        base['description']=(base.get('description') or '')+'\n\n'+details
        base['mechanics']['source_fields']['cost']=cost
        base['mechanics']['original_variant_rules']=details
        base['conversion']={'kind':'optional-bg3-inspired-variant','parent_item_id':parent_id,'version':'0.1.0','edition_target':'2024','balance_status':'not-playtested','pricing_status':'author-estimate-not-source-price','automated_effects_implemented':False}
        base['presentation']={'tldr':'A limited-use defensive reaction, in addition to the base equipment rules.','flavor':flavor,'details':details,'creative_use':{'text':'Save the reaction for a dangerous exchange; it competes with opportunity attacks and other reactions.','requires_dm_ruling':False}}
        result.append(base)
    source={'id':'mystara-draft-conversions','name':'Mystara internet-research adaptations (draft 0.1.0)','ruleset':'dnd-2024','setting_ids':['mystara'],
            'record_count':len(result),'source_url':'https://www.pandius.com/items.html','license_ids':['project-original-adaptations-plus-CC-BY-4.0-base-rules'],
            'coverage':'Selected evidence-backed mappings and original drafts only; not a complete extraction of gazetteers or boxed sets.',
            'distribution_status':'Draft adaptations; original setting/fan rights remain with their owners; verify before distributing setting content.'}
    return result,source
