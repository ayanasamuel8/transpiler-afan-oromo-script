# Short Report

## Design decisions

The main design decision was to keep OromScript small and beginner-focused by localizing **keywords** instead of inventing a completely different programming model. This keeps the language readable for Afan Oromo speakers while preserving a direct path to standard Python. Python was chosen as the target language because it is widely used in beginner programming, has readable syntax, and allows the translator to generate valid executable code with minimal extra complexity.

A second important decision was to implement the translator as a real compilation pipeline: lexing, parsing, semantic analysis, and code generation. This was better than simple text replacement because it preserves program structure and produces reliable Python output. The design also keeps the language open for future growth, which is why the repository includes extra features such as classes, `match/case`, a REPL, and an adapter system for more languages.

## Why the language helps beginners

OromScript reduces beginner confusion by presenting core programming ideas in Afan Oromo. Students can read `yoo`, `yoo_miti`, `yeroo`, `hojii`, and `deebi` more naturally than English keywords such as `if`, `else`, `while`, `def`, and `return`. This reduces the language barrier and lets the learner focus on logic first.

The language also remains close to Python, which helps learners transition later. They can compare the `.orm` source with the generated `.py` file and see exactly how local-language constructs map to standard Python. This makes OromScript useful not only as a programming language, but also as a learning bridge.

## Challenges

The biggest challenge was local-language design itself. Some programming terms do not have one perfect everyday equivalent, so keyword selection required balancing clarity, consistency, and technical correctness. Another challenge was Unicode support, because source files and tooling must handle non-English text reliably.

Another practical challenge was avoiding clashes between localized keywords or builtins and user-defined names. During testing, a variable name close to a localized builtin created confusing output, which shows that local-language language design must think carefully about keyword selection and naming conventions.

Error localization was also more difficult than keyword localization. Keywords can be mapped directly, but syntax and parser errors may still come from Python internals. For that reason, the project includes a localized error-message foundation, but fully natural end-to-end error reporting remains a harder problem than keyword translation alone.
