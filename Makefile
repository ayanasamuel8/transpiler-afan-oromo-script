# Dev Shortcuts

.PHONY: test lint dev-ext

test:
	pytest tests/ adapters/*/tests/ -v --tb=short

lint:
	ruff check oromscript/ adapters/
	black --check oromscript/ adapters/
	mypy oromscript/

dev-ext:
	mkdir -p scripts
	python3 scripts/gen_tmlanguage.py adapters/afan_oromo/keyword_map.json > vscode-extension/syntaxes/afan_oromo.tmLanguage.json
