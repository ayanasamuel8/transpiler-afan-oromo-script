# OromScript

*Write Python in Afan Oromo — Execute Anywhere*

OromScript is an open-source, language-localisation transpiler platform that lets developers write Python programs using **Afan Oromo** keywords, identifiers, and idioms.

The transpiler parses Oromo-syntax source files (`.orm`), translates them into standard Python 3.12+, and executes or outputs the result — with no measurable runtime overhead above Python itself.

## Core Value Proposition

Lower the barrier to programming for the 40+ million Afan Oromo speakers worldwide. It also provides a reusable, well-documented platform so any other language community (Amharic, Tigrinya, Somali, etc.) can add their own keyword layer seamlessly. 

## Features

- **Full Python Parity:** Every Python 3 construct has an Afan Oromo equivalent.
- **Zero Runtime Overhead:** Generated Python is fully identical to hand-written Python. CPython runs the output directly.
- **Language Plugin Architecture:** Add a new language by simply supplying one JSON keyword map.
- **VS Code Support:** Syntax highlighting extension included.

## Examples

To view examples, check out the `examples/` directory containing concepts like loops, conditional statements, simple scripts, classes and `match`/`case` scenarios.

```bash
oromscript run examples/hello_world.orm
oromscript run examples/fibonacci.orm
```

## Getting Started
See [Getting Started](getting-started.md).

## Contributing
See [Contributing](contributing.md) for contribution guidelines, including how to add new language adapters, submit pull requests, and the testing strategies in-place.

## License
MIT
