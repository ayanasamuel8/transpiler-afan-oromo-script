"""
oromscript._gc
~~~~~~~~~~~~~~
Pauses Python's cycle collector while the lexer or parser builds many objects.

The collector scans every live object each time it runs, so building a big
tree with it switched on is noticeably slower (about 15% for the lexer and the
parser). The lexer and parser create no reference cycles, so nothing is lost.
The previous state is restored afterwards. With threads, the collector may come
back on a little early, which only changes timing.
"""

from __future__ import annotations

import contextlib
import gc
from collections.abc import Iterator


@contextlib.contextmanager
def gc_paused() -> Iterator[None]:
    """Turn the cycle collector off inside the block, if it was on."""
    was_enabled = gc.isenabled()
    if was_enabled:
        gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
