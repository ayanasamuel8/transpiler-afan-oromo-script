# OromScript Project Documentation

## 1. Language Specification

### 1.1 Project overview

OromScript is a small beginner-focused programming language that uses **Afan Oromo** keywords and translates source code into **Python**. The main goal is to help new learners understand programming concepts in a familiar local language while still producing valid, executable Python code.

This project is designed as a **source-to-source translator**:

```text
OromScript source (.orm) -> Python source (.py)
```

Although the repository contains some advanced extra features, this documentation presents OromScript as a **small and focused language for beginners**, matching the course requirements.

### 1.2 Target language

- Source language: OromScript
- Local language used: Afan Oromo
- Target language: Python
- Source file extension used in this project: `.orm`
- Output extension: `.py`

### 1.3 Language goals

The language was designed with these goals:

1. Make basic programming structure easier to read for Afan Oromo speakers.
2. Reduce beginner confusion caused by English keywords.
3. Keep the syntax simple and close to Python.
4. Generate valid Python code that can run immediately.
5. Stay small and focused rather than trying to become a completely new general-purpose language.

### 1.4 Beginner-friendly design

OromScript includes several beginner-friendly ideas.

#### Local-language keywords

The most important programming keywords are written in Afan Oromo. A learner sees:

- `yoo` instead of `if`
- `yoo_miti` instead of `else`
- `yookaan` instead of `elif`
- `yeroo` instead of `while`
- `hojii` instead of `def`
- `deebi` instead of `return`
- `agarsiisi` instead of `print`

This reduces the language barrier. A beginner can focus on logic first instead of struggling with unfamiliar English control words.

#### Readable natural-like syntax

The syntax is intentionally close to Python. OromScript uses indentation instead of many brackets or punctuation symbols. This makes blocks visually clear and easier to follow.

#### Learning bridge to Python

Since the translator produces normal Python, students can compare their OromScript code with generated Python and gradually learn the standard language.

#### Localized error support

The implementation includes structured error classes and an Afan Oromo error-message catalog. This helps move toward more understandable error feedback for beginners.

### 1.5 Keywords and meanings

The following are the main beginner-level keywords used in the course subset.

| OromScript | Python | Meaning |
| --- | --- | --- |
| `yoo` | `if` | start a condition |
| `yoo_miti` | `else` | alternative branch |
| `yookaan` | `elif` | additional condition |
| `yeroo` | `while` | repeat while condition is true |
| `hojii` | `def` | define a function |
| `deebi` | `return` | return a value from a function |
| `agarsiisi` | `print` | display output |
| `Dhugaa` | `True` | boolean true |
| `Sobaa` | `False` | boolean false |
| `Wanti_hin_jirre` | `None` | no value |

The implementation also supports additional localized forms, including:

- `hanga` for `for`
- `gosa` for `class`
- `walsimsiisi` for `match`
- `haala` for `case`

These are extra features beyond the minimum course requirements.

### 1.6 Syntax rules

#### Variables

Variables are created by assignment.

```orm
maqaa = "Bontu"
umri = 20
```

#### Arithmetic expressions

Supported arithmetic operators:

- `+`
- `-`
- `*`
- `/`

Example:

```orm
a = 4
b = 2
buaa = a + b
```

#### Comparison expressions

Supported comparisons:

- `==`
- `<`
- `>`

Example:

```orm
yoo buaa > 5:
    agarsiisi("Guddaadha")
```

#### Conditional statements

The language supports `if / else` using Afan Oromo keywords.

```orm
yoo lakki > 10:
    agarsiisi("Guddaadha")
yoo_miti:
    agarsiisi("Xiqqaadha")
```

It also supports an additional `elif`-style branch:

```orm
yoo marka > 80:
    agarsiisi("A")
yookaan marka > 60:
    agarsiisi("B")
yoo_miti:
    agarsiisi("C")
```

#### Loop

The required loop in this project is `while`, written as `yeroo`.

```orm
lakkoo = 1
yeroo lakkoo < 4:
    agarsiisi(lakkoo)
    lakkoo = lakkoo + 1
```

The implementation also supports localized `for` loops, but `while` is enough for the course requirement.

#### Functions

Functions are defined with `hojii` and return values using `deebi`.

```orm
hojii ida_i(a, b):
    deebi a + b
```

Function call:

```orm
agarsiisi(ida_i(2, 3))
```

### 1.7 Example mini program

```orm
hojii salaama(maqaa):
    agarsiisi("Akkam " + maqaa)

salaama("Bontu")
```

Generated Python:

```python
def salaama(maqaa):
    print("Akkam " + maqaa)

salaama("Bontu")
```

### 1.8 Implementation model

This project does **not** use pure text replacement. It uses a structured translation pipeline:

1. Read UTF-8 Oromo source code.
2. Tokenize the source using a Unicode-aware lexer.
3. Translate recognized Oromo keywords into Python token equivalents.
4. Parse the translated token stream into an AST.
5. Run a semantic pass.
6. Generate valid Python source code.

This satisfies the strict requirement that the translator must parse structure rather than simply replace words in raw text.

### 1.9 Unicode support

Unicode support is important because the source language is not English. The implementation reads files using UTF-8 and uses Python’s tokenizer, which supports Unicode text. This makes the project suitable for local-language programming and documentation.

### 1.10 Extra implemented features

Beyond the required course subset, the repository also includes:

- class support
- `match/case` support
- REPL support
- adapter/plugin support for additional languages
- VS Code syntax highlighting
- optional source-map generation

These features are not the main focus of the beginner course version, but they show the project can grow in the future.

## 2. Translator Implementation

The course deliverable requires a command-line translator. This project includes:

- `translator.py`

Usage:

```bash
python3 translator.py program.orm
```

This generates:

```text
program.py
```

Optional output path:

```bash
python3 translator.py program.orm -o output.py
```

### 2.1 Internal structure

The translator is implemented in phases.

#### Lexer

The lexer reads the OromScript source and translates localized keywords such as `yoo`, `hojii`, and `agarsiisi` into Python token equivalents.

#### Parser

The parser rebuilds the translated program and uses Python AST parsing to ensure the result follows real syntax rules.

#### Semantic analysis

A semantic pass builds basic scope information and can report some name-related errors.

#### Code generation

The final stage generates valid Python code using `ast.unparse()`.

This design was chosen because it is more correct and more maintainable than raw text replacement.

## 3. Test Programs

This section provides the three required test programs. Each one includes source code, generated Python, and execution output.

### 3.1 Basic program: variables and math

Source code:

```orm
lakkoofsa1 = 8
lakkoofsa2 = 4
idaama = lakkoofsa1 + lakkoofsa2
hirama = lakkoofsa1 / lakkoofsa2

agarsiisi("Idaama =", idaama)
agarsiisi("Hirama =", hirama)
```

Generated Python:

```python
lakkoofsa1 = 8
lakkoofsa2 = 4
idaama = lakkoofsa1 + lakkoofsa2
hirama = lakkoofsa1 / lakkoofsa2
print('Idaama =', idaama)
print('Hirama =', hirama)
```

Execution result:

```text
Idaama = 12
Hirama = 2.0
```

### 3.2 Control flow program

Source code:

```orm
lakkoo = 1
walitti_qabi = 0

yeroo lakkoo < 6:
    walitti_qabi = walitti_qabi + lakkoo
    lakkoo = lakkoo + 1

yoo walitti_qabi > 10:
    agarsiisi("Walitti qabamni guddaadha")
yoo_miti:
    agarsiisi("Walitti qabamni xiqqaadha")

agarsiisi("Bu'aa =", walitti_qabi)
```

Generated Python:

```python
lakkoo = 1
walitti_qabi = 0
while lakkoo < 6:
    walitti_qabi = walitti_qabi + lakkoo
    lakkoo = lakkoo + 1
if walitti_qabi > 10:
    print('Walitti qabamni guddaadha')
else:
    print('Walitti qabamni xiqqaadha')
print("Bu'aa =", walitti_qabi)
```

Execution result:

```text
Walitti qabamni guddaadha
Bu'aa = 15
```

### 3.3 Feature demonstration

This example demonstrates functions, return values, and one extra implemented feature: class support.

Source code:

```orm
hojii sadarkaa_kenni(marka):
    yoo marka > 80:
        deebi "A"
    yookaan marka > 60:
        deebi "B"
    yoo_miti:
        deebi "C"

gosa Barataa:
    hojii __init__(of, maqaa, marka):
        of.maqaa = maqaa
        of.marka = marka

    hojii agarsiisi_gatii(of):
        agarsiisi(of.maqaa + " => " + sadarkaa_kenni(of.marka))

barataa = Barataa("Bontu", 75)
barataa.agarsiisi_gatii()
```

Generated Python:

```python
def sadarkaa_kenni(marka):
    if marka > 80:
        return 'A'
    elif marka > 60:
        return 'B'
    else:
        return 'C'

class Barataa:

    def __init__(self, maqaa, marka):
        self.maqaa = maqaa
        self.marka = marka

    def agarsiisi_gatii(self):
        print(self.maqaa + ' => ' + sadarkaa_kenni(self.marka))

barataa = Barataa('Bontu', 75)
barataa.agarsiisi_gatii()
```

Execution result:

```text
Bontu => B
```

## 4. Short Report

### 4.1 Design decisions

The first design decision was to keep OromScript small and beginner-focused. Instead of building a completely different syntax, the project localizes the most important keywords into Afan Oromo while keeping the overall structure close to Python. This reduces learning difficulty and makes later transition to standard Python easier.

The second design decision was choosing Python as the target language. Python is already widely used in beginner education and has readable syntax. That makes it a strong backend for a local-language teaching language. It also means the generated code is easy for instructors to inspect and run.

The third design decision was to implement the translator as a real compiler pipeline with lexing, parsing, semantic analysis, and code generation. This was necessary both for correctness and for satisfying the assignment constraint that the project must not rely on simple word replacement.

### 4.2 Why the language helps beginners

OromScript helps beginners mainly because it reduces the language barrier. New learners can read control-flow words such as `yoo`, `yoo_miti`, `yeroo`, and `deebi` more naturally than English words such as `if`, `else`, `while`, and `return`. That lets the student focus on the underlying programming idea.

It also helps by keeping syntax visually simple. Indentation-based structure is easier for many beginners than symbol-heavy languages. Since the translated output is standard Python, students can compare both versions and learn how local-language code maps to industry-standard code.

### 4.3 Challenges, especially with local-language design

One challenge was selecting localized keywords that are short, understandable, and technically consistent. Some programming terms do not have one perfect direct equivalent in everyday language, so the design required balancing naturalness with precision.

Another challenge was Unicode handling. A local-language programming system must correctly process non-English text in source files, examples, and tooling. This makes correct UTF-8 handling essential.

A further challenge was avoiding naming collisions between localized builtins and user-defined identifiers. During testing, it became clear that local-language language design must carefully choose keywords and also encourage naming conventions that reduce ambiguity.

The final challenge was error localization. Translating keywords is relatively direct, but making parser and syntax errors fully natural in Afan Oromo is harder because some messages originate from Python parsing behavior. The current implementation includes a foundation for localized errors, but this remains an area for future improvement.

## 5. Conclusion

OromScript shows that a small local-language programming language can make beginner programming more approachable without losing connection to a standard target language. By using Afan Oromo keywords, structured parsing, Unicode support, and Python code generation, the project satisfies the course requirements while staying practical and focused.
