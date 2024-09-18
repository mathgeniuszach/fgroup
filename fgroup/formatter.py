from typing import TYPE_CHECKING
if TYPE_CHECKING: # pragma: nocover
    from typing import Generator

import argparse
import textwrap

from .util import TERMINAL_COLUMNS, RESERVED_COLUMNS


class Formatter(argparse.RawTextHelpFormatter):
    "Lazy-and-compact fix for https://github.com/python/cpython/issues/119021 with other improvements."
    def __init__(self, prog: str) -> None:
        super().__init__(prog, 2, 60, TERMINAL_COLUMNS)

    def add_argument(self, action):
        subaction = isinstance(action, argparse._SubParsersAction)
        if subaction: self._indent()
        try: super().add_argument(action)
        finally:
            if subaction: self._dedent()

    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar
        else:
            stext = ', '.join(action.option_strings)

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0: return stext
            # if the Optional takes a value, format (instead of the default) should be:
            #    -s, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                return stext + " " + args_string

def _wrap_iter(size: int, *msgs: str) -> 'Generator[str]':
    "Helper method for wrap() and wrap_full() which preserves empty string arguments."
    for msg in msgs:
        if msg == "": yield ""
        else: yield from textwrap.wrap(msg, size)

def wrap(*msgs: str):
    "Wraps each message across lines to fit the current terminal width (minus the reserved column count)."
    return '\n'.join(_wrap_iter(TERMINAL_COLUMNS - RESERVED_COLUMNS, *msgs))

def wrap_full(*msgs: str) -> str:
    "Wraps each message across lines to fit the current terminal width."
    return '\n'.join(_wrap_iter(TERMINAL_COLUMNS, *msgs))