# Dev Shortcuts

.PHONY: test lint

test:
	pytest tests/ adapters/*/tests/ -v --tb=short

lint:
	ruff check oromscript/ adapters/
	black --check oromscript/ adapters/
	mypy oromscript/
