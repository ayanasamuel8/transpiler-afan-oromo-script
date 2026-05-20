# Adding a Language

OromScript is designed to support arbitrary spoken languages via an **Adapter System**. Adapters are lightweight JSON definitions that map Python language structures to local language words.

## Creating an Adapter

1. Inside the `adapters/` folder, create a new directory for your language (e.g., `adapters/amharic/`).
2. Inside that directory, create a `keyword_map.json` file.
3. Map Python keywords to your target language:

```json
{
  "$schema": "https://oromscript.dev/schemas/keyword_map/v1.json",
  "$lang": "amharic",
  "$version": "1.0.0",
  "keywords": {
    "def": "tegbari",
    "if": "kehone",
    "print": "atmi"
  },
  "builtins": {
    "str": "tsehufe"
  }
}
```

## Validating the Adapter
You can use the built-in validator to ensure your schema is correct:
```bash
oromscript validate-adapter adapters/amharic/
```
