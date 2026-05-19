# OromScript Error Codes Reference

All error codes, their trigger conditions, and available `context` substitution variables
for use in `error_messages.json`.

---

## Error Code Table

| Code  | Class           | Trigger                                      | Context Variables              |
|-------|-----------------|----------------------------------------------|--------------------------------|
| E0001 | OrmLexError     | Tokenisation failure (bad character/encoding)| `{token}`, `{line}`, `{col}`  |
| E0010 | OrmSyntaxError  | ast.parse() fails (syntax error)             | `{line}`, `{col}`, `{text}`   |
| E0011 | OrmSyntaxError  | Indentation error                            | `{line}`, `{col}`             |
| E0012 | OrmSyntaxError  | Mixed keyword languages detected             | `{line}`, `{local}`, `{py}`   |
| E0020 | OrmNameError    | Undefined name in strict mode                | `{name}`, `{line}`, `{col}`   |
| E0030 | OrmAdapterError | Grammar hook raised an exception             | `{hook}`, `{error}`           |
| E0050 | OrmAdapterError | keyword_map.json missing from adapter dir    | `{lang}`, `{dir}`             |
| E0051 | OrmAdapterError | Language not registered in AdapterRegistry   | `{lang}`, `{available}`       |
| E0052 | OrmAdapterError | keyword_map.json fails schema validation     | `{lang}`, `{field}`, `{error}`|
| E0060 | OrmError        | --strict: local keyword used in wrong context| `{token}`, `{line}`           |

---

## Afan Oromo error_messages.json (reference)

```json
{
  "E0001": "Dogoggora: Qubee '{token}' sirrii miti — sarara {line}, tuqaa {col}",
  "E0010": "Dogoggora caasaa — sarara {line}, tuqaa {col}: {text}",
  "E0011": "Dogoggora wawwaltoo (indentation) — sarara {line}",
  "E0012": "Jechoota Afaan Oromoo fi Python walitti hin makatin — sarara {line}: '{local}' fi '{py}'",
  "E0020": "Maqaan '{name}' hin beekamu — sarara {line}, tuqaa {col}",
  "E0030": "Dogoggora hook caasaa — '{hook}': {error}",
  "E0050": "keyword_map.json afaan '{lang}' keessa '{dir}' hin argamne",
  "E0051": "Afaan '{lang}' hin deeggeramu. Afaanota deeggeraman: {available}",
  "E0052": "keyword_map.json afaan '{lang}' sirrii miti — '{field}': {error}",
  "E0060": "Jechamni '{token}' iddoo dha'uuf qabamu hin dha'u — sarara {line}"
}
```

---

## How error messages are rendered

```python
# oromscript/errors.py — ErrorRenderer (to be implemented)
class ErrorRenderer:
    def __init__(self, lang: str) -> None:
        adapter = AdapterRegistry.get(lang)
        self._templates = adapter.error_messages

    def render(self, error: OrmError) -> str:
        template = self._templates.get(error.code, error.message)
        try:
            msg = template.format(**error.context, line=error.orm_line, col=error.orm_col)
        except KeyError:
            msg = template  # Fallback: un-interpolated template
        return (
            f"error[{error.code}] sarara {error.orm_line}, tuqaa {error.orm_col}:\n"
            f"  {msg}\n"
        )
```

---

## Adding a new error code

1. Add the code to this table (update `references/error_codes.md`).
2. Raise it in the appropriate pipeline stage using the correct `OrmError` subclass.
3. Add the code to ALL adapter `error_messages.json` files (CI validates coverage).
4. Add a test that triggers the error: `pytest tests/ -k "E0052"`.
