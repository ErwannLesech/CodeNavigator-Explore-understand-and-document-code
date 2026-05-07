# CodeNavigator

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Mistral](https://img.shields.io/badge/LLM-Mistral-black)](https://mistral.ai/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-E74C3C?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![NetworkX](https://img.shields.io/badge/Graph-NetworkX-0C6EFD)](https://networkx.org/)
[![Tree-sitter](https://img.shields.io/badge/Parser-Tree--sitter-3C873A)](https://tree-sitter.github.io/tree-sitter/)
[![SQLGlot](https://img.shields.io/badge/SQL-SQLGlot-4B5563)](https://github.com/tobymao/sqlglot)

CodeNavigator is an open-source toolkit to explore, document and interact with codebases using structural parsing, knowledge graphs and RAG-powered chat.

Key capabilities:

- Ingest repositories (local or remote) for Python, SQL, JS, TS and more.
- Perform structural parsing (functions, classes, SQL schemas, cross-file dependencies).
- Generate Markdown documentation assisted by LLMs.
- Build and export knowledge graphs (JSON & Mermaid).
- Provide a RAG chatbot over the codebase via CLI or HTTP API.

**Table of Contents**

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [Examples](#examples)
- [API: Chat Endpoint](#api-chat-endpoint)
- [Tests](#tests)
- [Contributing](#contributing)
- [License](#license)

## Features

- Local or remote repository ingestion (Git clone supported).
- Specialized Python and SQL parsing with Tree-sitter fallback.
- Chunking and vector indexing for semantic search (Qdrant).
- Documentation generation for project/module/file levels in Markdown.
- Knowledge graph export in JSON (and visualizable via Mermaid).
- RAG-enabled chat available both in CLI and via FastAPI endpoints.

## Project Structure

```text
CodeNavigator-Explore-understand-and-document-code/
├─ backend/                # FastAPI server and route handlers
├─ frontend/               # Web client (Vite + React)
├─ src/                    # Core processing code
│  ├─ embedding/           # chunker, embedder, indexer, vector store
│  ├─ generation/          # doc generation and exporter
│  ├─ graph/               # graph builder & exporters
│  ├─ ingestion/           # parsers and repo walker
│  ├─ rag/                 # chatbot, retriever, CLI
│  └─ main.py              # CLI entrypoint
├─ data/                   # sample inputs and output artifacts
├─ tests/                  # pytest suite
└─ requirements.txt
```

## Prerequisites

- Python 3.11+
- pip
- Mistral API key (required for generation and chat)
- Qdrant (for vector index and RAG)

Docker Compose is recommended to start Qdrant, backend and frontend locally:

```bash
docker-compose up --build
```

Services (defaults):

- Frontend: http://localhost:5173
- Backend: http://localhost:8001
- Qdrant: http://localhost:6333

## Installation

1. Clone the repository

```bash
git clone <repo-url>
cd CodeNavigator-Explore-understand-and-document-code
```

2. Create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. (Optional) Install the Qdrant client

```bash
pip install qdrant-client==1.9.1
```

## Configuration

Create a `.env` file at the repository root with at least:

```env
MISTRAL_API_KEY=your_mistral_api_key
GRAPH_JSON_PATH=data/output/graph/graph.json
```

## CLI Usage

The primary CLI entrypoint is `src/main.py`.

Index a repository:

```bash
python -m src.main index --repo <path_or_git_url>
```

Dry-run (no embeddings / validation mode):

```bash
python -m src.main index --repo <path_or_git_url> --dry-run
```

Generate Markdown documentation:

```bash
python -m src.main generate --repo <path_or_git_url> --output data/output/docs
```

Export the knowledge graph:

```bash
python -m src.main graph --repo <path_or_git_url> --output data/output/graph
```

Full pipeline (index + docs + graph):

```bash
python -m src.main full --repo <path_or_git_url> --output data/output/docs
```

Start the CLI chatbot (RAG):

```bash
python -m src.main chat --graph data/output/graph/graph.json
```

Useful chat commands inside the CLI:

- `/sources` — toggle source display
- `/reset` — clear conversation history
- `/quit` — exit

## Examples

Use the provided sample repository:

```bash
python -m src.main graph --repo data/input/sample_repo --output data/output/graph
python -m src.main generate --repo data/input/sample_repo --output data/output/docs
python -m src.main chat --graph data/output/graph/graph.json
```

## API: Chat Endpoint (FastAPI)

The chat router lives in `backend/chat.py` (prefixed at `/api/chat`).

Example integration:

```python
from fastapi import FastAPI
from backend.chat import router as chat_router

app = FastAPI(title="CodeNavigator API")
app.include_router(chat_router)
```

Exposed endpoints:

- `POST /api/chat` — send a chat request
- `DELETE /api/chat/reset` — reset the chat session

## Tests

Run the test suite with:

```bash
pytest -q
```

## Contributing

Thank you for considering contributing! We welcome contributions of all kinds: bug reports, fixes, tests, documentation improvements, and new features.

Please follow these guidelines to make contributing straightforward:

1. Fork the repository and create a branch for your change: `git checkout -b feat/your-feature`.
2. Follow the project conventions: Python 3.11, type hints, Pydantic models for schemas, and `logging` (no `print`).
3. Add or update tests where appropriate and run `pytest` locally.
4. Keep commits focused and follow Conventional Commits (e.g., `feat(...)`, `fix(...)`, `chore(...)`).
5. Open a pull request describing the change, why it's needed, and any migration or runtime impacts.

If your contribution adds heavy dependencies or external services, document why they are needed and how to configure them in the README.

We review PRs quickly and are happy to help improve your changes — feel free to ask for guidance on an issue before implementation.

## License

This project is licensed under the terms in the `LICENSE` file.

---

If you'd like, I can also add a `CONTRIBUTING.md` and a PR template. Want me to add those now?
