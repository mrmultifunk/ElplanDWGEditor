"""Kompatibilitetsfacade for eksisterende Elplan-importer."""

from elplan_legacy import core_api as __compat
from elplan_legacy.core_api import *  # noqa: F401,F403 - bevar det eksisterende API


def __getattr__(name: str):
    return getattr(__compat, name)


def __dir__():
    return sorted(set(globals()) | set(dir(__compat)))
