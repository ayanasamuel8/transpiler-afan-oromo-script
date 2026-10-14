# Dev Shortcuts

.PHONY: test test-slow lint bench dev-ext

test:
	pytest tests/ adapters/*/tests/ -v --tb=short

test-slow:
	pytest tests/ -m slow -v --tb=short

lint:
	ruff check oromscript/ adapters/ tests/
	black --check oromscript/ adapters/ tests/
	mypy oromscript/ --strict

bench:
	python benchmarks/bench.py

dev-ext:
	mkdir -p scripts
	python3 scripts/gen_tmlanguage.py adapters/afan_oromo/keyword_map.json > vscode-extension/syntaxes/afan_oromo.tmLanguage.json
