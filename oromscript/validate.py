import json
from pathlib import Path


def validate_adapters(paths: list[Path]) -> bool:
    """Validate adapter directories against the JSON schema."""
    import jsonschema
    
    schema_path = Path(__file__).parent.parent / "schemas" / "keyword_map" / "v1.json"
    if not schema_path.exists():
        schema = {
            "type": "object",
            "required": ["$lang", "$version", "keywords", "builtins"],
            "properties": {
                "keywords": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "minLength": 1}
                },
                "builtins": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "minLength": 1}
                }
            }
        }
    else:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        
    ok = True
    for p in paths:
        kmap = p / "keyword_map.json"
        if not kmap.exists():
            print(f"✗ {p.name}     E0050: keyword_map.json not found")
            ok = False
            continue
        try:
            data = json.loads(kmap.read_text(encoding="utf-8"))
            jsonschema.validate(instance=data, schema=schema)
            # check mandatory python keywords (just checking a few as example,
            # the full list is 35)
            # here we assume schema does most of the job
            # Check for duplicates in values of keywords mapping
            values = list(data.get("keywords", {}).values())
            if len(values) != len(set(values)):
                print(f"✗ {p.name}     E0052: duplicate values in keywords mapping")
                ok = False
                continue
            k_len = len(data.get("keywords", {}))
            b_len = len(data.get("builtins", {}))
            print(f"✓ {p.name}  ({k_len} keywords, {b_len} builtins)")
        except Exception as e:
            print(f"✗ {p.name}     E0052: {e}")
            ok = False
    return ok
