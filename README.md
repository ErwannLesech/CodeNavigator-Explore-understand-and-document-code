# CodeNavigator

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Mistral](https://img.shields.io/badge/LLM-Mistral-black)](https://mistral.ai/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-E74C3C?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![NetworkX](https://img.shields.io/badge/Graph-NetworkX-0C6EFD)](https://networkx.org/)
[![Tree-sitter](https://img.shields.io/badge/Parser-Tree--sitter-3C873A)](https://tree-sitter.github.io/tree-sitter/)
[![SQLGlot](https://img.shields.io/badge/SQL-SQLGlot-4B5563)](https://github.com/tobymao/sqlglot)

CodeNavigator est un outil d'exploration de code qui automatise:

- l'ingestion d'un depot (Python, SQL, JS, TS),
- le parsing structurel (fonctions, classes, schemas SQL, dependances),
- la generation de documentation Markdown assistee par IA,
- la construction d'un graphe de connaissances,
- un chatbot RAG pour interroger la codebase en langage naturel.

## Fonctionnalites

- Ingestion de depot local ou distant (via clone Git).
- Parsing specialise Python et SQL + fallback Tree-sitter.
- Chunking et indexation vectorielle pour la recherche semantique.
- Generation de docs projet/modules/fichiers au format Markdown.
- Export de graphes en JSON.
- Chat RAG en CLI et endpoint FastAPI reutilisable.

## Structure du projet

```text
CodeNavigator/
|- backend/
|  `- chat.py
|- src/
|  `- codeNavigator/
|     |- embedding/
|     |  |- chunker.py
|     |  |- embedder.py
|     |  |- indexer.py
|     |  `- vector_store.py
|     |- generation/
|     |  |- assembler.py
|     |  |- doc_generator.py
|     |  |- exporter.py
|     |  `- prompts.py
|     |- graph/
|     |  |- builder.py
|     |  |- json_exporter.py
|     |  `- models.py
|     |- ingestion/
|     |  |- parser_dispatcher.py
|     |  |- python_parser.py
|     |  |- repo_walker.py
|     |  |- sql_parser.py
|     |  `- treesitter_parser.py
|     `- rag/
|        |- chatbot.py
|        |- cli.py
|        |- graph_context.py
|        `- retriever.py
|- frontend/
|- tests/
|  `- ingestion/
|- data/
|  |- input/
|  `- output/
|- main.py
`- requirements.txt
```

## Prerequis

- Python 3.11+
- pip
- Cle API Mistral (obligatoire pour generation et chat)
- Qdrant (obligatoire pour indexation vectorielle et RAG)

Option recommande (Docker Compose) pour lancer Qdrant + backend + frontend:

```bash
docker-compose up --build
```

Services exposes:

- Frontend: http://localhost:5173
- Backend: http://localhost:8001
- Qdrant: http://localhost:6333

## Installation

1. Cloner le depot

```bash
git clone <url-du-repo>
cd CodeNavigator-Explore-understand-and-document-code
```

2. Creer et activer un environnement virtuel

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

3. Installer les dependances

```bash
pip install -r requirements.txt
```

4. Installer Qdrant client (necessaire a l'indexation)

```bash
pip install qdrant-client==1.9.1
```

## Configuration

Creer un fichier .env a la racine:

```env
MISTRAL_API_KEY=your_mistral_api_key
GRAPH_JSON_PATH=data/output/graph/graph.json
```

## Utilisation CLI

La CLI principale est dans main.py.

### 1) Indexer une codebase

```bash
python main.py index --repo <path_ou_git_url>
```

Mode validation sans appels embeddings:

```bash
python main.py index --repo <path_ou_git_url> --dry-run
```

### 2) Generer la documentation Markdown

```bash
python main.py generate --repo <path_ou_git_url> --output data/output/docs
```

### 3) Generer le knowledge graph

```bash
python main.py graph --repo <path_ou_git_url> --output data/output/graph
```

### 4) Lancer le pipeline complet

```bash
python main.py full --repo <path_ou_git_url> --output data/output/docs
```

### 5) Lancer le chatbot RAG en CLI

```bash
python main.py chat --graph data/output/graph/graph.json
```

Commandes utiles dans le chat:

- /sources : activer/desactiver l'affichage des sources
- /reset : vider l'historique
- /quit : quitter

## Exemples rapides

Utiliser le repo d'exemple fourni:

```bash
python main.py graph --repo data/input/sample_repo --output data/output/graph
python main.py generate --repo data/input/sample_repo --output data/output/docs
python main.py chat --graph data/output/graph/graph.json
```

## Endpoint API Chat (FastAPI)

Le routeur est defini dans backend/chat.py (prefixe /api/chat).

Exemple d'integration:

```python
from fastapi import FastAPI
from backend.chat import router as chat_router

app = FastAPI(title="CodeNavigator API")
app.include_router(chat_router)
```

Endpoints exposes:

- POST /api/chat
- DELETE /api/chat/reset

## Tests

Executer la suite de tests:

```bash
pytest -q
```