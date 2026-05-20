import json
from pathlib import Path


def scaffold_adapter(lang_name: str, adapters_dir: Path) -> None:
    """Scaffold a new adapter directory."""
    d = adapters_dir / lang_name
    d.mkdir(parents=True, exist_ok=True)
    
    (d / "keyword_map.json").write_text(json.dumps({
        "$schema": "https://oromscript.dev/schemas/keyword_map/v1.json",
        "$lang": lang_name,
        "$version": "1.0.0",
        "keywords": {
            k: "" for k in [
                "False", "None", "True", "and", "as", "assert", "async", "await",
                "break", "class", "continue", "def", "del", "elif", "else",
                "except", "finally", "for", "from", "global", "if", "import",
                "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
                "return", "try", "while", "with", "yield", "yield from"
            ]
        },
        "builtins": {
            k: "" for k in [
                "print", "input", "len", "range", "list", "dict", "set", "tuple",
                "str", "int", "float", "bool", "type", "open", "zip", "map",
                "filter", "sorted", "sum", "min", "max", "abs", "round",
                "enumerate", "self", "super"
            ]
        }
    }, indent=2) + "\n", encoding="utf-8")
    
    (d / "error_messages.json").write_text(json.dumps({
        "E0001": "", "E0010": "", "E0011": "", "E0012": "", "E0020": "",
        "E0030": "", "E0050": "", "E0051": "", "E0052": "", "E0060": ""
    }, indent=2) + "\n", encoding="utf-8")
    
    (d / "grammar_hooks.py").write_text(
        "def pre_parse(source: str) -> str:\n    return source\n", encoding="utf-8"
    )
    
    (d / "tests").mkdir(exist_ok=True)
    (d / "tests" / "corpus").mkdir(exist_ok=True)
    (d / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (d / "tests" / "test_keywords.py").write_text(
        "# Tests for keywords\n", encoding="utf-8"
    )
    
    print(f"✓ Adapter scaffolded at {d}")
    print("Next steps:")
    print(f"  1. Fill {d}/keyword_map.json with {lang_name} keywords")
    print(f"  2. Fill {d}/error_messages.json with {lang_name} error messages")
    print(f"  3. Add corpus tests in {d}/tests/corpus/")
    print(f"  4. Run: oromscript validate-adapter {d}")
    print(f"  5. Run: pytest {d}/tests/ -v")
