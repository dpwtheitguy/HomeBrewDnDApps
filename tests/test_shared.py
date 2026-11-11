import sys,unittest
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from economy import bg3_style_quote
from proficiencies import resolve_grants,skill_bonus
from item_enrichment import positive_amount

class EconomyTests(unittest.TestCase):
    def test_worked_example(self):
        q=bg3_style_quote(100,5,0)
        self.assertEqual(Decimal(q['buy_estimate_gp']),200)
        self.assertEqual(Decimal(q['sell_estimate_gp']),50)
    def test_floor_and_difficulty(self):
        self.assertEqual(Decimal(bg3_style_quote(100,15,100,'honour')['multiplier']),1)
        for difficulty,baseline in [('balanced','2.5'),('explorer','2'),('tactician','3'),('honour','3')]:
            self.assertEqual(Decimal(bg3_style_quote(100,0,0,difficulty)['multiplier']),Decimal(baseline))
    def test_monotonic_and_no_arbitrage(self):
        for skill in range(-5,21):
            q=bg3_style_quote('16',skill,50)
            r=bg3_style_quote('16',skill+1,50)
            self.assertLessEqual(Decimal(q['sell_estimate_gp']),Decimal(q['buy_estimate_gp']))
            self.assertLessEqual(Decimal(r['buy_estimate_gp']),Decimal(q['buy_estimate_gp']))
            self.assertGreaterEqual(Decimal(r['sell_estimate_gp']),Decimal(q['sell_estimate_gp']))
    def test_invalid_context_and_money(self):
        for x in ['nan','inf',-1]:
            with self.assertRaises(ValueError): bg3_style_quote(x)
        with self.assertRaises(ValueError): bg3_style_quote(100,attitude=101)
        self.assertEqual(positive_amount('25 sp'),'2.5')
        self.assertIsNone(positive_amount('0.00'));self.assertIsNone(positive_amount('priceless'))

class ProficiencyTests(unittest.TestCase):
    def test_overlapping_grants_do_not_stack(self):
        grants=[{'source_id':'class:a','kind':'skill','target':'skill:persuasion','multiplier':1},
                {'source_id':'background:b','kind':'skill','target':'skill:persuasion','multiplier':1},
                {'source_id':'feat:c','kind':'skill','target':'skill:persuasion','multiplier':2,'min_level':4}]
        self.assertEqual(resolve_grants(grants,1)[0]['multiplier'],1)
        self.assertEqual(resolve_grants(grants,4)[0]['multiplier'],2)
        self.assertEqual(len(resolve_grants(grants,4)[0]['sources']),3)
        self.assertEqual(skill_bonus(16,3,2),9)
        self.assertEqual(skill_bonus(9,3,.5),0)
    def test_conditional_grants_are_not_silently_applied(self):
        with self.assertRaises(ValueError): resolve_grants([{'condition_ref':'mounted','source_id':'test','kind':'skill','target':'skill:x','multiplier':1}],3)
if __name__=='__main__':unittest.main()
