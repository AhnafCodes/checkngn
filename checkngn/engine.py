from .fields import FIELD_NO_INPUT
from . import logs
from .utils import normalize_action
from .exceptions import (
    RuleValidationError,
    MissingVariableError,
    UndefinedOperatorError,
    UndefinedActionError,
)
import pandas as pd

# Sentinel for missing attributes
_MISSING = object()


def _coerce_bool(result):
    """ Coerce a condition result to a scalar bool for logging/branching.

    ``DataframeType`` operators return a pandas Series; calling ``bool()`` on a
    multi-element Series raises ``ValueError: The truth value of a Series is
    ambiguous``. Treat a Series as truthy if any element is truthy.
    """
    if isinstance(result, pd.Series):
        return bool(result.any())
    return bool(result)


def validate_rules(rule_list):
    """ Fail fast with a helpful error if rules are structurally malformed.

    Catches missing ``conditions``/``actions`` keys up front instead of raising
    a raw ``KeyError`` deep inside condition evaluation.
    """
    if not isinstance(rule_list, (list, tuple)):
        raise RuleValidationError(
            f"rule_list must be a list of rule dicts, got {type(rule_list).__name__}"
        )
    for idx, rule in enumerate(rule_list):
        if not isinstance(rule, dict):
            raise RuleValidationError(
                f"Rule {idx} must be a dict, got {type(rule).__name__}"
            )
        for required_key in ("conditions", "actions"):
            if required_key not in rule:
                raise RuleValidationError(
                    f"Rule {idx} is missing required key '{required_key}'"
                )


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
    validate_rules(rule_list)

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
            # Use bitwise ~ for pandas Series (element-wise), logical not for
            # scalars (~True == -2, which is truthy and would be wrong here).
            if isinstance(inner_result, pd.Series):
                result = ~inner_result
            else:
                result = not inner_result
            logs.log_condition_group('not', _coerce_bool(result))
            return result

        case ["all"]:
            result = True
            if len(conditions['all']) < 1:
                raise RuleValidationError("'all' block must contain at least one condition")
            # Always check all conditions in the case that we are operating on a dataframe
            for condition in conditions['all']:
                check_result = check_conditions_recursively(condition, defined_variables)
                result = result & check_result
            logs.log_condition_group('all', _coerce_bool(result))
            return result

        case ["any"]:
            result = False
            if len(conditions['any']) < 1:
                raise RuleValidationError("'any' block must contain at least one condition")
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
            logs.log_condition_group('any', _coerce_bool(result))
            return result

        case keys:
            # help prevent errors - any and all can only be in the condition dict
            # if they're the only item
            if 'any' in keys or 'all' in keys:
                raise RuleValidationError(
                    "'any'/'all' must be the only key in a condition group"
                )
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
    logs.log_condition_result(field, op, value, _coerce_bool(result))
    return result

def _get_variable_value(defined_variables, name, params=None):
    """ Call the function provided on the defined_variables object with the
    given name (raise exception if that doesn't exist) and casts it to the
    specified type.

    Returns an instance of operators.BaseType
    """
    method = getattr(defined_variables, name, _MISSING)
    if method is _MISSING:
        raise MissingVariableError(
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
        raise UndefinedOperatorError(
            f"Operator {operator_name} does not exist for type {operator_type.__class__.__name__}"
        )
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)


def do_actions(actions, defined_actions, results=None):
    for action in actions:
        # Normalize internally so callers can pass dict, list/tuple, or string
        # action formats without pre-processing (fulfils the documented contract).
        normalized = normalize_action(action)
        method_name = normalized['action']
        params = normalized.get('params') or {}
        method = getattr(defined_actions, method_name, _MISSING)
        if method is _MISSING:
            raise UndefinedActionError(
                f"Action {method_name} is not defined in class {defined_actions.__class__.__name__}"
            )
        # Only allow methods explicitly registered with @rule_action to be
        # invoked from rule data, so arbitrary methods can't be called.
        if not getattr(method, 'is_rule_action', False):
            raise UndefinedActionError(
                f"Action {method_name} is not a registered rule action on "
                f"{defined_actions.__class__.__name__} (decorate it with @rule_action)"
            )
        logs.log_action_execution(method_name, params if params else None)
        method(**params, results=results)
