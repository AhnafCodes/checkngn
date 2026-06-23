"""Custom exception hierarchy for checkngn.

These replace the previous use of bare ``assert`` statements and
``AssertionError`` for configuration/runtime validation. ``assert`` statements
are stripped when Python runs with ``-O``, and ``AssertionError`` is awkward for
library consumers to catch deliberately. A dedicated hierarchy lets callers
handle rule-definition problems gracefully.
"""


class RuleEngineError(Exception):
    """Base class for all checkngn errors."""


class RuleValidationError(RuleEngineError):
    """Raised when a rule, variable, or action *definition* is invalid.

    e.g. a malformed rule dict, an empty ``all``/``any`` block, or an unknown
    field type / parameter on an action.
    """


class MissingVariableError(RuleEngineError):
    """Raised when a rule references a variable not defined on the variables class."""


class UndefinedOperatorError(RuleEngineError):
    """Raised when a rule references an operator that does not exist for the type."""


class UndefinedActionError(RuleEngineError):
    """Raised when a rule references an action that is not a registered rule action."""
