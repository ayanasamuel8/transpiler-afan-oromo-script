"""Memory checks: repeated work must not make the process grow."""

from __future__ import annotations

import contextlib
import gc
import tracemalloc
import weakref

import pytest

from oromscript import transpile
from oromscript.adapter import Adapter, AdapterRegistry
from oromscript.errors import OrmError
from oromscript.lexer import OrmLexer, _build_scanner
from oromscript.parser import OrmParser

SAMPLE = (
    'agarsiisi("Akkam, Addunyaa!")\n'
    "x = [i for i in lakkoofsa(3)]\n"
    "yoo x:\n"
    '    deebi f"{x} {of.maqaa}"\n'
    "walsimsiisi x:\n"
    "    haala [1, *rest]:\n"
    "        darbii\n"
) * 6

pytestmark = pytest.mark.perf


def _bytes_grown(work, *, warmup: int, rounds: int) -> int:
    """Bytes of Python memory still held after more runs of ``work``.

    The first runs warm caches. Memory is then measured over two windows of
    ``rounds`` runs each, and the smaller growth is returned. A real leak adds
    memory in both windows. Noise from the interpreter (it differs between
    Python versions) rarely shows up twice.
    """
    for _ in range(warmup):
        work()
    gc.collect()
    tracemalloc.start()
    try:
        for _ in range(rounds // 2):
            work()
        gc.collect()
        marks = [tracemalloc.take_snapshot()]
        for _ in range(2):
            for _ in range(rounds):
                work()
            gc.collect()
            marks.append(tracemalloc.take_snapshot())
    finally:
        tracemalloc.stop()
    return min(
        sum(stat.size_diff for stat in after.compare_to(before, "filename"))
        for before, after in zip(marks, marks[1:], strict=False)
    )


def _objects_grown(work, *, warmup: int, rounds: int) -> int:
    """Live Python objects added by ``rounds`` more runs of ``work``.

    This runs without tracemalloc, which keeps objects of its own.
    """
    for _ in range(warmup + rounds // 2):
        work()
    gc.collect()
    before = len(gc.get_objects())
    for _ in range(rounds):
        work()
    gc.collect()
    return len(gc.get_objects()) - before


def _assert_no_growth(work, *, warmup: int = 10, rounds: int = 80) -> None:
    # A leak of even 1 KB per run would add up to 80 KB in each window.
    grown = _bytes_grown(work, warmup=warmup, rounds=rounds)
    assert grown < 32 * 1024, f"memory grew by {grown} bytes"
    objects = _objects_grown(work, warmup=warmup, rounds=rounds)
    assert objects < 50, f"{objects} more objects are alive"


def test_repeated_transpile_does_not_grow_memory():
    _assert_no_growth(lambda: transpile(SAMPLE))


def test_repeated_lexing_does_not_grow_memory(oromo_adapter):
    _assert_no_growth(lambda: OrmLexer(SAMPLE, oromo_adapter).tokenize())


def test_repeated_parsing_does_not_grow_memory(oromo_adapter):
    tokens = OrmLexer(SAMPLE, oromo_adapter).tokenize()
    _assert_no_growth(lambda: OrmParser(oromo_adapter).parse(tokens))


def test_failing_input_does_not_leak():
    def fail() -> None:
        for bad in ("x = = 1\n", "x = 'abc\n", "if x:\n  y\n z\n", "f(\n"):
            with contextlib.suppress(OrmError):
                transpile(bad)

    _assert_no_growth(fail, rounds=300)


def test_f_string_scanning_does_not_leak():
    source = "f\"{of.maqaa!r:>{w}} {f'{x}'}\"\n" * 10
    _assert_no_growth(lambda: transpile(source), warmup=5)


def test_memory_is_released_after_a_large_file():
    big = SAMPLE * 40
    transpile(big)  # warm up caches
    gc.collect()
    tracemalloc.start()
    try:
        baseline, _ = tracemalloc.get_traced_memory()
        result = transpile(big)
        _, peak = tracemalloc.get_traced_memory()
        del result
        gc.collect()
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert after - baseline < 64 * 1024, f"{after - baseline} bytes still held"
    # Peak use should be a bounded multiple of the input size.
    assert peak < len(big) * 600, f"peak {peak} bytes for {len(big)} bytes of source"


def test_syntax_tree_is_freed_after_use(oromo_adapter):
    tokens = OrmLexer("x = 1\n", oromo_adapter).tokenize()
    tree = OrmParser(oromo_adapter).parse(tokens)
    ref = weakref.ref(tree.body[0])
    del tree
    gc.collect()
    assert ref() is None


def test_error_objects_do_not_keep_the_parser_alive(oromo_adapter):
    tokens = OrmLexer("x = = 1\n", oromo_adapter).tokenize()
    gc.collect()
    before = len(gc.get_objects())
    for _ in range(200):
        with contextlib.suppress(OrmError):
            OrmParser(oromo_adapter).parse(tokens)
    gc.collect()
    assert len(gc.get_objects()) - before < 100


def test_scanner_cache_is_bounded():
    for index in range(100):
        adapter = Adapter(
            lang=f"lang{index}",
            keyword_map={"print": f"word{index}'s"},
            builtin_map={},
            error_messages={},
        )
        OrmLexer("x = 1\n", adapter).tokenize()
    assert _build_scanner.cache_info().currsize <= 32


def test_same_adapter_shares_one_compiled_scanner(oromo_adapter):
    first = OrmLexer("x\n", oromo_adapter)._scanner
    second = OrmLexer("y\n", oromo_adapter)._scanner
    assert first is second


def test_adapter_registry_does_not_grow():
    before = list(AdapterRegistry.list_langs())
    for _ in range(50):
        transpile("x = 1\n")
    assert AdapterRegistry.list_langs() == before


def test_grapheme_cache_is_bounded():
    from oromscript.graphemes import grapheme_nodes

    for index in range(6000):
        grapheme_nodes(f"word{index}dhaa")
    assert grapheme_nodes.cache_info().currsize <= 4096


def test_parsing_with_grapheme_nodes_does_not_leak():
    _assert_no_growth(lambda: transpile("maqaa = dhaabbata(xiyyeeffannoo=1)\n" * 30))
