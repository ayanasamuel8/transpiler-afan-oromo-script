"""
OromScript performance benchmark.

Usage:
    python benchmarks/bench.py           # human-readable output
    python benchmarks/bench.py --ci      # fail if any budget is missed
"""

from __future__ import annotations

import argparse
import gc
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

from oromscript import transpile
from oromscript.adapter import AdapterRegistry
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser

BUDGET_MS = {
    "transpile_small": 20,  # < 20 ms for a ~100 line file
    "transpile_large": 100,  # < 100 ms for a ~1000 line file
    "transpile_1mb": 10_000,  # < 10 s for a ~1 MB file (about 35,000 lines)
    "parse_1mb": 2_000,  # < 2 s for the parse stage of a ~1 MB file
}
PARSE_TARGET_MS = 600  # the parse stage of a 1 MB file should take less than this
MIN_TOKENS_PER_SECOND = 15_000
MAX_LEAK_BYTES = 32 * 1024

SMALL = 'agarsiisi("Akkam, Addunyaa!")\n' * 50
LARGE = SMALL * 20  # synthetic 1000-line load
ONE_MB = 'agarsiisi("Akkam, Addunyaa!")\n' * 35_000


def mixed_one_mb() -> str:
    """About 1 MB of different statements: the example programs, repeated."""
    examples = Path(__file__).parent.parent / "examples"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(examples.glob("*.orm"))
        if path.stat().st_size > 0
    )
    text = (text + "\n") * (1_000_000 // len(text) + 1)
    text = text[:1_000_000]
    return text[: text.rfind("\n") + 1]


def bench(fn: Callable[[], object], reps: int = 100) -> float:
    """Return mean ms over `reps` repetitions."""
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return sum(times) / len(times)


def leaked_bytes() -> int:
    """Bytes still held after 100 more transpiles (should be near zero)."""
    for _ in range(20):
        transpile(SMALL)
    gc.collect()
    tracemalloc.start()
    try:
        for _ in range(50):
            transpile(SMALL)
        gc.collect()
        before = tracemalloc.take_snapshot()
        for _ in range(100):
            transpile(SMALL)
        gc.collect()
        after = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    return sum(s.size_diff for s in after.compare_to(before, "filename"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()

    adapter = AdapterRegistry.get("afan_oromo")
    results: dict[str, float] = {
        "transpile_small": bench(lambda: transpile(SMALL)),
        "transpile_large": bench(lambda: transpile(LARGE), reps=20),
        "transpile_1mb": bench(lambda: transpile(ONE_MB), reps=3),
    }

    print("\nOromScript Benchmark Results")
    print("=" * 52)
    failed = False
    for name, ms in results.items():
        budget = BUDGET_MS[name]
        status = "✓" if ms <= budget else "✗"
        print(f"  {status} {name:<25} {ms:9.2f} ms  (budget: {budget} ms)")
        if ms > budget:
            failed = True

    print("\n1 MB files, by stage")
    print("-" * 52)
    rate = 0.0
    parse_ms = 0.0
    for label, text in (("print statements", ONE_MB), ("mixed code", mixed_one_mb())):
        tokens = OrmLexer(text, adapter).tokenize()
        lex_ms = bench(lambda text=text: OrmLexer(text, adapter).tokenize(), reps=3)
        parse_ms = bench(lambda tokens=tokens: OrmParser(adapter).parse(tokens), reps=3)
        rate = len(tokens) / ((lex_ms + parse_ms) / 1000)
        met = "✓" if parse_ms <= PARSE_TARGET_MS else "·"
        print(f"  {label} ({len(text):,d} bytes, {len(tokens):,d} tokens)")
        print(f"    lexer   {lex_ms:9.2f} ms")
        print(f"    parser  {parse_ms:9.2f} ms  {met} target: {PARSE_TARGET_MS} ms")
        status = "✓" if rate >= MIN_TOKENS_PER_SECOND else "✗"
        failed = failed or rate < MIN_TOKENS_PER_SECOND
        print(
            f"  {status} lexer + parser {rate:11,.0f} tokens/sec"
            f"  (minimum: {MIN_TOKENS_PER_SECOND:,})"
        )
        results.setdefault("parse_1mb", 0.0)
        results["parse_1mb"] = max(results["parse_1mb"], parse_ms)
    if results["parse_1mb"] > BUDGET_MS["parse_1mb"]:
        failed = True
        print(f"  ✗ parse_1mb {results['parse_1mb']:.0f} ms is over its budget")

    leak = leaked_bytes()
    status = "✓" if leak <= MAX_LEAK_BYTES else "✗"
    failed = failed or leak > MAX_LEAK_BYTES
    print("\nMemory")
    print("-" * 52)
    print(
        f"  {status} held after 100 runs {leak:9,d} bytes"
        f"  (max: {MAX_LEAK_BYTES:,})"
    )

    if args.ci and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
