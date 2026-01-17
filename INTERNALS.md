# checkngn - Internal Architecture Guide

This guide explains how the `checkngn` library works internally, covering each component and how they interact to provide a flexible rule engine.

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Components](#core-components)
   - [fields.py - Field Type Constants](#fieldspy---field-type-constants)
   - [operators.py - Type System & Operators](#operatorspy---type-system--operators)
   - [variables.py - Variable Definitions](#variablespy---variable-definitions)
   - [actions.py - Action Definitions](#actionspy---action-definitions)
   - [engine.py - Rule Execution Engine](#enginepy---rule-execution-engine)
   - [utils.py - Utility Functions](#utilspy---utility-functions)
4. [Data Flow](#data-flow)
5. [Rule Structure](#rule-structure)
6. [Execution Walkthrough](#execution-walkthrough)
7. [Decorator Pattern Deep Dive](#decorator-pattern-deep-dive)
8. [Extending the Library](#extending-the-library)

---

## Overview

The `checkngn` library is a Python DSL (Domain Specific Language) for defining and executing business rules. It allows you to:

- Define **variables** that extract data from your domain objects
- Define **actions** that execute when rules match
- Write **rules** as JSON/dict structures with conditions and actions
- Execute rules against your data

The library separates the "what to check" (variables), "how to check" (operators), and "what to do" (actions) into distinct, composable components.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Rule Definition (JSON/dict)                     │
│  {                                                                          │
│    "conditions": {"all": [{"field": "age", "operator": "greater_than", ...}]}│
│    "actions": [{"action": "send_email", "params": {...}}]                     │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            engine.py (Orchestrator)                          │
│  ┌─────────────┐    ┌──────────────────────┐    ┌─────────────────┐        │
│  │  run_all()  │───▶│ check_conditions_    │───▶│  do_actions()   │        │
│  │   run()     │    │   recursively()      │    │                 │        │
│  └─────────────┘    └──────────────────────┘    └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
          │                       │                         │
          │                       ▼                         ▼
          │         ┌─────────────────────────┐   ┌─────────────────────┐
          │         │     variables.py        │   │     actions.py      │
          │         │  ┌───────────────────┐  │   │  ┌───────────────┐  │
          │         │  │  BaseVariables    │  │   │  │  BaseActions  │  │
          │         │  │  @rule_variable   │  │   │  │  @rule_action │  │
          │         │  └───────────────────┘  │   │  └───────────────┘  │
          │         └─────────────────────────┘   └─────────────────────┘
          │                       │
          │                       ▼
          │         ┌─────────────────────────┐
          │         │     operators.py        │
          │         │  ┌───────────────────┐  │
          │         │  │  StringType       │  │
          │         │  │  NumericType      │  │
          │         │  │  BooleanType      │  │
          │         │  │  SelectType       │  │
          │         │  │  DataframeType    │  │
          │         │  └───────────────────┘  │
          │         └─────────────────────────┘
          │                       │
          │                       ▼
          │         ┌─────────────────────────┐
          │         │      fields.py          │
          │         │  FIELD_TEXT             │
          │         │  FIELD_NUMERIC          │
          │         │  FIELD_NO_INPUT         │
          │         │  FIELD_SELECT           │
          │         └─────────────────────────┘
          │
          └──────────────────────────────────────────────────────────────────┐
                                                                             │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              utils.py                                        │
│  export_rule_data() - Exports schema for UI/client consumption              │
│  fn_name_to_pretty_label() - Converts function names to labels              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### fields.py - Field Type Constants

**Purpose:** Defines constants that identify what type of input an operator expects.

```python
FIELD_TEXT = 'text'
FIELD_NUMERIC = 'numeric'
FIELD_NO_INPUT = 'none'
FIELD_SELECT = 'select'
FIELD_SELECT_MULTIPLE = 'select_multiple'
FIELD_DATAFRAME = 'dataframe'
```

**Why it exists:** When building a UI for rule configuration, you need to know what kind of input widget to show. These constants tell the UI:
- `FIELD_TEXT` → Show a text input
- `FIELD_NUMERIC` → Show a number input
- `FIELD_NO_INPUT` → No input needed (e.g., `is_true`, `non_empty`)
- `FIELD_SELECT` → Show a dropdown
- `FIELD_SELECT_MULTIPLE` → Show a multi-select

---

### operators.py - Type System & Operators

**Purpose:** Defines the type system and comparison operators for rule conditions.

#### Key Classes

**`BaseType`** - Abstract base class for all types:

```python
class BaseType(object):
    __slots__ = ('value',)  # Memory optimization

    def __init__(self, value):
        self.value = self._assert_valid_value_and_cast(value)

    def _assert_valid_value_and_cast(self, value):
        raise NotImplementedError()

    @classmethod
    @cache  # Results are cached for performance
    def get_all_operators(cls):
        # Uses introspection to find all methods decorated with @type_operator
        methods = inspect.getmembers(cls)
        return [{'name': m[0], 'label': m[1].label, 'input_type': m[1].input_type}
                for m in methods if getattr(m[1], 'is_operator', False)]
```

**Type Classes** - Each handles a specific data type:

| Class | Purpose | Example Operators |
|-------|---------|-------------------|
| `StringType` | String comparisons | `equal_to`, `contains`, `matches_regex`, `starts_with` |
| `NumericType` | Numeric comparisons | `equal_to`, `greater_than`, `less_than` |
| `BooleanType` | Boolean checks | `is_true`, `is_false` |
| `SelectType` | List membership | `contains`, `does_not_contain` |
| `SelectMultipleType` | Set operations | `contains_all`, `shares_at_least_one_element_with` |
| `DataframeType` | Pandas operations | `exists`, `not_exists` |
| `GenericType` | Any value | `equal_to` |

#### The `@type_operator` Decorator

This decorator marks a method as an operator and handles type validation:

```python
def type_operator(input_type, label=None, assert_type_for_arguments=True):
    def wrapper(func):
        func.is_operator = True  # Marker for introspection
        func.label = label or fn_name_to_pretty_label(func.__name__)
        func.input_type = input_type

        @wraps(func)
        def inner(self, *args, **kwargs):
            if assert_type_for_arguments:
                # Validate and cast arguments using the type's validation
                args = [self._assert_valid_value_and_cast(arg) for arg in args]
                kwargs = {k: self._assert_valid_value_and_cast(v) for k, v in kwargs.items()}
            return func(self, *args, **kwargs)
        return inner
    return wrapper
```

**Example usage:**

```python
@export_type
class NumericType(BaseType):
    __slots__ = ()
    name = "numeric"

    def _assert_valid_value_and_cast(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        raise AssertionError(f"Value {value} is not a number")

    @type_operator(FIELD_NUMERIC)
    def greater_than(self, other_numeric):
        return self.value > other_numeric  # other_numeric is already cast to float
```

#### The `@export_type` Decorator

Marks a type class for inclusion in `export_rule_data()`:

```python
def export_type(cls):
    cls.export_in_rule_data = True  # Simple marker
    return cls
```

---

### variables.py - Variable Definitions

**Purpose:** Provides the base class and decorators for defining rule variables.

#### `BaseVariables` Class

```python
class BaseVariables(object):
    @classmethod
    @cache
    def get_all_variables(cls):
        methods = inspect.getmembers(cls)
        return [{'name': m[0],
                 'label': m[1].label,
                 'field_type': m[1].field_type.name,
                 'options': m[1].options}
                for m in methods if getattr(m[1], 'is_rule_variable', False)]
```

#### The `@rule_variable` Decorator

Links a method to a type class:

```python
def rule_variable(field_type, label=None, options=None):
    def wrapper(func):
        # Validate that field_type is a BaseType subclass
        if not (type(field_type) == type and issubclass(field_type, BaseType)):
            raise AssertionError(f"{field_type} is not instance of BaseType")

        func.field_type = field_type      # e.g., NumericType
        func.is_rule_variable = True      # Marker for introspection
        func.label = label or fn_name_to_pretty_label(func.__name__)
        func.options = options or []
        return func
    return wrapper
```

#### Convenience Decorators

For cleaner syntax, helper decorators are provided:

```python
def numeric_rule_variable(label=None):
    return rule_variable(NumericType, label=label)

def string_rule_variable(label=None):
    return rule_variable(StringType, label=label)

def boolean_rule_variable(label=None):
    return rule_variable(BooleanType, label=label)

# ... etc
```

**Usage comparison:**

```python
# Verbose way
@rule_variable(NumericType)
def age(self):
    return self.person.age

# Cleaner way
@numeric_rule_variable()
def age(self):
    return self.person.age
```

---

### actions.py - Action Definitions

**Purpose:** Provides the base class and decorator for defining rule actions.

#### `BaseActions` Class

```python
class BaseActions(object):
    @classmethod
    @cache
    def get_all_actions(cls):
        methods = inspect.getmembers(cls)
        return [{'name': m[0], 'label': m[1].label, 'params': m[1].params}
                for m in methods if getattr(m[1], 'is_rule_action', False)]
```

#### The `@rule_action` Decorator

```python
# Precomputed at module load for performance
_VALID_FIELDS = frozenset(
    getattr(fields, f) for f in dir(fields) if f.startswith("FIELD_")
)

def rule_action(label=None, params=None):
    def wrapper(func):
        params_ = params
        # Convert dict format to list format
        if isinstance(params, dict):
            params_ = [{'label': fn_name_to_pretty_label(name),
                        'name': name,
                        'fieldType': field_type}
                       for name, field_type in params.items()]

        _validate_action_parameters(func, params_)
        func.is_rule_action = True
        func.label = label or fn_name_to_pretty_label(func.__name__)
        func.params = params_
        return func
    return wrapper
```

**Usage:**

```python
class MyActions(BaseActions):
    @rule_action(params={'discount_percent': FIELD_NUMERIC})
    def apply_discount(self, discount_percent, results=None):
        self.order.discount = discount_percent
```

---

### engine.py - Rule Execution Engine

**Purpose:** The core orchestrator that evaluates conditions and executes actions.

#### Entry Points

**`run_all()`** - Execute multiple rules:

```python
def run_all(rule_list, defined_variables, defined_actions, stop_on_first_trigger=False):
    rule_was_triggered = False
    for rule in rule_list:
        result = run(rule, defined_variables, defined_actions)
        if result:
            rule_was_triggered = True
            if stop_on_first_trigger:
                return True
    return rule_was_triggered
```

**`run()`** - Execute a single rule:

```python
def run(rule, defined_variables, defined_actions):
    conditions, actions = rule['conditions'], rule['actions']
    rule_results = check_conditions_recursively(conditions, defined_variables)

    # Handle both scalar and DataFrame results
    if isinstance(rule_results, pd.Series):
        rule_triggered = True in rule_results.values
    else:
        rule_triggered = rule_results

    if rule_triggered:
        do_actions(actions, defined_actions, results=rule_results)
        return True
    return False
```

#### Condition Evaluation

**`check_conditions_recursively()`** - Uses Python 3.10+ match statement:

```python
def check_conditions_recursively(conditions, defined_variables):
    match list(conditions.keys()):
        case ["not"]:
            # Negate the nested condition
            return ~check_conditions_recursively(conditions["not"], defined_variables)

        case ["all"]:
            # AND logic - all conditions must be true
            result = True
            for condition in conditions['all']:
                check_result = check_conditions_recursively(condition, defined_variables)
                result = result & check_result  # Bitwise AND works for bool and pandas
            return result

        case ["any"]:
            # OR logic - at least one condition must be true
            result = False
            missing_variables = []
            for condition in conditions['any']:
                try:
                    check_result = check_conditions_recursively(condition, defined_variables)
                    result = check_result | result  # Bitwise OR
                except KeyError as e:
                    missing_variables.append(e.args[0])
            # Only raise if ALL conditions failed with KeyError
            if len(missing_variables) == len(conditions["any"]):
                raise KeyError(", ".join(list(set(missing_variables))))
            return result

        case keys:
            # Leaf node - actual condition to check
            assert not ('any' in keys or 'all' in keys)
            return check_condition(conditions, defined_variables)
```

**`check_condition()`** - Evaluates a single condition:

```python
def check_condition(condition, defined_variables):
    field, op, value = condition['field'], condition['operator'], condition['value']
    params = condition.get("params")

    # Get the variable value wrapped in its type class
    operator_type = _get_variable_value(defined_variables, field, params)

    # Execute the operator
    return _do_operator_comparison(operator_type, op, value)
```

#### Helper Functions

**`_get_variable_value()`** - Retrieves and wraps a variable:

```python
_MISSING = object()  # Sentinel for missing attributes

def _get_variable_value(defined_variables, name, params=None):
    method = getattr(defined_variables, name, _MISSING)
    if method is _MISSING:
        raise AssertionError(
            f"Variable {name} is not defined in class {defined_variables.__class__.__name__}"
        )
    val = method(params) if params else method()
    return method.field_type(val)  # Wrap in type class (e.g., NumericType(val))
```

**`_do_operator_comparison()`** - Executes an operator:

```python
def _do_operator_comparison(operator_type, operator_name, comparison_value):
    method = getattr(operator_type, operator_name, _MISSING)
    if method is _MISSING:
        raise AssertionError(
            f"Operator {operator_name} does not exist for type {operator_type.__class__.__name__}"
        )
    # Some operators (like is_true) don't need input
    if getattr(method, 'input_type', '') == FIELD_NO_INPUT:
        return method()
    return method(comparison_value)
```

**`normalize_action()`** - Normalizes action formats to standard dict:

```python
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
```

**`do_actions()`** - Executes triggered actions:

```python
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
        method(**params, results=results)  # Pass results for DataFrame filtering
```

---

### utils.py - Utility Functions

**`fn_name_to_pretty_label()`** - Converts snake_case to Title Case:

```python
def fn_name_to_pretty_label(name):
    return ' '.join(w.title() for w in name.split('_'))
    # "current_inventory" → "Current Inventory"
```

**`export_rule_data()`** - Exports schema for UI consumption:

```python
def export_rule_data(variables, actions):
    from . import operators

    actions_data = actions.get_all_actions()
    variables_data = variables.get_all_variables()

    # Collect all operators from exported types
    variable_type_operators = {}
    for name, variable_type in inspect.getmembers(operators):
        if getattr(variable_type, 'export_in_rule_data', False):
            variable_type_operators[variable_type.name] = variable_type.get_all_operators()

    return {
        "variables": variables_data,
        "actions": actions_data,
        "variable_type_operators": variable_type_operators
    }
```

---

## Data Flow

Here's how data flows through the system when a rule is executed:

```
1. User defines variables class:
   ┌─────────────────────────────────────────┐
   │ class OrderVariables(BaseVariables):    │
   │     @numeric_rule_variable()            │
   │     def total_amount(self):             │
   │         return self.order.total         │
   └─────────────────────────────────────────┘
                      │
                      ▼
2. User defines actions class:
   ┌─────────────────────────────────────────┐
   │ class OrderActions(BaseActions):        │
   │     @rule_action(params={...})          │
   │     def apply_discount(self, ...):      │
   │         self.order.discount = ...       │
   └─────────────────────────────────────────┘
                      │
                      ▼
3. User defines rule:
   ┌─────────────────────────────────────────┐
   │ rule = {                                │
   │   "conditions": {                       │
   │     "all": [{                           │
   │       "field": "total_amount",          │
   │       "operator": "greater_than",       │
   │       "value": 100                      │
   │     }]                                  │
   │   },                                    │
   │   "actions": [{                         │
   │     "action": "apply_discount",         │
   │     "params": {"percent": 10}           │
   │   }]                                    │
   │ }                                       │
   └─────────────────────────────────────────┘
                      │
                      ▼
4. Engine processes:
   ┌─────────────────────────────────────────┐
   │ run(rule, variables_instance,           │
   │     actions_instance)                   │
   │                                         │
   │ a) Parse conditions                     │
   │ b) For each condition:                  │
   │    - Get variable value (150.00)        │
   │    - Wrap in type: NumericType(150.00)  │
   │    - Call operator: .greater_than(100)  │
   │    - Returns: True                      │
   │ c) Combine results with all/any/not     │
   │ d) If True, execute actions             │
   └─────────────────────────────────────────┘
```

---

## Rule Structure

Rules are dictionaries with this structure:

```python
{
    "conditions": {
        # One of: "all", "any", "not", or a leaf condition
        "all": [
            # Nested conditions (can be all/any/not or leaf)
            {
                "field": "variable_name",     # Method name on variables class
                "operator": "operator_name",  # Method name on type class
                "value": <comparison_value>,  # Value to compare against
                "params": {}                  # Optional params for variable
            },
            {
                "any": [
                    # More nested conditions...
                ]
            }
        ]
    },
    "actions": [
        {
            "action": "action_name",  # Method name on actions class
            "params": {               # Parameters passed to action
                "param_name": value
            }
        }
    ]
}
```

**Condition operators:**

| Operator | Behavior |
|----------|----------|
| `all` | All nested conditions must be True (AND) |
| `any` | At least one nested condition must be True (OR) |
| `not` | Negates the nested condition |

---

## Execution Walkthrough

Let's trace through a complete example:

```python
# 1. Define domain object
order = {"customer": "John", "total": 150, "items": 3}

# 2. Define variables
class OrderVariables(BaseVariables):
    def __init__(self, order):
        self.order = order

    @numeric_rule_variable()
    def order_total(self):
        return self.order["total"]

    @numeric_rule_variable()
    def item_count(self):
        return self.order["items"]

# 3. Define actions
class OrderActions(BaseActions):
    def __init__(self, order):
        self.order = order

    @rule_action(params={"percent": FIELD_NUMERIC})
    def apply_discount(self, percent, results=None):
        self.order["discount"] = percent

# 4. Define rule
rule = {
    "conditions": {
        "all": [
            {"field": "order_total", "operator": "greater_than", "value": 100},
            {"field": "item_count", "operator": "greater_than_or_equal_to", "value": 2}
        ]
    },
    "actions": [
        {"action": "apply_discount", "params": {"percent": 15}}
    ]
}

# 5. Execute
from checkngn import run_all
run_all([rule], OrderVariables(order), OrderActions(order))
```

**Execution trace:**

```
run_all([rule], variables, actions)
└── run(rule, variables, actions)
    ├── conditions = {"all": [...]}
    ├── check_conditions_recursively(conditions, variables)
    │   └── match ["all"]
    │       ├── check_conditions_recursively(condition[0], variables)
    │       │   └── match ["field", "operator", "value"]  # leaf
    │       │       └── check_condition({"field": "order_total", ...}, variables)
    │       │           ├── _get_variable_value(variables, "order_total")
    │       │           │   ├── method = variables.order_total
    │       │           │   ├── val = method() → 150
    │       │           │   └── return NumericType(150)
    │       │           └── _do_operator_comparison(NumericType(150), "greater_than", 100)
    │       │               └── NumericType(150).greater_than(100) → True
    │       ├── check_conditions_recursively(condition[1], variables)
    │       │   └── ... → True
    │       └── return True & True → True
    ├── rule_triggered = True
    └── do_actions([{"action": "apply_discount", ...}], actions, results=True)
        └── actions.apply_discount(percent=15, results=True)
            └── order["discount"] = 15
```

---

## Decorator Pattern Deep Dive

The library uses decorators extensively. Here's how they work together:

### Variable Registration Flow

```python
@numeric_rule_variable(label="Total Order Amount")
def order_total(self):
    return self.order.total
```

Expands to:

```python
def order_total(self):
    return self.order.total

# After decoration:
order_total.field_type = NumericType  # Type class for wrapping values
order_total.is_rule_variable = True   # Marker for get_all_variables()
order_total.label = "Total Order Amount"
order_total.options = []
```

### Operator Registration Flow

```python
@type_operator(FIELD_NUMERIC, label="Greater Than")
def greater_than(self, other):
    return self.value > other
```

Expands to:

```python
def greater_than(self, other):
    return self.value > other

# After decoration (simplified):
def greater_than_wrapper(self, other):
    other = self._assert_valid_value_and_cast(other)  # Validate input
    return original_greater_than(self, other)

greater_than_wrapper.is_operator = True
greater_than_wrapper.label = "Greater Than"
greater_than_wrapper.input_type = "numeric"
```

---

## Extending the Library

### Adding a Custom Type

```python
from checkngn.operators import BaseType, type_operator, export_type
from checkngn.fields import FIELD_TEXT

@export_type
class EmailType(BaseType):
    __slots__ = ()
    name = "email"

    def _assert_valid_value_and_cast(self, value):
        if not isinstance(value, str) or "@" not in value:
            raise AssertionError(f"Value {value} is not a valid email")
        return value.lower()

    @type_operator(FIELD_TEXT)
    def domain_equals(self, domain):
        return self.value.split("@")[1] == domain

    @type_operator(FIELD_NO_INPUT)
    def is_corporate(self):
        return not any(p in self.value for p in ["gmail", "yahoo", "hotmail"])
```

### Adding a Custom Variable

```python
from checkngn.variables import rule_variable

def email_rule_variable(label=None):
    return rule_variable(EmailType, label=label)

class CustomerVariables(BaseVariables):
    @email_rule_variable()
    def customer_email(self):
        return self.customer.email
```

### Using in Rules

```python
rule = {
    "conditions": {
        "all": [
            {"field": "customer_email", "operator": "domain_equals", "value": "company.com"},
            {"field": "customer_email", "operator": "is_corporate", "value": None}
        ]
    },
    "actions": [...]
}
```

---

## Performance Considerations

The library includes several optimizations:

1. **`__slots__`** on type classes - Reduces memory per instance
2. **`@cache`** on introspection methods - `get_all_operators()`, `get_all_actions()`, `get_all_variables()` are cached
3. **`_MISSING` sentinel** - Avoids creating closure functions for missing attribute checks
4. **`frozenset` for field validation** - O(1) lookup for valid field types
5. **f-strings** - Faster than `.format()` for error messages

---

## Summary

| Component | Responsibility |
|-----------|----------------|
| `fields.py` | Defines input type constants for UI |
| `operators.py` | Type system + comparison operators |
| `variables.py` | Maps domain data to typed values |
| `actions.py` | Defines executable actions |
| `engine.py` | Orchestrates rule evaluation |
| `utils.py` | Export schema + string utilities |

The library achieves flexibility through:
- **Decorators** for registration and metadata
- **Introspection** for discovering variables/actions/operators
- **Type wrapping** for type-safe comparisons
- **Recursive evaluation** for complex nested conditions