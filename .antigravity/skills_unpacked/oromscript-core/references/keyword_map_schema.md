# keyword_map.json — Schema & Validation Reference

Every language adapter **must** contain a `keyword_map.json` that conforms to this schema.
The schema lives at `schemas/keyword_map/v1.json` in the repo and is validated in CI.

---

## Full Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://oromscript.dev/schemas/keyword_map/v1.json",
  "title": "OromScript keyword_map",
  "description": "Maps Python keywords and builtins to a local language equivalent.",
  "type": "object",
  "required": ["$lang", "$version", "keywords", "builtins"],
  "additionalProperties": false,
  "properties": {
    "$schema":      { "type": "string" },
    "$lang":        { "type": "string", "pattern": "^[a-z_]+$",
                      "description": "Snake_case language identifier, e.g. afan_oromo" },
    "$version":     { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "$description": { "type": "string" },
    "keywords": {
      "type": "object",
      "description": "Python keyword → local-language equivalent (1-to-1 in v1)",
      "additionalProperties": { "type": "string", "minLength": 1 }
    },
    "builtins": {
      "type": "object",
      "description": "Python builtin name → local-language equivalent",
      "additionalProperties": { "type": "string", "minLength": 1 }
    }
  }
}
```

---

## Mandatory Python Keywords (must all appear in `keywords`)

```
False    await    else     import   pass
None     break    except   in       raise
True     class    finally  is       return
and      continue for      lambda   try
as       def      from     nonlocal while
assert   del      global   not      with
async    elif     if       or       yield
```

---

## Recommended Builtins (cover in `builtins`)

```
print   input   len    range   list   dict   set   tuple
str     int     float  bool    type   open   zip   map
filter  sorted  sum    min     max    abs    round enumerate
```

---

## Afan Oromo Reference Map (complete)

```json
{
  "$schema": "https://oromscript.dev/schemas/keyword_map/v1.json",
  "$lang": "afan_oromo",
  "$version": "1.0.0",
  "$description": "Afan Oromo keyword mapping for OromScript",
  "keywords": {
    "False":    "Sobaa",
    "None":     "Wanti_hin_jirre",
    "True":     "Dhugaa",
    "and":      "fi",
    "as":       "akka",
    "assert":   "mirkaanessi",
    "async":    "yeroo_eeguu",
    "await":    "eegi",
    "break":    "addaan_kut",
    "class":    "gosa",
    "continue": "itti_fufuu",
    "def":      "hojii",
    "del":      "haqi",
    "elif":     "yookaan",
    "else":     "yoo_miti",
    "except":   "dogoggora",
    "finally":  "dhuma",
    "for":      "hanga",
    "from":     "irra",
    "global":   "addunyaa",
    "if":       "yoo",
    "import":   "fidi",
    "in":       "keessa",
    "is":       "dha",
    "lambda":   "hojii_gabaabaa",
    "nonlocal": "naannoo_miti",
    "not":      "miti",
    "or":       "yookaan_immoo",
    "pass":     "darbii",
    "raise":    "ol_kaasi",
    "return":   "deebi",
    "try":      "yaali",
    "while":    "yeroo",
    "with":     "waliin",
    "yield":    "kennii",
    "yield from": "kennii_irra"
  },
  "builtins": {
    "print":     "agarsiisi",
    "input":     "gaafadhu",
    "len":       "dheerina",
    "range":     "lakkoofsa",
    "list":      "tarree",
    "dict":      "galmee",
    "set":       "walitti_qabama",
    "tuple":     "tarree_cufamaa",
    "str":       "barruu",
    "int":       "lakki",
    "float":     "lakki_caccabaa",
    "bool":      "dhugaa_sobaa",
    "type":      "gosa_data",
    "open":      "bani",
    "zip":       "walitti_makami",
    "map":       "jijjiiri",
    "filter":    "caalbaasi",
    "sorted":    "tartiibessi",
    "sum":       "walitti_ida'i",
    "min":       "xiqqaa",
    "max":       "guddaa",
    "abs":       "gatii_dhugaa",
    "round":     "marsii",
    "enumerate": "lakkaa_fi_argadhu",
    "self":      "of",
    "super":     "abbaa_gosa"
  }
}
```

---

## Validation Command

```bash
# Validate a specific adapter
python -m oromscript.cli validate-adapter adapters/afan_oromo/

# Validate all adapters (run in CI)
python -m oromscript.cli validate-adapter adapters/*/
```

The validator checks:
1. JSON is valid UTF-8
2. Schema compliance (all required keys present)
3. No duplicate values within `keywords` (would create ambiguous reverse-lookup)
4. All mandatory Python keywords are covered
5. Values are non-empty strings
