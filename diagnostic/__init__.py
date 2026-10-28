"""Describe Data Diagnostic: the same data-quality checks on any survey export."""
from .checks import run
from .config import Config, load_config
from .load import load

__all__ = ["run", "load", "load_config", "Config"]
__version__ = "0.1.0"
