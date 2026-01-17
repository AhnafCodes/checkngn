import inspect
from functools import wraps, cache
from .utils import fn_name_to_pretty_label
from .fields import FIELD_TEXT, FIELD_NUMERIC, FIELD_NO_INPUT, FIELD_SELECT, FIELD_SELECT_MULTIPLE, FIELD_DATAFRAME
import re
import pandas as pd

class BaseType(object):
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = self._assert_valid_value_and_cast(value)

    def _assert_valid_value_and_cast(self, value):
        raise NotImplementedError()

    @classmethod
    @cache
    def get_all_operators(cls):
        methods = inspect.getmembers(cls)
        return [{'name': m[0],
                 'label': m[1].label,
                 'input_type': m[1].input_type}
                for m in methods if getattr(m[1], 'is_operator', False)]

def export_type(cls):
    """ Decorator to expose the given class to checkngn.export_rule_data. """
    cls.export_in_rule_data = True
    return cls


def type_operator(input_type, label=None,
                  assert_type_for_arguments=True):
    """ Decorator to make a function into a type operator.

    - assert_type_for_arguments - if True this patches the operator function
      so that arguments passed to it will have _assert_valid_value_and_cast
      called on them to make type errors explicit.
    """
    def wrapper(func):
        func.is_operator = True
        func.label = label \
            or fn_name_to_pretty_label(func.__name__)
        func.input_type = input_type

        @wraps(func)
        def inner(self, *args, **kwargs):
            if assert_type_for_arguments:
                args = [self._assert_valid_value_and_cast(arg) for arg in args]
                kwargs = dict((k, self._assert_valid_value_and_cast(v))
                              for k, v in kwargs.items())
            return func(self, *args, **kwargs)
        return inner
    return wrapper

@export_type
class StringType(BaseType):
    __slots__ = ()

    name = "string"

    def _assert_valid_value_and_cast(self, value):
        value = value or ""
        if not isinstance(value, str):
            raise AssertionError(f"Value {value} is not a string")
        return value

    @type_operator(FIELD_TEXT)
    def equal_to(self, other_string):
        return self.value == other_string

    @type_operator(FIELD_TEXT, label="Equal To (case insensitive)")
    def equal_to_case_insensitive(self, other_string):
        return self.value.lower() == other_string.lower()

    @type_operator(FIELD_TEXT)
    def starts_with(self, other_string):
        return self.value.startswith(other_string)

    @type_operator(FIELD_TEXT)
    def ends_with(self, other_string):
        return self.value.endswith(other_string)

    @type_operator(FIELD_TEXT)
    def contains(self, other_string):
        return other_string in self.value

    @type_operator(FIELD_TEXT)
    def matches_regex(self, regex):
        return re.search(regex, self.value)

    @type_operator(FIELD_NO_INPUT)
    def non_empty(self):
        return bool(self.value)

@export_type
class NumericType(BaseType):
    __slots__ = ()

    name = "numeric"

    def _assert_valid_value_and_cast(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        # Allow strings that look like numbers
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        raise AssertionError(f"Value {value} is not a number")

    @type_operator(FIELD_NUMERIC)
    def equal_to(self, other_numeric):
        return abs(self.value - other_numeric) <= 0.000001

    @type_operator(FIELD_NUMERIC)
    def greater_than(self, other_numeric):
        return self.value > other_numeric

    @type_operator(FIELD_NUMERIC)
    def less_than(self, other_numeric):
        return self.value < other_numeric

    @type_operator(FIELD_NUMERIC)
    def greater_than_or_equal_to(self, other_numeric):
        return self.greater_than(other_numeric) or self.equal_to(other_numeric)

    @type_operator(FIELD_NUMERIC)
    def less_than_or_equal_to(self, other_numeric):
        return self.less_than(other_numeric) or self.equal_to(other_numeric)

@export_type
class BooleanType(BaseType):
    __slots__ = ()

    name = "boolean"

    def _assert_valid_value_and_cast(self, value):
        if type(value) is bool:
            return value
        raise AssertionError(f"Value {value} is not a boolean")

    @type_operator(FIELD_NO_INPUT)
    def is_true(self):
        return self.value

    @type_operator(FIELD_NO_INPUT)
    def is_false(self):
        return not self.value

@export_type
class SelectType(BaseType):
    __slots__ = ()

    name = "select"

    def _assert_valid_value_and_cast(self, value):
        if not hasattr(value, '__iter__'):
            raise AssertionError(f"Value {value} is not iterable")
        return value

    @type_operator(FIELD_SELECT)
    def contains(self, other_value):
        return other_value in self.value

    @type_operator(FIELD_SELECT)
    def does_not_contain(self, other_value):
        return other_value not in self.value

@export_type
class SelectMultipleType(BaseType):
    __slots__ = ()

    name = "select_multiple"

    def _assert_valid_value_and_cast(self, value):
        if not hasattr(value, '__iter__'):
            raise AssertionError(f"Value {value} is not iterable")
        return value

    @type_operator(FIELD_SELECT_MULTIPLE)
    def contains_all(self, other_value):
        select = [o['name'] for o in other_value]
        return set(select).issubset(set(self.value))

    @type_operator(FIELD_SELECT_MULTIPLE)
    def is_contained_by(self, other_value):
        select = [o['name'] for o in other_value]
        return set(self.value).issubset(set(select))

    @type_operator(FIELD_SELECT_MULTIPLE)
    def shares_at_least_one_element_with(self, other_value):
        select = [o['name'] for o in other_value]
        return set(self.value).intersection(set(select))

    @type_operator(FIELD_SELECT_MULTIPLE)
    def shares_exactly_one_element_with(self, other_value):
        select = [o['name'] for o in other_value]
        return len(set(self.value).intersection(set(select))) == 1

    @type_operator(FIELD_SELECT_MULTIPLE)
    def shares_no_elements_with(self, other_value):
        select = [o['name'] for o in other_value]
        return len(set(self.value).intersection(set(select))) == 0

@export_type
class GenericType(BaseType):
    """
    This is a generic type that can be used for any type of value.
    It is useful when you want to define a variable that can be any type.
    """
    __slots__ = ()

    name = "generic"

    def _assert_valid_value_and_cast(self, value):
        return value

    @type_operator(FIELD_TEXT)
    def equal_to(self, other_value):
        return self.value == other_value

@export_type
class DataframeType(BaseType):
    __slots__ = ()

    name = "dataframe"

    def _assert_valid_value_and_cast(self, value):
        if isinstance(value, (pd.Series, pd.DataFrame)):
            return value
        raise AssertionError(f"Value {value} is not a dataframe")

    @type_operator(FIELD_TEXT)
    def exists(self, other_value):
        return self.value.notnull()

    @type_operator(FIELD_TEXT)
    def not_exists(self, other_value):
        return self.value.isnull()
