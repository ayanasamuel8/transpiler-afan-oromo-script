#!/bin/bash
set -e

echo "======================================"
echo "    Running Code Quality Checks       "
echo "======================================"

echo "=> Running ruff..."
ruff check oromscript/ adapters/ tests/

echo "=> Running black..."
black --check oromscript/ adapters/ tests/

echo "=> Running mypy..."
mypy oromscript/ --strict

echo "======================================"
echo "         Running Tests                "
echo "======================================"

echo "=> Running pytest with coverage..."
pytest tests/ adapters/*/tests/ -v --tb=short --cov=oromscript --cov-report=xml --cov-fail-under=95

echo "======================================"
echo "      Running Benchmarks & Valid      "
echo "======================================"

echo "=> Running benchmark..."
python benchmarks/bench.py --ci

echo "=> Validating adapters..."
python -m oromscript.cli validate-adapter adapters/*/

echo "======================================"
echo "             Building Docs            "
echo "======================================"

echo "=> Building docs (strict mode)..."
NO_MKDOCS_2_WARNING="true" python -m mkdocs build --strict

echo "======================================"
echo "       All checks passed! ✨ 🍰 ✨      "
echo "======================================"
