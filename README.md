# CodeNavigator

AI-powered codebase documentation engine: AST parsing, LLM doc generation, knowledge graph, SQL lineage and RAG chatbot. MCP-ready.

## Project Structure

```text
CodeNavigator/
|- ingestion/          # Parsing AST (tree-sitter, sqlglot)
|- embedding/          # Chunking + vectorisation + Qdrant
|- generation/         # Prompts LLM + generation doc
|- graph/              # Knowledge graph NetworkX + Mermaid exports
|- rag/                # Pipeline RAG + chatbot
|- api/                # FastAPI layer
|- tests/
|- data/
|  |- input/           # Codebase to analyze (or Git URL)
|  |- output/          # Generated docs, diagrams, indexes
|- main.py
|- requirements.txt
|- .env.example
`- README.md
```

## Phase 1 Scope

- Repository walker with extension filtering
- Python AST parser (built-in ast)
- Minimal execution entrypoint for validation

## Quick Start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Add a sample repository under data/input/sample_repo.

3. Run the ingestion validation:

   ```bash
   python main.py
   ```

## Current Ingestion Modules

- ingestion/repo_walker.py: Accepts local path or Git URL, walks recursively with extension filters, and returns structured file metadata and content.
- ingestion/python_parser.py: Parses imports, top-level functions and classes, and extracts method signatures, decorators, docstrings, and line numbers.

## Next Logical Steps

1. Add SQL parser using sqlglot.
2. Introduce tree-sitter for multi-language parsing behind a common interface.
3. Add unit tests for walker filters and parser extraction accuracy.