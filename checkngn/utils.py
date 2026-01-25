import inspect
import json
import sys

import yaml

try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper

def fn_name_to_pretty_label(name):
    return ' '.join([w.title() for w in name.split('_')])

def export_rule_data(variables, actions):
    """ export_rule_data is used to export all information about the
    variables, actions, and operators to the client. This will return a
    dictionary with three keys:
    - variables: a list of all available variables along with their label, type and options
    - actions: a list of all actions along with their label and params
    - variable_type_operators: a dictionary of all field_types -> list of available operators
    """
    from . import operators
    actions_data = actions.get_all_actions()
    variables_data = variables.get_all_variables()
    variable_type_operators = {}
    for name, variable_type in inspect.getmembers(operators):
        if getattr(variable_type, 'export_in_rule_data', False):
            variable_type_operators[variable_type.name] = variable_type.get_all_operators()

    return {"variables": variables_data,
            "actions": actions_data,
            "variable_type_operators": variable_type_operators}

def normalize_action(action_data):
    """
    Normalize action to standard format: {"action": "name", "params": {}}

    Supported formats:
        String: "notify_manager"
        List:   ["put_on_sale", {"percent": 25}]
        Dict:   {"action": "log_event", "params": {"id": 1}}
        List of actions: [{"action": "a"}, "b"] -> [{"action": "a", "params": {}}, {"action": "b", "params": {}}]
    """
    data_type = type(action_data)

    if data_type is str:
        return {"action": action_data, "params": {}}

    if data_type is dict:
        if "action" in action_data:
            return {"action": action_data["action"], "params": action_data.get("params") or {}}
        # If it's a dict but no "action" key, it might be invalid or something else.
        # But let's assume valid input for now or raise error.
        raise ValueError(f"Unknown action format (dict missing 'action'): {action_data}")

    if data_type in (list, tuple):
        # Check if it is a single action in list format ["name", params]
        # It must be length 2, first is string, second is dict (params).
        # AND the second dict should NOT have "action" key (otherwise it looks like list of actions where 2nd is an action)
        if len(action_data) == 2 and isinstance(action_data[0], str) and isinstance(action_data[1], dict) and "action" not in action_data[1]:
             return {
                "action": action_data[0],
                "params": action_data[1]
            }
        
        # Otherwise, treat as list of actions
        return [normalize_action(a) for a in action_data]

    raise ValueError(f"Unknown action format: {action_data}")


def yaml_to_dict(yaml_input):
    """Convert YAML to Python dictionary."""
    data = yaml.load(yaml_input, Loader=SafeLoader)
    return data


def dict_to_yaml(dict_data, indent=2, default_flow_style=False):
    """Convert Dictionary to YAML string."""
    return yaml.dump(
        dict_data,
        Dumper=SafeDumper,
        indent=indent,
        default_flow_style=default_flow_style,
        allow_unicode=True,
        sort_keys=False,
    )
