from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oromscript import transpile
from oromscript.errors import OrmError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate OromScript (.orm) source into Python (.py)."
    )
    parser.add_argument("source", type=Path, help="Path to the .orm source file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .py path. Defaults to the input filename with a .py extension.",
    )
    parser.add_argument(
        "--lang",
        default="afan_oromo",
        help="Language adapter to use. Default: afan_oromo",
    )
    parser.add_argument(
        "--map",
        dest="emit_map",
        action="store_true",
        help="Also write a simple source map next to the source file.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_path: Path = args.source
    output_path = args.output or source_path.with_suffix(".py")

    try:
        source = source_path.read_text(encoding="utf-8")
        result = transpile(source, lang=args.lang, emit_map=args.emit_map)
    except FileNotFoundError:
        print(f"File not found: {source_path}", file=sys.stderr)
        return 1
    except OrmError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if isinstance(result, tuple):
        py_source, map_json = result
    else:
        py_source, map_json = result, None

    output_path.write_text(py_source + "\n", encoding="utf-8")
    print(f"Written Python file: {output_path}")

    if args.emit_map and map_json is not None:
        map_path = source_path.with_suffix(".orm.map")
        map_path.write_text(map_json + "\n", encoding="utf-8")
        print(f"Written source map: {map_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
