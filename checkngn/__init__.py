__version__ = "1.5.0"

from .engine import run_all
from .utils import export_rule_data
from .logs import enable_debug

# Appease pyflakes by "using" these exports
assert run_all
assert export_rule_data
assert enable_debug
