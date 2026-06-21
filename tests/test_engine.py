import pandas as pd

from checkngn import run_all
from checkngn.engine import (
    do_actions,
    check_conditions_recursively,
    validate_rules,
)
from checkngn.variables import (
    BaseVariables,
    numeric_rule_variable,
    boolean_rule_variable,
    select_multiple_rule_variable,
    dataframe_rule_variable,
)
from checkngn.actions import BaseActions, rule_action
from checkngn.exceptions import (
    RuleValidationError,
    MissingVariableError,
    UndefinedOperatorError,
    UndefinedActionError,
)
from . import TestCase


class _Variables(BaseVariables):
    def __init__(self, obj=None):
        self.obj = obj or {}

    @numeric_rule_variable()
    def current_inventory(self):
        return self.obj.get('inventory', 0)

    @boolean_rule_variable()
    def is_active(self):
        return self.obj.get('active', False)

    @select_multiple_rule_variable()
    def tags(self):
        return self.obj.get('tags', [])

    @dataframe_rule_variable()
    def prices(self):
        return pd.Series([1.0, None, 3.0])


class _Actions(BaseActions):
    def __init__(self):
        self.calls = []

    @rule_action(params={'percent': 'numeric'})
    def put_on_sale(self, percent=0, results=None):
        self.calls.append(('put_on_sale', percent))

    @rule_action()
    def notify_manager(self, results=None):
        self.calls.append(('notify_manager', None))

    @rule_action(params={'quantity': 'numeric'})
    def order_more(self, quantity=0, results=None):
        self.calls.append(('order_more', quantity))

    # NOT decorated as a rule action - must not be callable from rules.
    def dangerous(self, results=None):
        self.calls.append(('dangerous', None))


def _rule(conditions, actions):
    return [{'conditions': conditions, 'actions': actions}]


class ValidateRulesTests(TestCase):
    def test_missing_conditions_key(self):
        with self.assertRaisesRegex(RuleValidationError, "missing required key 'conditions'"):
            validate_rules([{'actions': []}])

    def test_missing_actions_key(self):
        with self.assertRaisesRegex(RuleValidationError, "missing required key 'actions'"):
            validate_rules([{'conditions': {}}])

    def test_non_list_rules(self):
        with self.assertRaisesRegex(RuleValidationError, "must be a list"):
            validate_rules({'conditions': {}, 'actions': []})

    def test_run_all_validates_up_front(self):
        with self.assertRaises(RuleValidationError):
            run_all([{'actions': []}], _Variables(), _Actions())


class ConditionLogicTests(TestCase):
    def test_simple_condition_triggers(self):
        actions = _Actions()
        rules = _rule(
            {'all': [{'field': 'current_inventory', 'operator': 'greater_than', 'value': 10}]},
            [{'action': 'notify_manager', 'params': {}}],
        )
        triggered = run_all(rules, _Variables({'inventory': 20}), actions)
        self.assertTrue(triggered)
        self.assertEqual(actions.calls, [('notify_manager', None)])

    def test_not_block_scalar_true(self):
        # ~True == -2 (truthy) was the old bug; logical not must be used.
        conditions = {'not': {'field': 'is_active', 'operator': 'is_true', 'value': ''}}
        result = check_conditions_recursively(conditions, _Variables({'active': True}))
        self.assertFalse(result)

    def test_not_block_scalar_false(self):
        conditions = {'not': {'field': 'is_active', 'operator': 'is_true', 'value': ''}}
        result = check_conditions_recursively(conditions, _Variables({'active': False}))
        self.assertTrue(result)

    def test_empty_all_block_raises(self):
        with self.assertRaises(RuleValidationError):
            check_conditions_recursively({'all': []}, _Variables())

    def test_any_and_all_mixed_keys_raises(self):
        with self.assertRaises(RuleValidationError):
            check_conditions_recursively(
                {'all': [], 'field': 'x'}, _Variables()
            )

    def test_missing_variable_raises(self):
        with self.assertRaises(MissingVariableError):
            check_conditions_recursively(
                {'field': 'does_not_exist', 'operator': 'greater_than', 'value': 1},
                _Variables(),
            )

    def test_undefined_operator_raises(self):
        with self.assertRaises(UndefinedOperatorError):
            check_conditions_recursively(
                {'field': 'current_inventory', 'operator': 'no_such_op', 'value': 1},
                _Variables({'inventory': 5}),
            )


class DataframeTests(TestCase):
    def test_dataframe_condition_does_not_crash_logging(self):
        # Regression: bool(Series) raised ValueError in the logging layer,
        # even with debug disabled.
        result = check_conditions_recursively(
            {'field': 'prices', 'operator': 'exists', 'value': ''},
            _Variables(),
        )
        self.assertIsInstance(result, pd.Series)

    def test_dataframe_rule_triggers_and_runs(self):
        actions = _Actions()
        rules = _rule(
            {'all': [{'field': 'prices', 'operator': 'exists', 'value': ''}]},
            [{'action': 'notify_manager', 'params': {}}],
        )
        triggered = run_all(rules, _Variables(), actions, debug=True)
        self.assertTrue(triggered)
        self.assertEqual(actions.calls, [('notify_manager', None)])


class SelectMultipleTests(TestCase):
    def test_plain_string_list_value(self):
        # Regression: contains_all assumed [{'name': ...}] and crashed on strings.
        result = check_conditions_recursively(
            {'field': 'tags', 'operator': 'contains_all', 'value': ['a', 'b']},
            _Variables({'tags': ['a', 'b', 'c']}),
        )
        self.assertTrue(result)

    def test_structured_name_list_value(self):
        result = check_conditions_recursively(
            {'field': 'tags', 'operator': 'contains_all',
             'value': [{'name': 'a'}, {'name': 'b'}]},
            _Variables({'tags': ['a', 'b', 'c']}),
        )
        self.assertTrue(result)


class DoActionsTests(TestCase):
    def test_dict_format(self):
        actions = _Actions()
        do_actions([{'action': 'put_on_sale', 'params': {'percent': 25}}], actions)
        self.assertEqual(actions.calls, [('put_on_sale', 25)])

    def test_list_format(self):
        actions = _Actions()
        do_actions([['order_more', {'quantity': 10}]], actions)
        self.assertEqual(actions.calls, [('order_more', 10)])

    def test_string_format(self):
        actions = _Actions()
        do_actions(['notify_manager'], actions)
        self.assertEqual(actions.calls, [('notify_manager', None)])

    def test_dict_without_params(self):
        actions = _Actions()
        do_actions([{'action': 'notify_manager'}], actions)
        self.assertEqual(actions.calls, [('notify_manager', None)])

    def test_undefined_action_raises(self):
        with self.assertRaises(UndefinedActionError):
            do_actions(['no_such_action'], _Actions())

    def test_non_rule_action_method_is_blocked(self):
        # Security: an existing but undecorated method must not be invokable.
        actions = _Actions()
        with self.assertRaises(UndefinedActionError):
            do_actions(['dangerous'], actions)
        self.assertEqual(actions.calls, [])


class EndToEndMixedFormatTests(TestCase):
    def test_mixed_action_formats_in_one_rule(self):
        actions = _Actions()
        rules = _rule(
            {'all': [{'field': 'current_inventory', 'operator': 'greater_than', 'value': 5}]},
            [
                {'action': 'put_on_sale', 'params': {'percent': 25}},
                ['order_more', {'quantity': 10}],
                'notify_manager',
            ],
        )
        triggered = run_all(rules, _Variables({'inventory': 50}), actions)
        self.assertTrue(triggered)
        self.assertEqual(
            actions.calls,
            [('put_on_sale', 25), ('order_more', 10), ('notify_manager', None)],
        )
