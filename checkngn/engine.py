from .fields import FIELD_NO_INPUT
from . import logs
import pandas as pd

# Sentinel for missing attributes
_MISSING = object()


def normalize_action(action_data):
    """
    Normalize action to standard format: {"action": "name", "params": {}}

    Supported formats:
        String: "notify_manager"
        List:   ["put_on_sale", {"percent": 25}]
        Dict:   {"action": "log_event", "params": {"id": 1}}
    """
    data_type = type(action_data)

    if data_type is str:
        return {"action": action_data, "params": {}}

    if data_type in (list, tuple):
        return {
            "action": action_data[0],
            "params": action_data[1] if len(action_data) > 1 else {}
        }

    if data_type is dict and (action := action_data.get("action")):
        return {"action": action, "params": action_data.get("params") or {}}

    raise ValueError(f"Unknown action format: {action_data}")


def run_all(rule_list,
            defined_variables,
            defined_actions,
            stop_on_first_trigger=False,
            debug=False):
    """
    Execute a list of rules against the provided variables and actions.

    Args:
        rule_list: List of rule dictionaries with 'conditions' and 'actions'
        defined_variables: Instance of BaseVariables subclass
        defined_actions: Instance of BaseActions subclass
        stop_on_first_trigger: If True, stop after first rule triggers
        debug: If True, enable debug logging to console

    Returns:
        bool: True if any rule was triggered
    """
    if debug:
        logs.enable_debug(True)

    rule_was_triggered = False
    total_rules = len(rule_list)

    for idx, rule in enumerate(rule_list, 1):
        logs.log_rule_start(idx, total_rules)
        result = run(rule, defined_variables, defined_actions)
        if result:
            rule_was_triggered = True
            if stop_on_first_trigger:
                if debug:
                    logs.enable_debug(False)
                return True

    if debug:
        logs.enable_debug(False)
    return rule_was_triggered


def run(rule, defined_variables, defined_actions):
    """
    Execute a single rule.

    Args:
        rule: Rule dictionary with 'conditions' and 'actions'
        defined_variables: Instance of BaseVariables subclass
        defined_actions: Instance of BaseActions subclass

    Returns:
        bool: True if rule was triggered
    """
    conditions, actions = rule['conditions'], rule['actions']
    rule_results = check_conditions_recursively(conditions, defined_variables)

    if isinstance(rule_results, pd.Series):
        rule_triggered = True in rule_results.values
    else:
        rule_triggered = rule_results

    if rule_triggered:
        logs.log_rule_result(True)
        do_actions(actions, defined_actions, results=rule_results)
        return True

    logs.log_rule_result(False, "conditions not met")
    return False


def check_conditions_recursively(conditions, defined_variables):
    match list(conditions.keys()):
        case ["not"]:
            inner_result = check_conditions_recursively(conditions["not"], defined_variables)
            result = ~inner_result
            logs.log_condition_group('not', bool(result))
            return result

        case ["all"]:
            result = True
            assert len(conditions['all']) >= 1
            # Always check all conditions in the case that we are operating on a dataframe
            for condition in conditions['all']:
                check_result = check_conditions_recursively(condition, defined_variables)
                result = result & check_result
            logs.log_condition_group('all', bool(result))
            return result

        case ["any"]:
            result = False
            assert len(conditions['any']) >= 1
            missing_variables = []
            for condition in conditions['any']:
                # Always check all conditions in the case that we are operating on a dataframe
                try:
                    check_result = check_conditions_recursively(condition, defined_variables)
                    result = check_result | result
                except KeyError as e:
                    missing_variables.append(e.args[0])
            if len(missing_variables) == len(conditions["any"]):
                # Raise a key error only if all conditions in an "any" condition result in a KeyError
                raise KeyError(", ".join(list(set(missing_variables))))
            logs.log_condition_group('any', bool(result))
            return result

        case keys:
            # help prevent errors - any and all can only be in the condition dict
            # if they're the only item
            assert not ('any' in keys or 'all' in keys)
            return check_condition(conditions, defined_variables)

def check_condition(condition, defined_variables):
    """ Checks a single rule condition - the condition will be made up of
    variables, values, and the comparison operator. The defined_variables
    object must have a variable defined for any variables in this condition.
    """
    field, op, value = condition['field'], condition['operator'], condition['value']
    params = condition.get("params")
    operator_type = _get_variable_value(defined_variables, field, params)
    result = _do_operator_comparison(operator_type, op, value)
    logs.log_condition_result(field, op, value, bool(result))
    return result

def _get_variable_value(defined_variables, name, params=None):
    """ Call the function provided on the defined_variables object with the
    given name (raise exception if that doesn't exist) and casts it to the
    specified type.

    Returns an instance of operators.BaseType
    """
    method = getattr(defined_variables, name, _MISSING)
    if method is _MISSING:
        raise AssertionError(
            f"Variable {name} is not defined in class {defined_variables.__class__.__name__}"
        )
    val = method(params) if params else method()
    return method.field_type(val)

def _do_operator_comparison(operator_type, operator_name, comparison_value):
    """ Finds the method on the given operator_type and compares it to the
    given comparison_value.

    operator_type should be an instance of operators.BaseType
    comparison_value is whatever python type to compare to
    returns a bool
    """
    method = getattr(operator_type, operator_name, _MISSING)
    if method is _MISSING:
        raise AssertionError(
            f"Operator {operator_name} does not exist for type {operator_type.__class__.__name__}"
        )
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)


def do_actions(actions, defined_actions, results=None):
    for action in actions:
        normalized = normalize_action(action)
        method_name = normalized['action']
        params = normalized['params']
        method = getattr(defined_actions, method_name, _MISSING)
        if method is _MISSING:
            raise AssertionError(
                f"Action {method_name} is not defined in class {defined_actions.__class__.__name__}"
            )
        logs.log_action_execution(method_name, params if params else None)
        method(**params, results=results)
