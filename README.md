# checkngn

A lightweight Python DSL for setting up business intelligence rules that can be configured without code.
(NOTE Disclaimer: Fork of Venmo-Business-Rules and CDICS-business-rules-enhanced, with simple updates like project setup and logging)

[![CI](https://github.com/AhnafCodes/business-rules/actions/workflows/automatic-test.yml/badge.svg)](https://github.com/AhnafCodes/business-rules/actions/workflows/automatic-test.yml)

## Overview

As a software system grows in complexity and usage, it can become burdensome if every change to the logic/behavior of the system also requires you to write and deploy new code. **checkngn** provides a simple interface allowing anyone to capture new rules and logic defining the behavior of a system, and a way to then process those rules on the backend.

Use cases:
- Marketing logic for customer/item discount eligibility
- Automated emails based on user state or event sequences
- Data validation rules for pandas DataFrames
- Any condition-action workflow

## Installation

```bash
# Using pip
pip install checkngn

# Using uv (faster)
uv pip install checkngn
```

**Requirements:** Python 3.14+

## Quick Start

```python
from checkngn import run_all
from checkngn.variables import BaseVariables, numeric_rule_variable, string_rule_variable
from checkngn.actions import BaseActions, rule_action
from checkngn.fields import FIELD_NUMERIC

# 1. Define variables
class ProductVariables(BaseVariables):
    def __init__(self, product):
        self.product = product

    @numeric_rule_variable()
    def current_inventory(self):
        return self.product['inventory']

    @string_rule_variable()
    def product_name(self):
        return self.product['name']

# 2. Define actions
class ProductActions(BaseActions):
    def __init__(self, product):
        self.product = product

    @rule_action(params={"sale_percentage": FIELD_NUMERIC})
    def put_on_sale(self, sale_percentage, results=None):
        self.product['price'] *= (1.0 - sale_percentage)

# 3. Define rules
rules = [
    {
        "conditions": {
            "all": [
                {"name": "current_inventory", "operator": "greater_than", "value": 20},
                {"name": "product_name", "operator": "contains", "value": "Widget"}
            ]
        },
        "actions": [
            {"name": "put_on_sale", "params": {"sale_percentage": 0.25}}
        ]
    }
]

# 4. Run rules
product = {'name': 'Super Widget', 'inventory': 50, 'price': 100.0}
run_all(rules, ProductVariables(product), ProductActions(product))
print(product['price'])  # 75.0
```

## Debug Mode

Enable "check engine light" debug output to see rule evaluation:

```python
run_all(rules, variables, actions, debug=True)
```

Output:
```
🔧 [checkngn] Evaluating rule 1/1
🔧 [checkngn] ✓ condition 'current_inventory greater_than 20' → True
🔧 [checkngn] ✓ condition 'product_name contains Widget' → True
🔧 [checkngn] ✓ 'all' block → True
🔧 [checkngn] Rule triggered ✓
🔧 [checkngn] Executing action 'put_on_sale' with {'sale_percentage': 0.25}
```

Or enable globally:
```python
from checkngn import enable_debug
enable_debug(True)
```

## Usage Guide

### 1. Define Variables

Variables represent values in your system. You define all available variables for a certain kind of object, then dynamically set conditions and thresholds for those.

```python
from checkngn.variables import (
    BaseVariables,
    numeric_rule_variable,
    string_rule_variable,
    boolean_rule_variable,
    select_rule_variable,
    select_multiple_rule_variable,
    dataframe_rule_variable
)

class ProductVariables(BaseVariables):
    def __init__(self, product):
        self.product = product

    @numeric_rule_variable()
    def current_inventory(self):
        return self.product.current_inventory

    @numeric_rule_variable(label='Days until expiration')
    def expiration_days(self):
        return (self.product.expiration_date - datetime.date.today()).days

    @string_rule_variable()
    def current_month(self):
        return datetime.datetime.now().strftime("%B")

    @select_rule_variable(options=['Electronics', 'Clothing', 'Food'])
    def category(self):
        return self.product.category
```

### 2. Define Actions

Actions are executed when conditions are triggered.

```python
from checkngn.actions import BaseActions, rule_action
from checkngn.fields import FIELD_NUMERIC, FIELD_TEXT, FIELD_SELECT

class ProductActions(BaseActions):
    def __init__(self, product):
        self.product = product

    @rule_action(params={"sale_percentage": FIELD_NUMERIC})
    def put_on_sale(self, sale_percentage, results=None):
        self.product.price *= (1.0 - sale_percentage)
        self.product.save()

    @rule_action(params={"number_to_order": FIELD_NUMERIC})
    def order_more(self, number_to_order, results=None):
        ProductOrder.objects.create(
            product_id=self.product.id,
            quantity=number_to_order
        )
```

### 3. Build Rules

Rules are JSON/dict structures with `conditions` and `actions`:

```python
rules = [
    # expiration_days < 5 AND current_inventory > 20
    {
        "conditions": {
            "all": [
                {"name": "expiration_days", "operator": "less_than", "value": 5},
                {"name": "current_inventory", "operator": "greater_than", "value": 20}
            ]
        },
        "actions": [
            {"name": "put_on_sale", "params": {"sale_percentage": 0.25}}
        ]
    },
    # current_inventory < 5 OR current_month = "December"
    {
        "conditions": {
            "any": [
                {"name": "current_inventory", "operator": "less_than", "value": 5},
                {"name": "current_month", "operator": "equal_to", "value": "December"}
            ]
        },
        "actions": [
            {"name": "order_more", "params": {"number_to_order": 40}}
        ]
    },
    # NOT (current_inventory > 100)
    {
        "conditions": {
            "not": {
                "name": "current_inventory", "operator": "greater_than", "value": 100
            }
        },
        "actions": [
            {"name": "order_more", "params": {"number_to_order": 10}}
        ]
    }
]
```

**Condition operators:**
- `all` - All conditions must be True (AND)
- `any` - At least one condition must be True (OR)
- `not` - Negates the condition

### 4. Export Rule Schema

Export available variables, operators, and actions for UI generation:

```python
from checkngn import export_rule_data

schema = export_rule_data(ProductVariables, ProductActions)
```

Returns:
```python
{
    "variables": [
        {"name": "current_inventory", "label": "Current Inventory", "field_type": "numeric", "options": []},
        {"name": "expiration_days", "label": "Days until expiration", "field_type": "numeric", "options": []},
        ...
    ],
    "actions": [
        {"name": "put_on_sale", "label": "Put On Sale", "params": [{"name": "sale_percentage", "fieldType": "numeric", "label": "Sale Percentage"}]},
        ...
    ],
    "variable_type_operators": {
        "numeric": [
            {"name": "equal_to", "label": "Equal To", "input_type": "numeric"},
            {"name": "greater_than", "label": "Greater Than", "input_type": "numeric"},
            ...
        ],
        "string": [...],
        ...
    }
}
```

### 5. Run Rules

```python
from checkngn import run_all

for product in products:
    run_all(
        rule_list=rules,
        defined_variables=ProductVariables(product),
        defined_actions=ProductActions(product),
        stop_on_first_trigger=True,  # Stop after first matching rule
        debug=False  # Set True for debug output
    )
```

## Variable Types & Operators

| Decorator | Type | Operators |
|-----------|------|-----------|
| `@numeric_rule_variable()` | int, float | `equal_to`, `greater_than`, `less_than`, `greater_than_or_equal_to`, `less_than_or_equal_to` |
| `@string_rule_variable()` | str | `equal_to`, `equal_to_case_insensitive`, `starts_with`, `ends_with`, `contains`, `matches_regex`, `non_empty` |
| `@boolean_rule_variable()` | bool | `is_true`, `is_false` |
| `@select_rule_variable()` | list | `contains`, `does_not_contain` |
| `@select_multiple_rule_variable()` | list | `contains_all`, `is_contained_by`, `shares_at_least_one_element_with`, `shares_exactly_one_element_with`, `shares_no_elements_with` |
| `@dataframe_rule_variable()` | pd.DataFrame/Series | `exists`, `not_exists` |

## Contributing

```bash
# Clone the repo
git clone https://github.com/AhnafCodes/business-rules.git
cd business-rules

# Install dev dependencies
pip install -e ".[dev]"
# or with uv
uv pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

See [INTERNALS.md](INTERNALS.md) for detailed architecture documentation.

## License

MIT
