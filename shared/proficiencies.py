"""Reference implementation for source-tracked proficiency grants shared by all class apps.
Ranks are not added together. An explicit effect is needed for any extra bonus.
"""
from fractions import Fraction

def resolve_grants(grants, level):
    if not 1<=level<=20: raise ValueError('Level must be 1–20')
    out={}
    for grant in grants:
        if grant.get('condition_ref'): raise ValueError('Resolve conditional grants before aggregation')
        if not grant.get('min_level',1)<=level<=grant.get('max_level',20): continue
        rank=Fraction(str(grant['multiplier']))
        if rank not in (Fraction(0),Fraction(1,2),Fraction(1),Fraction(2)): raise ValueError('Unsupported multiplier')
        key=(grant['kind'],grant['target'])
        entry=out.setdefault(key,{'multiplier':Fraction(0),'sources':[]})
        entry['multiplier']=max(entry['multiplier'],rank)
        entry['sources'].append(grant['source_id'])
    return [{'kind':kind,'target':target,'multiplier':float(value['multiplier']),
             'sources':sorted(set(value['sources']))} for (kind,target),value in sorted(out.items())]

def skill_bonus(ability_score, proficiency_bonus, multiplier=0, other_bonus=0):
    rank=Fraction(str(multiplier))
    if rank not in (Fraction(0),Fraction(1,2),Fraction(1),Fraction(2)): raise ValueError('Unsupported multiplier')
    return (ability_score-10)//2 + (proficiency_bonus*rank).__floor__() + other_bonus
