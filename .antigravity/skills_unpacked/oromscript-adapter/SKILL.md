---
name: oromscript-adapter
description: >
  Create, validate, or extend a OromScript language adapter — the plugin that lets
  the transpiler understand a new local language (Amharic, Tigrinya, Somali, etc.).
  Use this skill whenever the task involves: creating a new adapter from scratch,
  filling or updating keyword_map.json, writing error_messages.json, implementing
  grammar_hooks.py, scaffolding the adapter directory, writing adapter tests,
  validating adapter schema compliance, publishing an adapter as a standalone PyPI
  package (oromscript-lang-NAME), or explaining how to add a new language to the
  platform. Also use when reviewing an existing adapter for completeness or correctness.
  This skill is the primary reference for all adapters/ work.
---

# OromScript Language Adapter

A Language Adapter is the **only** thing a contributor needs to create to add a new
local language to OromScript. The core engine (Lexer, Parser, etc.) never changes.

---

## Adapter Directory Layout

```
adapters/
└── <lang_name>/                  ← snake_case, e.g. amharic, tigrinya
    ├── keyword_map.json          ← REQUIRED. Maps Python↔local keywords.
    ├── error_messages.json       ← REQUIRED. Localised error strings.
    ├── grammar_hooks.py          ← OPTIONAL. Pre-parse source transforms.
    └── tests/
        ├── test_keywords.py      ← Unit tests: every keyword has a round-trip test.
        └── corpus/
            ├── 001_hello.orm     ← Input: Oromo source.
            ├── 001_hello.py      ← Expected: generated Python.
            └── ...               ← One pair per language feature tested.
```

---

## Step-by-Step: Adding a New Language

### Step 1 — Scaffold

```bash
oromscript new-lang <lang_name>
# Creates the directory structure above with templates.
```

Or manually create the folder. The `new-lang` command generates:
- `keyword_map.json` with all Python keywords listed and empty value strings.
- `error_messages.json` with all error codes listed and empty strings.
- `grammar_hooks.py` as a no-op stub.
- `tests/` directory.

### Step 2 — Fill keyword_map.json

Fill every entry under `keywords` and `builtins` with the local-language equivalent.
Rules (enforced by schema validator):

| Rule | Detail |
|------|--------|
| 1-to-1 mapping (v1) | Each Python keyword maps to exactly ONE local keyword. No synonyms yet. |
| No duplicates | Two Python keywords cannot share the same local keyword. |
| Non-empty values | Every value must be a non-empty string. |
| All keywords covered | All 35 Python keywords must have an entry. |
| UTF-8 | File must be valid UTF-8 (supports all scripts: Ethiopic, Arabic, etc.). |

See `oromscript-core` skill → `references/keyword_map_schema.md` for the full schema
and the complete Afan Oromo reference map.

### Step 3 — Fill error_messages.json

```json
{
  "E0001": "Xiyyeeffannoo: maddii '{token}' sirriitti barreeffamee hin jiru — sarara {line}",
  "E0010": "Dogoggora caasaa — sarara {line}, tuqaa {col}: {text}",
  "E0020": "Maqaan '{name}' hin beekamu",
  "E0050": "Faayiliin keyword_map.json hin argamne",
  "E0051": "Afaan '{lang}' hin deeggeramu"
}
```

Template variables (always available): `{line}`, `{col}`, `{lang}`, `{token}`, `{name}`, `{text}`.
Only use variables that appear in the `context` dict of the specific error code.
See `references/error_codes.md` for the full list of codes and their context variables.

### Step 4 — grammar_hooks.py (optional)

Only needed for languages that require **source-level text transformations** before parsing,
such as:
- Right-to-left script reordering (rare — Python indentation is LTR regardless of script)
- Agglutinative suffix stripping (e.g. verb conjugations that embed keywords)
- Multi-word keywords (e.g. "yoo miti" → `else`)

```python
# adapters/amharic/grammar_hooks.py
"""
Grammar hooks for the Amharic adapter.
All functions are optional. The core engine checks for their existence before calling.
"""

def pre_parse(source: str) -> str:
    """Pre-process the untokenised Python source before ast.parse().

    Args:
        source: The source string after keyword translation (valid Python keywords,
                but may still have Amharic identifiers and string literals).

    Returns:
        Modified source string. Must still be valid Python after modification.
    """
    # Example: normalise Ethiopic full stop (።) to Python colon (:)
    return source.replace("።", ":")
```

**Important:** `grammar_hooks.py` functions receive source that has **already had keywords
translated**. They work on Python-keyword source with local identifiers/strings still intact.

### Step 5 — Write corpus tests

Each corpus pair tests one language feature end-to-end:

```
# corpus/002_for_loop.orm       ← INPUT (Afan Oromo)
hanga lakki keessa lakkoofsa(5):
    agarsiisi(lakki)

# corpus/002_for_loop.py        ← EXPECTED OUTPUT (Python)
for lakki in range(5):
    print(lakki)
```

Rules:
- Filename prefix must be 3-digit zero-padded number (`001_`, `002_`, ...).
- `.orm` and `.py` must have identical prefixes.
- The `.py` file is the **exact** output of `oromscript compile <file>.orm` — no reformatting.
- Every Python keyword used in the language must have at least one corpus pair.

### Step 6 — Write unit tests

```python
# adapters/amharic/tests/test_keywords.py
import pytest
from oromscript import transpile

# Auto-generate a test for every keyword in the map
import json
from pathlib import Path

ADAPTER_DIR = Path(__file__).parent.parent
KMAP = json.loads((ADAPTER_DIR / "keyword_map.json").read_text())

@pytest.mark.parametrize("local_kw,py_kw", KMAP["keywords"].items())
def test_keyword_roundtrip(local_kw: str, py_kw: str) -> None:
    """Each local keyword must transpile to its Python equivalent."""
    # Build a minimal valid snippet using the keyword
    snippets = {
        "if": f"{local_kw} Dhugaa:\n    darbii",
        "for": f"{local_kw} i keessa lakkoofsa(1):\n    darbii",
        "def": f"{local_kw} f():\n    darbii",
        # Add more as needed
    }
    snippet = snippets.get(py_kw)
    if snippet is None:
        pytest.skip(f"No test snippet for {py_kw}")
    result = transpile(snippet, lang="amharic")  # replace with adapter lang
    assert py_kw in result
```

### Step 7 — Validate & test

```bash
# Schema validation
oromscript validate-adapter adapters/<lang_name>/

# Run all adapter tests
pytest adapters/<lang_name>/tests/ -v

# Run corpus tests (auto-discovered)
pytest adapters/<lang_name>/tests/ -v -k "corpus"
```

### Step 8 — Open a PR

Use the `new_language` issue template (`.github/ISSUE_TEMPLATE/new_language.md`).
PR title format: `lang(<lang_name>): add <Language Name> adapter`.

---

## Distributing an Adapter as a PyPI Package

For community adapters that live outside the main repo:

```
oromscript-lang-amharic/
├── pyproject.toml
├── adapters/
│   └── amharic/
│       ├── keyword_map.json
│       └── ...
└── README.md
```

```toml
# pyproject.toml
[project.entry-points."oromscript.adapters"]
amharic = "adapters.amharic"
```

The `AdapterRegistry.discover()` method also scans installed entry points in the
`oromscript.adapters` group, so the adapter is available immediately after `pip install`.

---

## Adapter Completeness Checklist

Before marking an adapter as stable (v1.0+):

- [ ] All 35 Python keywords mapped
- [ ] At least 15 builtins mapped (including print, input, len, range, list, dict, str, int, float, bool)
- [ ] error_messages.json covers all E00xx codes
- [ ] Corpus: at minimum one test per keyword category (control flow, functions, classes, exceptions, imports)
- [ ] Schema validation passes (`oromscript validate-adapter`)
- [ ] All tests pass (`pytest`)
- [ ] README in adapter folder: language name, native speakers count, author, example code

---

## See Also

- `oromscript-core` skill → `references/keyword_map_schema.md` — full JSON schema
- `oromscript-testing` skill — corpus runner implementation details
- `references/error_codes.md` — all error codes with context variable docs
