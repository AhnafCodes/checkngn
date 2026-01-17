"""
Themed logging for checknginlite with "check engine light" style output.

Usage:
    # Quick toggle via debug parameter
    run_all(rules, variables, actions, debug=True)

    # Or fine-grained control via standard logging
    import logging
    logging.getLogger('checkngn').setLevel(logging.DEBUG)
"""

import logging
import sys

# Logger name - short and themed
LOGGER_NAME = 'checkngn'

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def _supports_color():
    """Check if the terminal supports color output."""
    if not hasattr(sys.stdout, 'isatty'):
        return False
    if not sys.stdout.isatty():
        return False
    return True


class CheckEngineLightFormatter(logging.Formatter):
    """Custom formatter with check engine light theme and colors."""

    def __init__(self, use_color=True):
        super().__init__()
        self.use_color = use_color and _supports_color()

    def _colorize(self, text, color):
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text

    def format(self, record):
        # Build the prefix
        prefix = f"🔧 [{LOGGER_NAME}]"

        # Get the message
        msg = record.getMessage()

        # Colorize only the ✓ and ✗ symbols
        if self.use_color:
            msg = msg.replace('✓', f"{Colors.GREEN}✓{Colors.RESET}")
            msg = msg.replace('✗', f"{Colors.RED}✗{Colors.RESET}")

        return f"{prefix} {msg}"


# Module-level logger
_logger = None
_handler = None


def get_logger():
    """Get the checkngn logger instance."""
    global _logger, _handler

    if _logger is None:
        _logger = logging.getLogger(LOGGER_NAME)
        _logger.setLevel(logging.WARNING)  # Off by default
        _logger.propagate = False

    return _logger


def enable_debug(enable=True):
    """
    Enable or disable debug logging with themed output.

    Args:
        enable: True to enable debug output, False to disable
    """
    global _handler

    logger = get_logger()

    if enable:
        logger.setLevel(logging.DEBUG)

        # Add handler if not already added
        if _handler is None:
            _handler = logging.StreamHandler(sys.stdout)
            _handler.setFormatter(CheckEngineLightFormatter(use_color=True))
            logger.addHandler(_handler)
        _handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)


def log_rule_start(rule_index, total_rules):
    """Log the start of rule evaluation."""
    get_logger().debug(f"Evaluating rule {rule_index}/{total_rules}")


def log_condition_result(condition_name, operator, value, result):
    """Log the result of a condition check."""
    if result:
        get_logger().debug(f"✓ condition '{condition_name} {operator} {value}' → True")
    else:
        get_logger().debug(f"✗ condition '{condition_name} {operator} {value}' → False")


def log_condition_group(group_type, result):
    """Log the result of a condition group (all/any/not)."""
    symbol = '✓' if result else '✗'
    get_logger().debug(f"{symbol} '{group_type}' block → {result}")


def log_rule_result(triggered, reason=None):
    """Log the final result of rule evaluation."""
    if triggered:
        get_logger().debug("Rule triggered ✓")
    else:
        msg = "Rule not triggered"
        if reason:
            msg += f" ({reason})"
        get_logger().debug(msg)


def log_action_execution(action_name, params=None):
    """Log action execution."""
    if params:
        get_logger().debug(f"Executing action '{action_name}' with {params}")
    else:
        get_logger().debug(f"Executing action '{action_name}'")


def log_variable_value(name, value):
    """Log variable value retrieval."""
    get_logger().debug(f"Variable '{name}' → {value}")