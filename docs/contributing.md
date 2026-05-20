# Contributing to OromScript

We welcome contributions of all forms—bug reports, feature requests, new language adapters, and code contributions. 

## Contribution Workflow

1. **Fork & Clone** the repository.
2. **Branching**:
   - `feat/` for new features or keywords
   - `fix/` for bug fixes
   - `lang/` for new language adapters
   - `docs/` for documentation
   - `chore/` for tooling and deps
3. **Make changes** and ensure `make test` runs cleanly.
4. **Open a Pull Request** to the `main` branch.

## Adding a New Language Adapter

Using OromScript's plugin infrastructure, it's easy to add a new language. You primarily need to supply a JSON keyword map and an error messages set.

1. **Scaffold**: `oromscript new-lang amharic` (for Amharic)
2. **Translate Keywords**: Edit `adapters/<lang>/keyword_map.json` mapping each Python keyword/builtin to local equivalents.
3. **Localize Errors**: Fill `error_messages.json` with appropriate translated syntax errors.
4. **Test Corpus**: Add testing `.orm` and expected `.py` pairs in `adapters/<lang>/tests/corpus/`
5. **Validate Schema**: Run `oromscript validate-adapter adapters/<lang>/`
6. **Submit PR**.

## Testing & Coverage

- We require **100%** of keywords in `keyword_map.json` to have at least one corpus test.
- Every mapped error path should trigger properly in tests.
- Core engine coverage requirement is ≥ 90%.

For more details on the architecture, see [Architecture](architecture.md) and [Design Specification](OromScript_Design_Specification.md).
