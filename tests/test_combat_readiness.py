"""Regression fixtures for the common combat audit findings."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_catalog_by_letter import bg3_effect_findings, rule_findings


class CombatReadinessTests(unittest.TestCase):
    def test_attack_requires_damage_and_range(self):
        item = {'type': 'weapon', 'mechanics': {}}
        weapon = {'evidence': 'published-2024-attack', 'range': '5 ft'}
        self.assertIn('weapon fields: missing damage', rule_findings(item, weapon, {}, {}, []))
        weapon['damage'] = '1d8 Piercing'
        self.assertEqual(rule_findings(item, weapon, {}, {}, []), [])

    def test_non_attack_and_armor_accessory_are_valid_exceptions(self):
        self.assertEqual(rule_findings(
            {'type': 'weapon', 'mechanics': {}}, {'evidence': 'launcher-dependent'}, {}, {}, [],
        ), [])
        self.assertEqual(rule_findings(
            {'type': 'armor', 'mechanics': {}}, {}, {'role': 'armor accessory'}, {}, [],
        ), [])

    def test_shield_requires_bonus_not_base_ac(self):
        item = {'type': 'shield', 'mechanics': {}}
        armor = {'role': 'shield', 'armor_class': '12'}
        self.assertIn('armor fields: missing armor class bonus', rule_findings(item, {}, armor, {}, []))

    def test_editorial_placeholder_detected_in_consumables_only_in_editorial_fields(self):
        item = {'type': 'potion', 'mechanics': {}, 'description': 'A pending curse.'}
        self.assertEqual(rule_findings(item, {}, {}, {}, []), [])
        item['presentation'] = {'details': 'Placeholder from the whitelist.'}
        self.assertIn('placeholder text: presentation.details', rule_findings(item, {}, {}, {}, []))

    def test_fallback_with_convincing_stats_still_needs_review(self):
        item = {'type': 'weapon', 'mechanics': {}}
        weapon = {'evidence': 'improvised-fallback', 'damage': '1d4 Piercing', 'range': '5 ft'}
        findings = rule_findings(item, weapon, {}, {}, [])
        self.assertEqual(findings, ['provisional rules: verify item identity and attack against source'])

    def test_named_effect_with_only_timing_is_incomplete(self):
        record = {'variants': [{'effects': ['Example']}]}
        effects = {'Example': {'stats': {'type': 'passive', 'cost': 'action', 'recharge': 'short rest'}}}
        self.assertEqual(bg3_effect_findings(record, effects, [], {}),
                         ['BG3 effect: no mechanic recorded for Example'])

    def test_coating_requires_mechanics_and_combination_rules(self):
        record = {'variants': [{'stats': {'type': 'Coatings'}, 'effects': ['Oil of Accuracy']}]}
        findings = bg3_effect_findings(record, {}, [], {})
        self.assertEqual(len(findings), 5)
        for phrase in ('playable effect', 'activation cost', 'coating duration', 'combination rules', 'source link only'):
            self.assertTrue(any(phrase in finding for finding in findings), phrase)
        verified = {
            'Special powers': ['+2 to attack rolls, no damage bonus or thrown-weapon bonus.'],
            'Activation': ['Bonus Action'],
            'Duration': ['10 turns'],
            'Combination rules': ['Both weapons in the active set. One coating per set.'],
        }
        effect = {'Oil of Accuracy': {'facts': {'Effect': ['+2 to attack rolls.']}}}
        self.assertEqual(bg3_effect_findings(record, effect, [], verified), [])


if __name__ == '__main__':
    unittest.main()
