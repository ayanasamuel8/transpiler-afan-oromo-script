# Architecture

The OromScript transpiler pipeline is designed to be fully standard-compliant with modern Python, meaning its output is standard Python code. The pipeline consists of the following core stages:

1. **Lexer** (`oromscript.lexer`): Tokenizes the local language source code and maps keywords (e.g., `hojii` -> `def`).
2. **Parser** (`oromscript.parser`): Transforms the token stream into a Python Abstract Syntax Tree (AST).
3. **Semantic Analysis** (`oromscript.semantic`): Validates the AST and prepares source-map information.
4. **Code Generation** (`oromscript.codegen`): Traverses the AST to reconstruct perfectly formatted Python source code using `ast.unparse`.

For a full breakdown of the system design, read the [OromScript Design Specification](OromScript_Design_Specification.md).
