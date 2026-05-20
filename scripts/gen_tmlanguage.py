import json
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python gen_tmlanguage.py <keyword_map.json>")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)

    keywords = list(data.get("keywords", {}).values())
    builtins = list(data.get("builtins", {}).values())

    # Create the grammar dictionary
    grammar = {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "Afan Oromo",
        "scopeName": "source.afan-oromo",
        "patterns": [
            {
                "include": "#keywords"
            },
            {
                "include": "source.python"
            }
        ],
        "repository": {
            "keywords": {
                "patterns": [
                    {
                        "name": "keyword.control.afan-oromo",
                        "match": r"\b(" + "|".join(keywords) + r")\b"
                    },
                    {
                        "name": "support.function.builtin.afan-oromo",
                        "match": r"\b(" + "|".join(builtins) + r")\b"
                    }
                ]
            }
        }
    }

    print(json.dumps(grammar, indent=2))

if __name__ == "__main__":
    main()