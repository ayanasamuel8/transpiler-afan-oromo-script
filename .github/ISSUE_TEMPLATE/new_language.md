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
