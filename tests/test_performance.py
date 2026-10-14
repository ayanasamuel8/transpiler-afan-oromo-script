"""Speed checks with wide limits, so they stay stable on slow machines.

For exact numbers run ``python benchmarks/bench.py``.
"""

from __future__ import annotations

import sys
import time

import pytest

from oromscript import transpile
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser

pytestmark = pytest.mark.perf


def _under_coverage() -> bool:
    cov = sys.modules.get("coverage")
    return cov is not None and cov.Coverage.current() is not None


# Coverage tracing makes Python code several times slower, so absolute limits
# grow when it is on. The checks for linear growth compare two runs and need no
# such change.
SLOWDOWN = 15 if _under_coverage() else 1

LINE = 'agarsiisi("Akkam, Addunyaa!")\n'
BLOCK = (
    "hojii ida(a, b):\n"
    "    yoo a > b:\n"
    "        deebi a + b\n"
    "    hanga i keessa lakkoofsa(a):\n"
    "        agarsiisi(f'{i}: {a * b}')\n"
    "    deebi [x * 2 hanga x keessa lakkoofsa(b)]\n"
)


def best_of(fn, runs: int = 3) -> float:
    """Return the shortest run time in seconds."""
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def test_small_file_is_fast():
    source = LINE * 100
    assert best_of(lambda: transpile(source)) < 0.5 * SLOWDOWN


def test_thousand_line_file_is_fast():
    source = BLOCK * 160  # about 1000 lines
    assert best_of(lambda: transpile(source)) < 2.0 * SLOWDOWN


def test_token_throughput_is_at_least_15000_per_second(oromo_adapter):
    source = LINE * 4000
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    seconds = best_of(
        lambda: OrmParser(oromo_adapter).parse(
            OrmLexer(source, oromo_adapter).tokenize()
        )
    )
    assert len(tokens) / seconds >= 15_000 / SLOWDOWN


def test_one_megabyte_file_finishes():
    source = LINE * 35_000  # about 1 MB
    assert len(source) > 1_000_000
    assert best_of(lambda: transpile(source), runs=1) < 30.0 * SLOWDOWN


def test_time_grows_linearly_with_file_size(oromo_adapter):
    def run(n: int) -> float:
        source = BLOCK * n
        return best_of(
            lambda: OrmParser(oromo_adapter).parse(
                OrmLexer(source, oromo_adapter).tokenize()
            )
        )

    small = run(30)
    large = run(240)  # eight times the input
    # Linear growth gives about 8. A quadratic parser would give about 64.
    assert large / small < 24


def test_deep_indentation_is_not_slow(oromo_adapter):
    depth = 60
    lines = [f"{'    ' * i}yoo x:" for i in range(depth)]
    lines.append(f"{'    ' * depth}darbii")
    source = "\n".join(lines) + "\n"
    assert best_of(lambda: OrmLexer(source, oromo_adapter).tokenize()) < 0.5 * SLOWDOWN


def test_long_single_line_is_not_quadratic(oromo_adapter):
    def run(n: int) -> float:
        source = "x = [" + ", ".join(str(i) for i in range(n)) + "]\n"
        return best_of(lambda: OrmLexer(source, oromo_adapter).tokenize())

    # Eight times the tokens on one line should cost about eight times as much.
    assert run(16_000) / max(run(2_000), 1e-9) < 24


def test_many_strings_with_backslashes_is_not_quadratic(oromo_adapter):
    def run(n: int) -> float:
        source = ("x = '" + "\\\\" * 20 + "'\n") * n
        return best_of(lambda: OrmLexer(source, oromo_adapter).tokenize())

    assert run(16_000) / max(run(2_000), 1e-9) < 24


def test_unterminated_triple_quote_fails_fast(oromo_adapter):
    from oromscript.errors import OrmLexError

    source = 'x = """' + "a" * 500_000
    start = time.perf_counter()
    with pytest.raises(OrmLexError):
        OrmLexer(source, oromo_adapter).tokenize()
    assert time.perf_counter() - start < 2.0 * SLOWDOWN


def test_parse_stage_of_a_one_megabyte_file(oromo_adapter):
    source = LINE * 35_000  # about 1 MB
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    seconds = best_of(lambda: OrmParser(oromo_adapter).parse(tokens), runs=2)
    assert seconds < 2.0 * SLOWDOWN


def test_parse_stage_of_a_mixed_one_megabyte_file(oromo_adapter):
    source = BLOCK * 6500  # classes, loops, f-strings, comprehensions
    assert len(source) > 900_000
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    seconds = best_of(lambda: OrmParser(oromo_adapter).parse(tokens), runs=2)
    assert seconds < 3.0 * SLOWDOWN
