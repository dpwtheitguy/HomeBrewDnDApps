"""Class-independent price estimates, not an assertion of an exact BG3 engine replica."""
from decimal import Decimal, ROUND_HALF_UP

def bg3_style_quote(base_value_gp, persuasion_bonus=0, attitude=0, difficulty='balanced', custom_baseline=None):
    base=Decimal(str(base_value_gp)); skill=Decimal(str(persuasion_bonus)); attitude=Decimal(str(attitude))
    if not all(x.is_finite() for x in (base,skill,attitude)): raise ValueError('Finite numeric inputs required')
    if base<0: raise ValueError('Base value cannot be negative')
    if not -100<=attitude<=100: raise ValueError('Attitude must be between -100 and 100')
    baselines={'explorer':Decimal('2.0'),'balanced':Decimal('2.5'),'tactician':Decimal('3.0'),'honour':Decimal('3.0')}
    if custom_baseline is not None:
        baseline=Decimal(str(custom_baseline))
        if not baseline.is_finite() or baseline<1: raise ValueError('Custom baseline must be finite and at least 1')
    else:
        if difficulty not in baselines: raise ValueError('Unknown difficulty')
        baseline=baselines[difficulty]
    multiplier=max(Decimal(1),baseline-skill/10-attitude/200)
    buy=base*multiplier; sell=base/multiplier
    return {'policy_id':'bg3-style-v1','currency':'gp','base_value_gp':str(base),
            'persuasion_bonus':str(skill),'attitude':str(attitude),'difficulty':difficulty,
            'multiplier':str(multiplier),'buy_estimate_gp':str(buy),'sell_estimate_gp':str(sell),
            'display_buy_gp':str(buy.quantize(Decimal('1'),rounding=ROUND_HALF_UP)),
            'display_sell_gp':str(sell.quantize(Decimal('1'),rounding=ROUND_HALF_UP)),
            'status':'approximate; display rounding is an app convention, not verified BG3 rounding'}
