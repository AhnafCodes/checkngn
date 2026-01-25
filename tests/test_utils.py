import unittest
import json
from checkngn.utils import normalize_action, yaml_to_dict, dict_to_yaml

class TestNormalize(unittest.TestCase):
    def test_normalize_string(self):
        self.assertEqual(
            normalize_action("notify_manager"),
            {"action": "notify_manager", "params": {}}
        )

    def test_normalize_list_single_action(self):
        self.assertEqual(
            normalize_action(["put_on_sale", {"percent": 25}]),
            {"action": "put_on_sale", "params": {"percent": 25}}
        )

    def test_normalize_dict(self):
        self.assertEqual(
            normalize_action({"action": "log_event", "params": {"id": 1}}),
            {"action": "log_event", "params": {"id": 1}}
        )

    def test_normalize_list_of_actions_dicts(self):
        self.assertEqual(
            normalize_action([{"action": "a"}, {"action": "b"}]),
            [
                {"action": "a", "params": {}},
                {"action": "b", "params": {}}
            ]
        )

    def test_normalize_list_of_actions_mixed(self):
        self.assertEqual(
            normalize_action(["notify", ["sale", {"p": 10}], {"action": "log"}]),
            [
                {"action": "notify", "params": {}},
                {"action": "sale", "params": {"p": 10}},
                {"action": "log", "params": {}}
            ]
        )

    def test_yaml_conversion(self):
        yaml_str = """
- conditions:
    all:
      - field: current_inventory
        operator: greater_than
        value: 20
  actions:
    - action: put_on_sale
      params:
        sale_percentage: 0.25
"""
        expected_dict = [
            {
                "conditions": {
                    "all": [
                        {"field": "current_inventory", "operator": "greater_than", "value": 20}
                    ]
                },
                "actions": [
                    {"action": "put_on_sale", "params": {"sale_percentage": 0.25}}
                ]
            }
        ]
        
        # Test YAML to Dict
        data = yaml_to_dict(yaml_str)
        self.assertEqual(data, expected_dict)

        # Test Dict to YAML (round trip check might be tricky due to formatting, so we check structure)
        yaml_output = dict_to_yaml(data)
        data_round_trip = yaml_to_dict(yaml_output)
        self.assertEqual(data_round_trip, expected_dict)

if __name__ == "__main__":
    unittest.main()
