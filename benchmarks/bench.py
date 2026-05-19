"""
OromScript performance benchmark.

Usage:
    python benchmarks/bench.py           # human-readable output
    python benchmarks/bench.py --ci      # fail if any stage exceeds budget
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from oromscript import transpile

BUDGET_MS = {
    "transpile_small":  20,   # < 20 ms for a ~100 line file
    "transpile_large":  100,  # < 100 ms for a ~1000 line file
}

SMALL = 'agarsiisi("Akkam, Addunyaa!")\n' * 50
LARGE = SMALL * 20   # synthetic 1000-line load


def bench(name: str, fn, reps: int = 100) -> float:
    """Return mean ms over `reps` repetitions."""
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    mean = sum(times) / len(times)
    return mean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()

    results: dict[str, float] = {
        "transpile_small": bench("small", lambda: transpile(SMALL)),
        "transpile_large": bench("large", lambda: transpile(LARGE), reps=20),
    }

    print("\nOromScript Benchmark Results")
    print("=" * 40)
    failed = False
    for name, ms in results.items():
        budget = BUDGET_MS[name]
        status = "✓" if ms <= budget else "✗"
        print(f"  {status} {name:<25} {ms:6.2f} ms  (budget: {budget} ms)")
        if ms > budget:
            failed = True

    if args.ci and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
