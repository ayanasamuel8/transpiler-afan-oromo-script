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
                "include": "#classes"
            },
            {
                "include": "#functions"
            },
            {
                "include": "#self"
            },
            {
                "include": "#keywords"
            },
            {
                "include": "source.python"
            }
        ],
        "repository": {
            "classes": {
                "match": r"(?x)\b(gosa)\s+([a-zA-Z_]\w*)",
                "captures": {
                    "1": {
                        "name": "keyword.control.class.afan-oromo"
                    },
                    "2": {
                        "name": "entity.name.type.class.afan-oromo"
                    }
                }
            },
            "functions": {
                "begin": r"(?x)\b(hojii)\s+([a-zA-Z_]\w*)\s*(\()",
                "beginCaptures": {
                    "1": {
                        "name": "keyword.control.def.afan-oromo"
                    },
                    "2": {
                        "name": "entity.name.function.afan-oromo"
                    },
                    "3": {
                        "name": "punctuation.definition.parameters.begin.afan-oromo"
                    }
                },
                "end": r"(\))",
                "endCaptures": {
                    "1": {
                        "name": "punctuation.definition.parameters.end.afan-oromo"
                    }
                },
                "patterns": [
                    {
                        "match": r"\bof\b",
                        "name": "variable.language.special.self.afan-oromo"
                    },
                    {
                        "match": r"([a-zA-Z_]\w*)",
                        "captures": {
                            "1": {
                                "name": "variable.parameter.function.language.afan-oromo"
                            }
                        }
                    },
                    {
                        "match": r",",
                        "name": "punctuation.separator.parameters.afan-oromo"
                    }
                ]
            },
            "self": {
                "match": r"\bof\b",
                "name": "variable.language.special.self.afan-oromo"
            },
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