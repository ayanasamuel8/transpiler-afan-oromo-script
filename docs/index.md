# OromScript

*Write Python in Afan Oromo — Execute Anywhere*

OromScript is an open-source, language-localisation transpiler platform that lets developers write Python programs using **Afan Oromo** keywords, identifiers, and idioms.

The transpiler parses Oromo-syntax source files (`.orm`), translates them into standard Python (3.10 or newer), and executes or outputs the result — with no measurable runtime overhead above Python itself.

## Core Value Proposition

Lower the barrier to programming for the 40+ million Afan Oromo speakers worldwide. It also provides a reusable, well-documented platform so any other language community (Amharic, Tigrinya, Somali, etc.) can add their own keyword layer seamlessly. 

## Features

- **Full Python Parity:** Every Python 3 construct has an Afan Oromo equivalent.
- **Zero Runtime Overhead:** Generated Python is fully identical to hand-written Python. CPython runs the output directly.
- **Language Plugin Architecture:** Add a new language by simply supplying one JSON keyword map.
- **Hand-written Lexer and Parser:** The lexer and the recursive descent parser are part of this project, not wrappers around Python's `tokenize` module. f-strings are parsed by the same code, including `=` debug fields, conversions and nested format specs. They keep the line and column of your original `.orm` source, so errors point at what you wrote.
- **Afan Oromo Aware:** Words with a hudhaa, such as `walitti_ida'i`, work with a straight or curly apostrophe. Names inside f-strings are translated too. `oromscript.graphemes` knows the letters of Afan Oromo: digraphs (`dh`), long vowels (`aa`), doubled consonants (`bb`) and the hudhaa. The parser attaches these as `Grapheme` nodes to every name in the tree (`node.graphemes`), and `split_graphemes` / `grapheme_len` work on plain words.
- **VS Code Support:** Syntax highlighting extension included.

## Examples

To view examples, check out the `examples/` directory containing concepts like loops, conditional statements, simple scripts, classes and `match`/`case` scenarios.

```bash
oromscript run examples/hello_world.orm
oromscript run examples/fibonacci.orm
```

## Quality

- The lexer and parser are tested against CPython itself: same syntax tree, same node positions, and the same accept/reject decisions on hundreds of snippets and on the Python standard library.
- Memory tests run the whole pipeline many times and fail if memory or live object counts grow.
- `python benchmarks/bench.py` reports time per stage, tokens per second, and memory growth. On a development laptop the lexer and parser handle about 230,000 to 330,000 tokens per second. The parse stage of a 1 MB file takes 0.25 to 0.45 seconds, and the whole transpile (with semantic analysis and code generation) about 1.2 to 1.3 seconds.

## Development

```bash
make test    # run the tests
make lint    # ruff, black, mypy
make bench   # run the benchmark
```

## Getting Started
See [Getting Started](getting-started.md).

## Contributing
See [Contributing](contributing.md) for contribution guidelines, including how to add new language adapters, submit pull requests, and the testing strategies in-place.

## License
MIT
