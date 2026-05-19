---
name: oromscript-ci
description: >
  Set up, maintain, or debug the OromScript CI/CD pipeline, release process,
  and documentation infrastructure. Use this skill whenever the task involves:
  GitHub Actions workflows (ci.yml, release.yml, docs.yml), branch protection rules,
  CODEOWNERS, issue/PR templates, semantic versioning and tagging, PyPI publishing,
  VS Code Marketplace publishing, MkDocs documentation site, CHANGELOG maintenance,
  Conventional Commits, pyproject.toml build configuration, ruff/mypy/black linting
  config, or any DevOps/workflow concern. Also use when explaining the contribution
  process to a new contributor or reviewing CI failures.
---

# OromScript CI/CD, Release & Documentation

---

## GitHub Actions Workflows

### .github/workflows/ci.yml — runs on every push & PR

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  # ── Job 1: Lint ───────────────────────────────────────────────────────────
  lint:
    name: Lint & type-check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install linting tools
        run: pip install ruff mypy black

      - name: ruff (fast linter)
        run: ruff check oromscript/ adapters/ tests/

      - name: black (formatter check)
        run: black --check oromscript/ adapters/ tests/

      - name: mypy (type checker)
        run: mypy oromscript/ --strict

  # ── Job 2: Test matrix ────────────────────────────────────────────────────
  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install project + dev deps
        run: pip install -e ".[dev]"

      - name: Run tests with coverage
        run: >
          pytest tests/ adapters/*/tests/ -v --tb=short
          --cov=oromscript --cov-report=xml --cov-fail-under=90

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          flags: python-${{ matrix.python-version }}

  # ── Job 3: Performance gate ───────────────────────────────────────────────
  bench:
    name: Performance benchmark
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e .
      - name: Run benchmark (fail if > budget)
        run: python benchmarks/bench.py --ci

  # ── Job 4: Schema validation ──────────────────────────────────────────────
  schema:
    name: Validate adapter schemas
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e .
      - name: Validate all adapters
        run: python -m oromscript.cli validate-adapter adapters/*/
```

---

### .github/workflows/docs.yml — deploy docs on merge to main

```yaml
name: Deploy Docs

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}

    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }

      - name: Install docs dependencies
        run: pip install mkdocs-material mkdocstrings[python]

      - name: Build docs site
        run: mkdocs build --strict

      - uses: actions/upload-pages-artifact@v3
        with: { path: site/ }

      - uses: actions/deploy-pages@v4
        id: deployment
```

---

### .github/workflows/release.yml — triggered by version tags

```yaml
name: Release

on:
  push:
    tags: ["v[0-9]+.[0-9]+.[0-9]+"]

permissions:
  contents: write
  id-token: write   # Required for PyPI OIDC trusted publishing

jobs:
  publish-pypi:
    name: Build & publish to PyPI
    runs-on: ubuntu-latest
    environment: pypi-release

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }

      - name: Install build tools
        run: pip install build

      - name: Build wheel + sdist
        run: python -m build

      - name: Publish to PyPI (OIDC — no stored secret needed)
        uses: pypa/gh-action-pypi-publish@release/v1

  publish-vscode:
    name: Publish VS Code extension
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }

      - name: Install vsce
        run: npm install -g @vscode/vsce

      - name: Package extension
        run: vsce package
        working-directory: vscode-extension/

      - name: Publish to Marketplace
        run: vsce publish --pat ${{ secrets.VSCODE_MARKETPLACE_TOKEN }}
        working-directory: vscode-extension/

  github-release:
    name: Create GitHub Release
    runs-on: ubuntu-latest
    needs: [publish-pypi]
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - name: Extract CHANGELOG section for this version
        id: changelog
        run: |
          VERSION=${GITHUB_REF_NAME#v}
          python scripts/extract_changelog.py $VERSION > release_notes.md

      - uses: softprops/action-gh-release@v2
        with:
          body_path: release_notes.md
          generate_release_notes: false
```

---

## Branch Protection Rules (main)

Configure in GitHub → Settings → Branches → Branch protection rules:

| Setting | Value |
|---------|-------|
| Require status checks to pass | ✓ |
| Required checks | `lint`, `test (3.10)`, `test (3.11)`, `test (3.12)`, `schema`, `bench` |
| Require branches to be up to date | ✓ |
| Require pull request reviews | 1 approval |
| Dismiss stale reviews | ✓ |
| Require conversation resolution | ✓ |
| Restrict force pushes | ✓ |
| Restrict deletions | ✓ |

---

## CODEOWNERS (.github/CODEOWNERS)

```
# Default: all maintainers review everything
*                           @ayanasamuel8

# Language adapters: adapter authors are owners of their adapter
adapters/afan_oromo/        @ayanasamuel8
adapters/amharic/           @amharic-adapter-maintainer

# Core engine: requires senior maintainer review
oromscript/                 @ayanasamuel8
schemas/                    @ayanasamuel8
```

---

## pyproject.toml — Full Configuration

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "oromscript"
version = "1.0.0"
description = "Write Python in Afan Oromo and other local languages"
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.10"
authors = [{ name = "Ayana Samuel", email = "ayanasamuel8@github.com" }]
keywords = ["transpiler", "afan-oromo", "localisation", "python"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Intended Audience :: Developers",
  "Intended Audience :: Education",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Topic :: Software Development :: Compilers",
  "Topic :: Software Development :: Internationalization",
]
dependencies = [
  "click>=8.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-cov>=5.0",
  "mypy>=1.10",
  "ruff>=0.4",
  "black>=24.0",
  "jsonschema>=4.22",
]
docs = [
  "mkdocs-material>=9.5",
  "mkdocstrings[python]>=0.25",
]

[project.scripts]
oromscript = "oromscript.cli:main"

[project.entry-points."oromscript.adapters"]
# Built-in adapter auto-registered — community adapters add their own entries here
afan_oromo = "adapters.afan_oromo"

[project.urls]
Homepage = "https://github.com/ayanasamuel8/transpiler-afan-oromo-script"
Documentation = "https://ayanasamuel8.github.io/transpiler-afan-oromo-script"
Repository = "https://github.com/ayanasamuel8/transpiler-afan-oromo-script"
Issues = "https://github.com/ayanasamuel8/transpiler-afan-oromo-script/issues"

[tool.ruff]
line-length = 88
target-version = "py310"
select = ["E", "F", "I", "UP", "B", "SIM", "S"]
ignore = ["S101"]   # allow assert in tests

[tool.mypy]
python_version = "3.10"
strict = true
exclude = ["adapters/", "tests/", "benchmarks/"]

[tool.black]
line-length = 88
target-version = ["py310", "py311", "py312"]

[tool.pytest.ini_options]
testpaths = ["tests", "adapters"]
addopts = ["--tb=short", "--strict-markers", "-q"]
markers = [
  "slow: marks tests as slow",
  "corpus: marks corpus round-trip tests",
  "perf: marks performance tests",
]

[tool.coverage.run]
source = ["oromscript"]

[tool.coverage.report]
fail_under = 90
show_missing = true
```

---

## Versioning & Release Process

### SemVer Rules

| Bump | When | Examples |
|------|------|---------|
| PATCH (x.y.**Z**) | Bug fix, no API change | Fix wrong keyword, fix error message |
| MINOR (x.**Y**.0) | New keyword/feature, backward-compatible | Add builtins, new CLI flag |
| MAJOR (**X**.0.0) | Breaking API or schema change | Rename keyword, schema v2 |

### Release Steps

1. Update `CHANGELOG.md` — move `[Unreleased]` items under new `[vX.Y.Z] - YYYY-MM-DD`.
2. Bump version in `pyproject.toml`.
3. Commit: `chore(release): v1.2.3`.
4. Tag: `git tag v1.2.3 && git push --tags`.
5. `release.yml` triggers automatically → PyPI + VS Code Marketplace + GitHub Release.

### CHANGELOG.md Format

```markdown
# Changelog

All notable changes to OromScript are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [SemVer](https://semver.org/)

## [Unreleased]

### Added
- ...

### Fixed
- ...

## [1.0.0] - 2025-05-01

### Added
- Initial release: full Python 3.12 parity for Afan Oromo
- CLI: run, compile, check, repl, new-lang, validate-adapter
- VS Code syntax highlighting extension
- Corpus test suite with 50+ test pairs
```

---

## PR & Issue Templates

### .github/PULL_REQUEST_TEMPLATE.md

```markdown
## Summary
<!-- What does this PR do? One sentence. -->

## Type of change
- [ ] Bug fix (fixes #<issue>)
- [ ] New feature
- [ ] New language adapter (`lang/<name>`)
- [ ] Documentation
- [ ] Chore (CI, deps, tooling)

## Checklist
- [ ] `make test` passes locally
- [ ] New/updated tests added for every change
- [ ] If adding a keyword: corpus pair (.orm + .py) added
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Type annotations maintained (`mypy --strict` clean)
- [ ] Docstrings updated for public API changes
- [ ] No new runtime dependencies added without discussion
```

### .github/ISSUE_TEMPLATE/new_language.md

```markdown
---
name: New Language Adapter
about: Request or announce a new language adapter
labels: [enhancement, new-language]
---

## Language Details
- **Language name:** (e.g. Amharic)
- **ISO code:** (e.g. am)
- **Native speakers:** (approx.)
- **Script:** (e.g. Ethiopic/Ge'ez)

## Adapter author
- [ ] I am implementing this adapter myself
- [ ] I am requesting that someone else implement this

## Checklist (for implementors)
- [ ] `oromscript new-lang <name>` scaffolded
- [ ] All 35 Python keywords mapped
- [ ] At least 15 builtins mapped
- [ ] error_messages.json complete
- [ ] Corpus: ≥ 20 test pairs
- [ ] `oromscript validate-adapter` passes
- [ ] `pytest adapters/<name>/tests/` passes
```

---

## MkDocs Configuration (mkdocs.yml)

```yaml
site_name: OromScript
site_url: https://ayanasamuel8.github.io/transpiler-afan-oromo-script
repo_url: https://github.com/ayanasamuel8/transpiler-afan-oromo-script
repo_name: ayanasamuel8/transpiler-afan-oromo-script

theme:
  name: material
  palette:
    - scheme: default
      primary: green
      accent: teal
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy
    - search.suggest

nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Keyword Reference: keyword-reference.md
  - Adding a Language: adding-a-language.md
  - Architecture: architecture.md
  - API Reference: api-reference.md
  - Contributing: contributing.md
  - Changelog: CHANGELOG.md

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.superfences
  - admonition
  - tables
```

---

## Conventional Commits Reference

All commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

Types:    feat | fix | docs | style | refactor | perf | test | chore | lang
Scopes:   lexer | parser | semantic | codegen | cli | adapter | ci | docs | repl

Examples:
  feat(lexer): add support for multi-byte identifiers
  fix(adapter): correct 'yoo_miti' → 'else' translation
  lang(amharic): add initial Amharic adapter
  test(corpus): add class inheritance corpus pair
  docs(adding-a-language): add Tigrinya walkthrough
  chore(ci): upgrade actions/setup-python to v5
  perf(lexer): merge keyword+builtin maps at init time
```

Breaking changes: append `!` after type/scope: `feat(api)!: rename transpile() return type`.
