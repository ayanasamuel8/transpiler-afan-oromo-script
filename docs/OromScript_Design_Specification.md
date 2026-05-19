  
**OROMSCRIPT**

Transpiler Design Specification

*Write Python in Afan Oromo — Execute Anywhere*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Version 1.0  ·  May 2025  ·  Open Source (MIT)

[github.com/ayanasamuel8/transpiler-afan-oromo-script](https://github.com/ayanasamuel8/transpiler-afan-oromo-script)

# **Table of Contents**

# **1\. Executive Summary**

OromScript is an open-source, language-localisation transpiler platform that lets developers write Python programs using **Afan Oromo** keywords, identifiers, and idioms. The transpiler parses Oromo-syntax source files (.orm), translates them into standard Python, and executes or outputs the result — with no measurable runtime overhead above Python itself.

**Core value proposition:** lower the barrier to programming for the 40+ million Afan Oromo speakers worldwide, and provide a reusable, well-documented platform so any other language community (Amharic, Tigrinya, Somali, …) can add their own keyword layer in under a day.

| Scope boundaries (what this design covers) • Afan Oromo → Python 3.12+ full-language transpiler (all Python constructs) • A plugin/adapter system for adding new languages (Amharic, etc.) • CLI tool, library API, VS Code syntax highlighting extension • Comprehensive test suite, CI/CD pipeline, contribution workflow • Localized error messages in Oromo (and extensible for other languages) • NOT in scope for v1: JIT compilation, custom C-extension ABI, IDE debugger protocol |
| :---- |

# **2\. Goals & Non-Goals**

## **2.1 Goals**

| Priority | Goal |
| :---- | :---- |
| **P0** | Full Python parity — every Python 3 construct has an Afan Oromo equivalent |
| **P0** | Transpile-time only overhead; generated Python must be identical to hand-written Python |
| **P0** | Plugin architecture: add a new language by supplying one JSON keyword map \+ optional grammar hooks |
| **P1** | Localized, actionable error messages (line/col, suggestion, Oromo text) |
| **P1** | VS Code extension with syntax highlighting for .orm files |
| **P1** | CI/CD with automated tests, linting, and release publishing |
| **P2** | Source-map support so stack traces reference .orm lines |
| **P2** | REPL (interactive Oromo Python shell) |

## **2.2 Non-Goals (v1)**

* Custom bytecode compiler or JIT — Python's CPython handles execution

* Full IDE debugger (DAP) integration — deferred to v2

* Transpiling to languages other than Python — possible in v2 via IR

* GUI application — CLI \+ library is sufficient for v1

# **3\. Architecture Overview**

OromScript follows a classic multi-phase compiler pipeline. The key design decision is to keep the Oromo-specific logic (lexer keyword map, grammar patches) strictly isolated from the generic AST manipulation and Python code-generation layers. This is what enables easy addition of new languages.

**Figure 1 — High-level transpiler pipeline**

|   ┌──────────────────────────────────────────────────────────────────────┐   │                         OROMSCRIPT PIPELINE                          │   └──────────────────────────────────────────────────────────────────────┘                                                                               .orm source file                                                                │                                                                          ▼                                                                    ┌─────────────┐    keyword\_map.json   ┌──────────────────────────────┐    │   LEXER     │◄─────────────────────│  Language Adapter (Oromo)    │    │  (Tokenizer)│                       │  • keyword\_map.json          │    └─────────────┘                       │  • grammar\_hooks.py (opt.)   │          │                               └──────────────────────────────┘          │ token stream                                                             ▼                                                                    ┌─────────────┐                                                           │   PARSER    │  (Python grammar extended with adapter hooks)              │  (LALR/PEG) │                                                           └─────────────┘                                                                 │                                                                          │ AST (language-neutral)                                                   ▼                                                                    ┌─────────────┐                                                           │  SEMANTIC   │  (symbol table, scope, type hints validation)              │  ANALYSER   │                                                           └─────────────┘                                                                 │                                                                          │ annotated AST                                                            ▼                                                                    ┌─────────────┐                                                           │  CODE GEN   │  ast.unparse() → standard Python source                   │  \+ SOURCEMAP│  produces .py \+ .orm.map (line/col mapping)               └─────────────┘                                                                 │                                                                          ├── output.py  (for \--emit-python)                                        └──► CPython   (for \--run)                                        |
| :---- |

## **3.1 Language Adapter (Plugin) Concept**

A Language Adapter is the only artefact a contributor needs to create to localise the platform for a new language. It consists of:

* **keyword\_map.json** — maps every Python keyword / builtin to the local-language equivalent

* **grammar\_hooks.py** (optional) — Python module with hooks if the language needs non-trivial grammar extensions (e.g. right-to-left parsing, agglutinative morphology)

* **error\_messages.json** — localised error strings keyed by error code

* **tests/** — adapter-specific test corpus

**Figure 2 — Language Adapter file structure**

|   adapters/   ├── afan\_oromo/          ← shipped with this repo   │   ├── keyword\_map.json   │   ├── grammar\_hooks.py   │   ├── error\_messages.json   │   └── tests/   └── amharic/             ← future adapter (community-contributed)       ├── keyword\_map.json       └── ... |
| :---- |

## **3.2 Why Python as the IR (Intermediate Representation)**

Rather than designing a custom IR, v1 uses Python source text as the IR. This gives us:

* Zero execution overhead — CPython runs the output directly

* Full ecosystem compatibility — pip packages, type checkers, debuggers all work

* Simpler code generator — we use Python's built-in ast.unparse()

* Easy verification — diff the generated .py against expected output in tests

| Future IR note (v2 consideration) If the project later targets multiple backends (JavaScript, Rust, etc.), a proper IR (e.g. LLVM or a custom DAG) can be introduced between the Semantic Analyser and Code Gen layers without touching the Lexer, Parser, or Adapter. |
| :---- |

# **4\. Detailed Component Design**

## **4.1 Lexer**

The Lexer inherits from Python's own tokenize module. It intercepts the token stream and applies a reverse keyword map: any token whose string value matches a local-language keyword is replaced with the corresponding Python keyword token before the parser sees it. This means the parser is always working with standard Python tokens and requires no changes per language.

| \# oromscript/lexer.py (simplified) import tokenize, io from .adapter import AdapterRegistry class OromLexer:     def \_\_init\_\_(self, source: str, lang: str \= 'afan\_oromo'):         self.adapter \= AdapterRegistry.get(lang)         self.source \= source     def tokenize(self):         tokens \= list(tokenize.generate\_tokens(             io.StringIO(self.source).readline         ))         return \[self.\_translate(tok) for tok in tokens\]     def \_translate(self, tok):         if tok.type \== tokenize.NAME:             py\_kw \= self.adapter.to\_python\_keyword(tok.string)             if py\_kw:                 return tok.\_replace(string=py\_kw)         return tok |
| :---- |

## **4.2 Parser**

The parser uses **Python's built-in** ast.parse() on the translated token stream (re-assembled into a string via tokenize.untokenize()). This keeps the parser zero-maintenance — as CPython evolves, our parser evolves for free. Grammar hooks in the adapter can pre-process the source string before re-assembly for languages with structural differences (e.g. postfix function calls).

## **4.3 Semantic Analyser**

The semantic analyser performs a single-pass walk of the AST to:

* Build a symbol table (scoped dictionary of names → type hints)

* Validate that all referenced names are defined (optional strict mode)

* Annotate nodes with source-map information (original .orm line/col)

* Detect common localisation mistakes (e.g., mixing Oromo and Python keywords)

## **4.4 Code Generator**

The code generator calls ast.unparse(tree) to produce Python source from the annotated AST. It also emits a JSON source-map file (.orm.map) mapping every generated line back to the original Oromo source line, enabling localised stack traces.

| \# oromscript/codegen.py import ast, json class CodeGen:     def generate(self, tree: ast.AST, source\_map: dict) \-\> tuple\[str, str\]:         py\_source \= ast.unparse(tree)         map\_json  \= json.dumps(source\_map, ensure\_ascii=False, indent=2)         return py\_source, map\_json |
| :---- |

## **4.5 Error Reporting**

Errors are structured objects carrying a numeric code, the offending .orm line/col, and a localised message. The error renderer looks up the message template from the active adapter's error\_messages.json and formats it with context-specific substitution variables.

**Figure 3 — Error message flow**

|   OromSyntaxError(code=E0042, line=7, col=3, context={'token': 'yoo'})          │          ▼   ErrorRenderer(adapter='afan\_oromo')          │  looks up error\_messages.json\[E0042\]          │  template: "Wardii himaa '{token}' iddoo dha'uu hin qabu — sarara {line}"          ▼   stderr: error\[E0042\] sarara 7, tuqaa 3:           Wardii himaa 'yoo' iddoo dha'uu hin qabu — sarara 7           Yaadannoo: 'yoo' jechuun 'if' jechuu dha; akka armaan gadiitti fayyadami:             yoo gatii \> 0: |
| :---- |

## **4.6 Adapter Registry**

The AdapterRegistry discovers adapters at startup by scanning the adapters/ directory for subdirectories containing a keyword\_map.json. Adapters can also be installed as PyPI packages following the naming convention oromscript-lang-\<name\>, allowing community adapters to be distributed independently.

| \# oromscript/adapter.py class AdapterRegistry:     \_adapters: dict\[str, Adapter\] \= {}     @classmethod     def discover(cls, adapters\_dir: Path):         for d in adapters\_dir.iterdir():             if (d / 'keyword\_map.json').exists():                 cls.\_adapters\[d.name\] \= Adapter.load(d)     @classmethod     def get(cls, lang: str) \-\> Adapter:         if lang not in cls.\_adapters:             raise AdapterNotFoundError(lang)         return cls.\_adapters\[lang\] |
| :---- |

## **4.7 CLI Interface**

The command-line interface is built with Click and supports:

| \# Usage examples oromscript run hello.orm               \# transpile \+ execute oromscript compile hello.orm           \# emit hello.py oromscript compile hello.orm \--map     \# emit hello.py \+ hello.orm.map oromscript check hello.orm             \# lint only, no output oromscript repl                        \# interactive Oromo Python REPL oromscript new-lang amharic            \# scaffold a new adapter oromscript \--lang amharic run hi.amh  \# use a different adapter |
| :---- |

## **4.8 Library API**

OromScript is importable as a Python library so it can be embedded in notebooks, build tools, or web services:

| from oromscript import transpile, execute py\_source \= transpile('agarsiisi("Akkam\!")', lang='afan\_oromo') result    \= execute('agarsiisi("Akkam\!")', lang='afan\_oromo') |
| :---- |

# **5\. Keyword Map Design**

The keyword map is the heart of each language adapter. It is a UTF-8 JSON file with two top-level objects: keywords and builtins.

| // adapters/afan\_oromo/keyword\_map.json  (excerpt) {   "$schema": "https://oromscript.dev/schemas/keyword\_map/v1.json",   "$lang": "afan\_oromo",   "$version": "1.0.0",   "$description": "Afan Oromo keyword mapping for OromScript",   "keywords": {     "if":       "yoo",     "else":     "yoo\_miti",     "elif":     "yookaan",     "for":      "hanga",     "while":    "yeroo",     "def":      "hojii",     "class":    "gosa",     "return":   "deebi",     "import":   "fidi",     "from":     "irra",     "as":       "akka",     "try":      "yaali",     "except":   "dogoggora",     "finally":  "dhuma",     "with":     "waliin",     "pass":     "itti\_fufuu",     "break":    "addaan\_kut",     "continue": "itti\_fufuu",     "and":      "fi",     "or":       "yookaan",     "not":      "miti",     "in":       "keessa",     "is":       "dha",     "lambda":   "hanga",     "True":     "Dhugaa",     "False":    "Sobaa",     "None":     "Wanti\_hin\_jirre"   },   "builtins": {     "print":    "agarsiisi",     "input":    "gaafadhu",     "len":      "dheerina",     "range":    "lakkoofsa",     "list":     "tarree",     "dict":     "galmee",     "str":      "barruu",     "int":      "lakki",     "float":    "lakki\_caccabaa",     "open":     "bani"   } } |
| :---- |

The schema at oromscript.dev/schemas/keyword\_map/v1.json enforces this structure and is validated in CI. Adding a new keyword requires: (1) add entry to keyword\_map.json, (2) add a test case, (3) open a PR.

| Design rule: 1-to-1 mapping only in v1 Each Python keyword maps to exactly one local keyword, and each local keyword maps to exactly one Python keyword. Many-to-one mappings (synonyms) are deferred to v2 to keep the lexer translation logic O(1) and deterministic. |
| :---- |

# **6\. Sample Afan Oromo Programs**

## **6.1 Hello World**

| Afan Oromo (.orm) \# Baga nagaan dhufte\! agarsiisi("Akkam, Addunyaa\!")  | Generated Python (.py) \# Baga nagaan dhufte\! print("Akkam, Addunyaa\!")  |
| :---- | :---- |

## **6.2 Functions and Conditionals**

| Afan Oromo (.orm) hojii faarfannaa(lakki):     yoo lakki % 2 \== 0:         deebi 'lakkoofsa lakkaa'     yoo\_miti:         deebi 'lakkoofsa baayyee' hanga i keessa lakkoofsa(1, 11):     agarsiisi(faarfannaa(i))  | Generated Python (.py) def faarfannaa(lakki):     if lakki % 2 \== 0:         return 'lakkoofsa lakkaa'     else:         return 'lakkoofsa baayyee' for i in range(1, 11):     print(faarfannaa(i))  |
| :---- | :---- |

## **6.3 Classes**

| Afan Oromo (.orm) gosa Barataa:     hojii \_\_init\_\_(of, maqaa, umri):         of.maqaa \= maqaa         of.umri  \= umri     hojii of\_ibsi(of):         agarsiisi(f'{of.maqaa}: {of.umri}') b \= Barataa('Chaltu', 20\) b.of\_ibsi()  | Generated Python (.py) class Barataa:     def \_\_init\_\_(self, maqaa, umri):         self.maqaa \= maqaa         self.umri  \= umri     def of\_ibsi(self):         print(f'{self.maqaa}: {self.umri}') b \= Barataa('Chaltu', 20\) b.of\_ibsi()  |
| :---- | :---- |

| Note on 'self' In the Afan Oromo adapter, 'self' is mapped to 'of' (meaning 'itself' / 'oneself' in Oromo). The keyword\_map.json entry is: "self": "of". Adapter authors can choose any culturally appropriate equivalent. |
| :---- |

# **7\. Repository Structure**

| transpiler-afan-oromo-script/ ├── .github/ │   ├── workflows/ │   │   ├── ci.yml              \# lint \+ test on every PR │   │   ├── release.yml         \# tag → PyPI publish │   │   └── docs.yml            \# build & deploy docs site │   ├── ISSUE\_TEMPLATE/ │   │   ├── bug\_report.md │   │   ├── keyword\_request.md  \# request a new Oromo keyword │   │   └── new\_language.md     \# request a new language adapter │   ├── PULL\_REQUEST\_TEMPLATE.md │   └── CODEOWNERS │ ├── adapters/                   \# Language adapter plugins │   └── afan\_oromo/ │       ├── keyword\_map.json │       ├── grammar\_hooks.py │       ├── error\_messages.json │       └── tests/ │           ├── test\_keywords.py │           └── corpus/         \# .orm \+ expected .py pairs │ ├── oromscript/                 \# Core library │   ├── \_\_init\_\_.py │   ├── lexer.py │   ├── parser.py │   ├── semantic.py │   ├── codegen.py │   ├── sourcemap.py │   ├── errors.py │   ├── adapter.py              \# AdapterRegistry │   └── cli.py                  \# Click CLI entry point │ ├── tests/                      \# Core engine tests │   ├── test\_lexer.py │   ├── test\_parser.py │   ├── test\_codegen.py │   ├── test\_cli.py │   └── test\_performance.py     \# benchmark vs raw Python │ ├── schemas/ │   └── keyword\_map/ │       └── v1.json             \# JSON Schema for keyword\_map.json │ ├── vscode-extension/           \# VS Code syntax highlighting │   ├── package.json │   ├── syntaxes/ │   │   └── afan\_oromo.tmLanguage.json │   └── README.md │ ├── docs/ │   ├── index.md │   ├── getting-started.md │   ├── keyword-reference.md │   ├── adding-a-language.md    \# step-by-step guide │   ├── architecture.md │   ├── api-reference.md │   └── contributing.md │ ├── examples/ │   ├── hello\_world.orm │   ├── fibonacci.orm │   ├── classes.orm │   └── web\_scraper.orm         \# real-world example │ ├── benchmarks/ │   └── bench.py                \# transpile-time \+ runtime benchmarks │ ├── CHANGELOG.md ├── CONTRIBUTING.md ├── CODE\_OF\_CONDUCT.md ├── LICENSE                     \# MIT ├── README.md ├── pyproject.toml              \# PEP 517/518 build config └── Makefile                    \# dev shortcuts |
| :---- |

# **8\. Performance Strategy**

The performance goal is that OromScript programs run indistinguishably from equivalent hand-written Python. This is achievable because the transpiler is a one-time preprocessing step — not an interpreter.

## **8.1 Transpilation Speed**

| Operation | Method | Target latency |
| :---- | :---- | :---- |
| Tokenise 1000-line file | Python tokenize (C extension) | \< 5 ms |
| Keyword translation | O(1) dict lookup per token | \< 1 ms |
| Parse | ast.parse() (CPython C) | \< 10 ms |
| Code gen | ast.unparse() (CPython C) | \< 2 ms |
| **Total transpile** | **—** | **\< 20 ms for any file** |

## **8.2 Runtime Performance**

* Generated .py is byte-for-byte equivalent to hand-written Python → CPython compiles it identically → zero runtime overhead

* Source-map JSON generation is optional (--map flag) and happens post-transpile

* **Caching:** oromscript run caches compiled .pyc next to the .orm file (in \_\_pycache\_\_) and skips re-transpilation if the .orm mtime has not changed — identical to how Python's own import cache works

## **8.3 Future: C Extension Option**

If transpilation speed ever becomes a bottleneck (e.g. transpiling thousands of files in a CI build), the lexer loop can be re-implemented as a C extension using CPython's C API. The interface is already designed with this in mind: OromLexer exposes a single tokenize() method whose return type would not change.

| Guideline Do not pre-optimise. Measure first with benchmarks/bench.py. The pure-Python implementation is the v1 baseline; a C extension is a v2 option only if benchmarks show a real bottleneck. |
| :---- |

# **9\. Adding a New Language (Amharic Example)**

This section is a step-by-step guide for a contributor who wants to add an Amharic adapter. The same steps apply to any language.

1. Scaffold the adapter directory:

| oromscript new-lang amharic \# Creates: adapters/amharic/keyword\_map.json (template) \#          adapters/amharic/error\_messages.json (template) \#          adapters/amharic/grammar\_hooks.py (no-op stub) \#          adapters/amharic/tests/ |
| :---- |

2. Fill in keyword\_map.json with Amharic equivalents:

| // adapters/amharic/keyword\_map.json (excerpt) {   "$lang": "amharic",   "keywords": {     "if":    "ከሆነ",     "else":  "ካልሆነ",     "for":   "ለ",     "def":   "ሥራ",     "class": "ዓይነት",     "return":"መልስ"   },   "builtins": {     "print": "አሳይ",     "input": "ጠይቅ"   } } |
| :---- |

3. Add error messages in error\_messages.json (Amharic text)

4. Add test corpus: pairs of .amh \+ expected .py files in adapters/amharic/tests/corpus/

5. Run tests:

| pytest adapters/amharic/tests/ \-v |
| :---- |

6. Validate keyword map schema:

| oromscript validate-adapter adapters/amharic/ |
| :---- |

7. Open a Pull Request — CI will run schema validation \+ tests automatically

| Time estimate A complete, tested adapter for a new language typically takes 4–8 hours: • 2 h — keyword translation (using a dictionary or LLM assistance) • 1 h — error message localisation • 2 h — writing test corpus • 1 h — PR \+ review cycle |
| :---- |

# **10\. CI/CD Pipeline**

**Figure 4 — CI/CD flow**

|   Developer pushes branch / opens PR          │          ▼   ┌─────────────────────────────────────────────┐   │              GitHub Actions: ci.yml          │   │  Triggers: push to any branch, PR to main   │   │                                             │   │  Jobs (parallel):                           │   │  ┌─────────┐ ┌─────────┐ ┌──────────────┐  │   │  │  lint   │ │  test   │ │ schema-valid  │  │   │  │ ruff    │ │ pytest  │ │ jsonschema    │  │   │  │ mypy    │ │ 3.10    │ │ all adapters  │  │   │  │ black   │ │ 3.11    │ └──────────────┘  │   │  └─────────┘ │ 3.12    │                   │   │              └─────────┘                   │   └────────────────────┬────────────────────────┘                        │ all green                        ▼               PR can be merged                        │                        │ merge to main                        ▼   ┌─────────────────────────────────────────────┐   │           GitHub Actions: docs.yml           │   │  Build MkDocs site → deploy to GitHub Pages │   └─────────────────────────────────────────────┘                        │                        │ maintainer tags v1.2.3                        ▼   ┌─────────────────────────────────────────────┐   │          GitHub Actions: release.yml         │   │  Build wheel \+ sdist → publish to PyPI      │   │  Build VS Code .vsix → publish to Marketplace│   └─────────────────────────────────────────────┘ |
| :---- |

## **10.1 ci.yml (annotated)**

| name: CI on:   push:     branches: \['\*\*'\]   pull\_request:     branches: \[main\] jobs:   lint:     runs-on: ubuntu-latest     steps:       \- uses: actions/checkout@v4       \- uses: actions/setup-python@v5         with: { python-version: '3.12' }       \- run: pip install ruff mypy black       \- run: ruff check oromscript/ adapters/       \- run: black \--check oromscript/ adapters/       \- run: mypy oromscript/   test:     runs-on: ubuntu-latest     strategy:       matrix:         python-version: \['3.10', '3.11', '3.12'\]     steps:       \- uses: actions/checkout@v4       \- uses: actions/setup-python@v5         with: { python-version: '${{ matrix.python-version }}' }       \- run: pip install \-e '.\[dev\]'       \- run: pytest tests/ adapters/\*/tests/ \-v \--tb=short       \- run: python benchmarks/bench.py \--ci   \# fail if \>20ms   schema:     runs-on: ubuntu-latest     steps:       \- uses: actions/checkout@v4       \- run: pip install jsonschema       \- run: python \-m oromscript.cli validate-adapter adapters/\*/ |
| :---- |

# **11\. Testing Strategy**

## **11.1 Test layers**

| Layer | What is tested | Tool |
| :---- | :---- | :---- |
| Unit | Lexer token translation, adapter loading, error formatting | pytest |
| Integration | Full .orm → .py round-trip for every keyword | pytest \+ corpus |
| Execution | .orm programs produce correct stdout/return values | pytest \+ subprocess |
| Performance | Transpile time \< 20 ms; generated .py runs at native speed | benchmarks/bench.py |
| Schema | Every keyword\_map.json validates against JSON Schema | jsonschema CLI |

## **11.2 Corpus test format**

Each integration test is a pair of files:

| adapters/afan\_oromo/tests/corpus/ ├── 001\_hello.orm          \# Oromo source ├── 001\_hello.py           \# Expected Python output ├── 002\_for\_loop.orm ├── 002\_for\_loop.py └── ... |
| :---- |

The test runner transpiles each .orm and diffs the output against the .py reference. Any diff is a test failure. New contributors adding keywords must add at least one corpus pair.

## **11.3 Coverage requirement**

* Core engine: ≥ 90% line coverage (enforced in CI via pytest-cov)

* Adapter keyword\_map.json: 100% of keywords must have at least one corpus test

* Error paths: every error code must have a test that triggers it

# **12\. Contribution Workflow**

**Figure 5 — PR lifecycle**

|   Contributor                 Maintainer       │                           │       │ fork repo                 │       │ create branch             │       │   feat/my-change          │       │                           │       │ make changes              │       │ run make test locally     │       │                           │       │──── open Pull Request ───►│       │                           │ CI runs automatically       │◄─── CI results ───────────│ (lint, test, schema)       │                           │       │ fix CI issues (if any)    │       │──── push fixes ──────────►│       │                           │ review \+ approve       │◄─── approval ─────────────│       │                           │       │                           │ squash merge to main       │                           │ CHANGELOG updated |
| :---- |

## **12.1 Branch naming**

| Prefix | Use case |
| :---- | :---- |
| feat/ | New feature or keyword |
| fix/ | Bug fix |
| lang/ | New language adapter |
| docs/ | Documentation only |
| chore/ | Tooling, CI, deps |

## **12.2 PR checklist (in PULL\_REQUEST\_TEMPLATE.md)**

* I have run make test and all tests pass

* I have added/updated tests for my change

* If adding a keyword: corpus pair .orm \+ .py added

* CHANGELOG.md updated under \[Unreleased\]

* Type annotations added/maintained (mypy clean)

* Docstrings updated for public API changes

## **12.3 Commit message convention (Conventional Commits)**

| feat(lexer): support multi-byte Oromo characters in identifiers fix(adapter): correct 'yoo\_miti' → 'else' mapping lang(amharic): add initial Amharic adapter docs: add step-by-step guide for adding a language chore(ci): upgrade actions/setup-python to v5 |
| :---- |

# **13\. Documentation Strategy**

All documentation lives in docs/ and is built with MkDocs \+ Material theme, deployed to GitHub Pages on every merge to main.

## **13.1 Documentation pages**

| Page | Audience & content |
| :---- | :---- |
| getting-started.md | End users — install, write first .orm file, run it |
| keyword-reference.md | End users — full table of all Oromo ↔ Python keywords |
| adding-a-language.md | Adapter authors — step-by-step guide (Section 9 above) |
| architecture.md | Core contributors — pipeline, design decisions, ADRs |
| api-reference.md | Library users — auto-generated from docstrings via mkdocstrings |
| contributing.md | All contributors — workflow, code style, CLA |

## **13.2 In-code documentation**

* Every public function/class has a Google-style docstring

* Every module has a module-level docstring explaining its role in the pipeline

* Architecture Decision Records (ADRs) live in docs/adr/ — one markdown file per decision

* **Example ADR:** docs/adr/001-use-ast-unparse-as-codegen.md — explains why we use ast.unparse() instead of a custom code generator

# **14\. Versioning & Release**

OromScript follows Semantic Versioning (SemVer 2.0). The Python package, VS Code extension, and keyword\_map.json schema are versioned independently but co-released.

## **14.1 Version matrix**

| Version bump | Trigger | Examples |
| :---- | :---- | :---- |
| PATCH (x.y.Z) | Bug fix, docs, no API change | Fix wrong keyword mapping |
| MINOR (x.Y.0) | New keyword, new feature, backward-compatible | Add 10 new builtins |
| MAJOR (X.0.0) | Breaking change to public API or keyword\_map schema | Rename a keyword, schema v2 |

## **14.2 Release steps (automated via release.yml)**

8. Maintainer creates and pushes a tag: git tag v1.2.3 && git push \--tags

9. release.yml triggers; builds wheel \+ sdist

10. Publishes to PyPI via OIDC trusted publishing (no stored secrets)

11. Builds VS Code .vsix and publishes to Marketplace

12. Creates GitHub Release with auto-generated notes from CHANGELOG.md

# **15\. Scalability Roadmap**

| Version | Theme | Key additions |
| :---- | :---- | :---- |
| v1.0 | Afan Oromo MVP | Full Python 3 parity, CLI, library, VS Code extension, docs |
| v1.x | Community adapters | Amharic, Tigrinya, Somali adapters contributed by community |
| v2.0 | Source maps \+ REPL | Full stack traces in Oromo, interactive REPL, DAP debugger support |
| v2.x | Synonym keywords | Allow multiple Oromo spellings per Python keyword |
| v3.0 | Multi-target IR | Optional IR layer enabling transpilation to JS/TypeScript |

# **16\. Security Considerations**

* **No code execution during transpilation:** the transpiler only parses and transforms ASTs — it never eval()s user code

* **Dependency minimisation:** core library has zero runtime dependencies beyond Python stdlib — reduces supply chain attack surface

* **Sandboxed execution:** oromscript run does not grant any additional permissions beyond what python itself would; the generated .py runs in a normal CPython process

* **JSON Schema validation:** keyword\_map.json is schema-validated before loading — prevents malformed adapter files from causing unexpected behaviour

* **No network access during transpile:** the transpiler is fully offline; no telemetry, no update checks