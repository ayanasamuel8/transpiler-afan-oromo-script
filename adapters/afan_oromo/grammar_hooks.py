"""
Grammar hooks for the Afan Oromo adapter.

The Afan Oromo adapter needs no hooks, so none is defined. The core engine
checks for each hook before calling it.

If a language needs one, define it in this file, for example::

    def pre_parse(source: str) -> str:
        # Change the source text after keyword translation. Return valid
        # Python. The parser then reads that text with Python's own ast.parse().
        return source.replace("...", "...")

Define a hook only if it changes something. Any hook makes the engine rebuild
the whole source text on every run, which takes about 8% of the parse time.
"""
