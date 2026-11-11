"""Add shared proficiency checks and contextual valuations without inventing missing facts."""
from decimal import Decimal, InvalidOperation
import re
from economy import bg3_style_quote

def positive_amount(value):
    if value is None or isinstance(value,bool): return None
    text=str(value).strip().replace(',','')
    m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(cp|sp|ep|gp|pp)?',text)
    if not m: return None
    try: amount=Decimal(m[1])*{'cp':Decimal('.01'),'sp':Decimal('.1'),'ep':Decimal('.5'),'gp':Decimal(1),'pp':Decimal(10),None:Decimal(1)}[m[2]]
    except InvalidOperation: return None
    # Source fixtures use zero as an unknown/sentinel for many magic items.
    return str(amount) if amount>0 else None

def enrich(item):
    fields=item['mechanics'].get('source_fields',{})
    checks=[]; weapon=item['mechanics'].get('weapon') or {}; armor=item['mechanics'].get('armor') or {}
    wname=weapon.get('name')
    slug=lambda v: re.sub(r'[^a-z0-9]+','-',str(v).casefold()).strip('-')
    if weapon:
        tags = set(item.get('tags', []))
        if weapon.get('damage_type'):
            tags.add('damage:' + slug(weapon['damage_type']))
        for assignment in item['mechanics'].get('properties', []):
            if not isinstance(assignment, dict):
                continue
            prop = assignment.get('property') or {}
            if isinstance(prop, dict) and prop.get('name') and prop.get('type') != 'Mastery':
                tags.add('property:' + slug(prop['name']))
        item['tags'] = sorted(tags)
    if item['ruleset']=='bg3':
        templates=item['mechanics']['bg3_template_variants']; facts=templates[0]['facts']
        weapon_category=facts.get('category','').lower()
    else: facts={}; weapon_category='simple' if weapon.get('is_simple') else 'martial' if weapon.get('is_simple') is False else None
    if item['type']=='weapon':
        options=[]
        if wname: options.append('weapon:'+slug(wname))
        if weapon_category in ('simple','martial'): options.append('weapon-category:'+weapon_category)
        if options: checks.append({'context':'weapon-attack','any_of':options,'failure_effect_rule':'rules:weapon-without-proficiency','status':'source-derived'})
    if item['type'] in ('armor','shield') and item['ruleset']!='game-reference':
        kind='shield' if item['image']['path'].endswith('/shield.svg') or item['type']=='shield' else None
        for weight in ('light','medium','heavy'):
            if item['image']['path'].endswith('/'+weight+'-armor.svg'): kind='armor:'+weight
        if kind: checks.append({'context':'wear-armor','any_of':[kind],'failure_effect_rule':'rules:armor-without-training','status':'type-inferred-needs-review'})
    item['access']={'proficiency_interactions':checks,
                    'attunement_conditions':{'status':'unparsed-review-required' if item.get('requires_attunement') else 'not-reported','rule_refs':[]},
                    'class_allowlist':None,
                    'status':'partial-source-derived' if checks else 'not-yet-evaluated',
                    'note':'These checks affect use, attacks or penalties; they do not prevent inventory ownership. No class restrictions have been invented.'}
    requirement=item.get('conversion',{}).get('attunement_requirement')
    if requirement:
        item['access']['attunement_conditions']={'status':'explicit-draft-requirement','all_of':[{'predicate':requirement}], 'rule_refs':[]}
    values=[]
    if facts:
        for field,context in [('price','standard'),('price honour','honour')]:
            amount=positive_amount(facts.get(field))
            if amount: values.append({'amount_gp':amount,'economy_id':'bg3','context':context,'source_field':field,'status':'source-reported-unverified','variant_index':0})
    else:
        amount=positive_amount(fields.get('cost'))
        if amount: values.append({'amount_gp':amount,'economy_id':item['ruleset'],'context':'catalog-list-value','source_field':'cost','status':'source-reported-unverified'})
    if item.get('conversion'):
        for v in values:
            v['status']='author-estimate' if item['conversion'].get('pricing_status') else '2024-base-item-reference-price'
    item['valuation']={'base_values':values,'preferred_policy_id':'bg3-style-v1',
                       'reference_quote':bg3_style_quote(values[0]['amount_gp']) if values else None,
                       'reference_quote_assumptions':{'persuasion_bonus':0,'merchant_attitude':0,'difficulty':'balanced'},
                       'missing_value_reason':None if values else 'No positive numeric source value available; not treated as free.',
                       'campaign_override_allowed':True,
                       'note':'BG3-style estimates for tabletop items are a campaign house rule. Prices are contextual, not permanent item attributes. BG3 variants can have different intrinsic values.'}
    if item.get('record_kind') in ('structure','construction-component'):
        item['valuation'].update(preferred_policy_id='construction-budget-v1',reference_quote=None,reference_quote_assumptions=None,note='Construction estimates exclude land and permits. Merchant Charisma multipliers are not automatically applied to buildings, labor or upkeep; sale value requires a location-specific DM appraisal.')
    return item
