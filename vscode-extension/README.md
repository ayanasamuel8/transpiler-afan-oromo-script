# OromScript VS Code Extension

OromScript is a transpiler that allows you to write Python using syntax in your local language (Afan Oromo).

This extension provides syntax highlighting for `.orm` files in Visual Studio Code.

## Features

- Syntax highlighting for Afan Oromo (`.orm`) source files.
- Reuses Python syntax for non-keyword elements.

## Installation

To install this extension on a new device, you will need to package it into a `.vsix` file and install it manually in VS Code.

### Requirements

- Node.js and `npm` installed.
- VS Code CLI (`code`) available in your terminal.

### Steps to Install

1. Open your terminal and navigate to the `vscode-extension` directory:
   ```bash
   cd path/to/transpiler-afan-oromo-script/vscode-extension
   ```
2. Package the extension using `vsce`:
   ```bash
   npx @vscode/vsce package
   ```
3. Install the generated `.vsix` file via the VS Code CLI:
   ```bash
   code --install-extension oromscript-1.0.0.vsix
   ```
   *(Alternatively, you can install it via the VS Code UI: Go to the Extensions view > Click the `...` menu at the top right > "Install from VSIX..." and select the generated file.)*

## Development

If you add new keywords to the language (in the `adapters/afan_oromo/keyword_map.json`), you'll need to update the syntax highlighting grammar.

1. From the **root** of the project, run the `gen_tmlanguage.py` script via the Makefile target:
   ```bash
   make dev-ext
   ```
2. Navigate to this directory and rebuild/reinstall the extension using the steps from the Installation section.

