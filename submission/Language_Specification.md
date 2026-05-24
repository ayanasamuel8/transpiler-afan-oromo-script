# OromScript Language Specification

## 1. Overview

OromScript is a small beginner-focused programming language that uses **Afan Oromo** keywords and translates source files into **Python**. The goal is to let a new learner read program structure in a familiar language while still producing valid, readable Python code.

For the course project, OromScript is intentionally presented as a **small teaching language**, even though the underlying repository contains extra engineering features beyond the minimum assignment requirements.

- Source file extension: `.orm`
- Translation target: Python 3
- Translation model: source-to-source transpilation
- Main command: `python3 translator.py program.orm`

Example:

```orm
lakki = 5
yoo lakki > 3:
    agarsiisi("Guddaadha")
yoo_miti:
    agarsiisi("Xiqqaadha")
```

Generated Python:

```python
lakki = 5
if lakki > 3:
    print("Guddaadha")
else:
    print("Xiqqaadha")
```

## 2. Design Goals

The language was designed around four practical goals:

1. Replace English programming keywords with familiar Afan Oromo words.
2. Keep the syntax close to normal Python so beginners can transition later.
3. Reduce confusion by using readable, natural-looking control-flow words.
4. Produce valid Python automatically so learners can run their programs immediately.

## 3. Beginner-Friendly Design

OromScript helps beginners in three direct ways.

### 3.1 Local-language keywords

The most important structures of a program are written in Afan Oromo:

- `yoo` for `if`
- `yoo_miti` for `else`
- `yookaan` for `elif`
- `yeroo` for `while`
- `hojii` for `def`
- `deebi` for `return`
- `agarsiisi` for `print`

This reduces the “double learning burden” where a student must learn both programming logic and unfamiliar English control words at the same time.

### 3.2 Readable, natural-like structure

OromScript keeps Python’s indentation-based block structure instead of introducing heavy punctuation. A beginner sees a clear sequence:

- declare a value
- test a condition with `yoo`
- repeat with `yeroo`
- define a task with `hojii`

This keeps the language small and predictable.

### 3.3 Clear error reporting foundation

The implementation includes structured error types and an Afan Oromo error-message catalog. This is useful because a beginner mistake should be explained in a familiar language, not only with technical English terms. In the current implementation, this localization support exists in the adapter and error system, though some parser-level messages still come from Python.

## 4. Core Syntax Rules

### 4.1 Variables and assignment

Variables are created by simple assignment.

```orm
maqaa = "Bontu"
umri = 20
```

### 4.2 Expressions

Supported expression forms required for the course:

- Arithmetic: `+`, `-`, `*`, `/`
- Comparisons: `==`, `<`, `>`

Example:

```orm
idaama = 3 + 2
yoo idaama == 5:
    agarsiisi("Sirrii")
```

### 4.3 Conditionals

Conditional flow uses:

- `yoo` → `if`
- `yookaan` → `elif`
- `yoo_miti` → `else`

Example:

```orm
yoo marka > 80:
    agarsiisi("A")
yookaan marka > 60:
    agarsiisi("B")
yoo_miti:
    agarsiisi("C")
```

### 4.4 Loops

The required loop support is satisfied by `yeroo`, which maps to Python `while`.

```orm
lakki = 1
yeroo lakki < 4:
    agarsiisi(lakki)
    lakki = lakki + 1
```

The implementation also supports additional loop forms such as localized `for` syntax using `hanga ... keessa ...`.

### 4.5 Functions

Functions use:

- `hojii` → `def`
- `deebi` → `return`

Example:

```orm
hojii ida_i(a, b):
    deebi a + b

agarsiisi(ida_i(2, 3))
```

## 5. Keyword Summary

| OromScript | Python | Meaning |
| --- | --- | --- |
| `yoo` | `if` | conditional start |
| `yoo_miti` | `else` | fallback branch |
| `yookaan` | `elif` | extra condition |
| `yeroo` | `while` | repeat while true |
| `hojii` | `def` | define function |
| `deebi` | `return` | return a value |
| `agarsiisi` | `print` | display output |
| `Dhugaa` | `True` | boolean true |
| `Sobaa` | `False` | boolean false |
| `Wanti_hin_jirre` | `None` | empty / no value |

## 6. Implementation Summary

The translator is implemented as a real parsing pipeline, not simple text replacement.

### 6.1 Lexer

The lexer uses Python’s Unicode-aware tokenizer. It reads `.orm` source as UTF-8 and replaces recognized Afan Oromo identifiers such as `yoo` or `agarsiisi` with their Python equivalents while preserving the program structure.

### 6.2 Parser

After keyword translation, the parser reconstructs the source and builds a Python AST using `ast.parse()`. This guarantees that the translated program follows real Python syntax rules.

### 6.3 Semantic pass

A semantic analysis pass records names and source mapping information. In strict mode, it can report undefined-name errors.

### 6.4 Code generator

The code generator uses `ast.unparse()` to emit readable Python code. Because the translator goes through an AST, the output is structurally valid Python instead of pseudo-code.

## 7. Extra Features Beyond the Minimum Requirement

Although the course project only requires a small language, the repository also includes extra implemented features:

- class support through localized `gosa`
- `match/case` support through `walsimsiisi` and `haala`
- a command-line REPL
- an adapter system for adding other Ethiopian or local languages
- VS Code syntax-highlighting support
- optional source-map generation

These features are secondary in the course framing. The core teaching subset remains small.

## 8. Design Decisions

### 8.1 Why Python was chosen as the target language

Python was selected because it is readable, widely taught to beginners, and already uses indentation instead of many symbols. This matches the beginner-focused goals of OromScript. It also makes the generated code easy for a teacher to inspect.

### 8.2 Why the language stays close to Python

A fully new syntax would create more work for beginners later. OromScript instead localizes the **keywords**, but keeps the overall structure familiar to Python. This design gives two benefits:

- the learner starts in a familiar human language
- the learner can later move to standard Python with less friction

### 8.3 Why keyword localization is the main strategy

Beginners usually struggle first with control words like `if`, `else`, and `return`. Replacing those words gives the biggest educational benefit with the smallest implementation complexity. It improves readability without changing the meaning of the program.

### 8.4 Why the compiler uses parsing instead of text replacement

Pure find-and-replace is unreliable. It can break identifiers, strings, or nested syntax. OromScript instead tokenizes the program, parses it into an AST, and only then generates Python. This makes the translator more correct and satisfies the assignment rule that the solution must parse structure.

## 9. Why the Language Helps Beginners

OromScript helps beginners because it lowers three common barriers.

First, it lowers the **language barrier**. A student can understand program flow using familiar Afan Oromo words.

Second, it lowers the **syntax barrier**. The language uses indentation and a small set of keywords, so students are not overwhelmed by punctuation-heavy syntax.

Third, it lowers the **transition barrier**. Since the output is normal Python, students can compare their OromScript program with the generated Python and gradually learn the standard form.

## 10. Challenges in Local Language Design

Designing a local-language programming language introduced several practical challenges.

### 10.1 Choosing understandable keywords

Some programming ideas do not have a perfect everyday equivalent. The selected keywords must sound natural enough for learners while still being consistent and short enough to type.

### 10.2 Balancing familiarity and technical precision

A phrase that sounds natural in conversation is not always the best technical keyword. The design had to balance human readability with exact one-to-one mapping to Python behavior.

### 10.3 Unicode and text handling

A local-language language must handle Unicode correctly in source files, examples, and editor support. This affected file reading, tokenization, and documentation choices.

### 10.4 Avoiding over-design

It is tempting to translate everything or invent many new grammar forms. For beginners, that can become confusing. The better decision was to keep the system small and let Python’s proven structure do most of the heavy lifting.

### 10.5 Localized errors are harder than localized keywords

Keyword translation is relatively direct, but error reporting is more difficult because some syntax errors come from Python’s parser. Making every message fully natural in Afan Oromo requires additional interpretation work.

## 11. Example Programs

The repository includes a submission-ready set of examples in `submission/examples/`:

1. `basic_program.orm` for variables and arithmetic
2. `control_flow_program.orm` for `while` and `if/else`
3. `feature_demo.orm` for functions, return values, and an extra class feature

Each example includes the OromScript source, generated Python, and execution output.
