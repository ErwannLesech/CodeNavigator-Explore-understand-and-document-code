# CodeNavigator

CodeNavigator est un outil d'exploration de codebase et de generation de
documentation assistee par IA (parsing multi-langages, extraction de structure,
export Markdown, contexte graphe, RAG).

Ce README decrit l'etat reel du projet au 2026-04-08.

## Etat actuel (resume)

- Ingestion: operationnelle (repo walker + parser Python + parser SQL + fallback
   tree-sitter).
- Generation de docs: code present et fonctionnel, avec appels Mistral.
- RAG chatbot: code present (CLI + route API), avec retrieval et contexte graphe.
- Embedding et graph build/index pipeline: references dans le CLI, mais modules
   manquants dans ce workspace (dossiers `embedding/` et `graph/` incomplets).
- Tests: presents sur ingestion uniquement.
- Artefacts de sortie: documentation et graph deja generes dans `data/output/`.

## Structure actuelle du repo

```text
CodeNavigator/
|- api/
|  `- chat.py
|- generation/
|  |- assembler.py
|  |- doc_generator.py
|  |- exporter.py
|  `- prompts.py
|- ingestion/
|  |- repo_walker.py
|  |- parser_dispatcher.py
|  |- python_parser.py
|  |- sql_parser.py
|  `- treesitter_parser.py
|- rag/
|  |- chatbot.py
|  |- cli.py
|  |- graph_context.py
|  `- retriever.py
|- tests/
|  `- ingestion/
|- data/
|  |- input/
|  `- output/
|- main.py
`- requirements.txt
```

## Ce qui fonctionne deja

### 1) Ingestion

- `ingestion/repo_walker.py`
   - Parcourt un repo local ou clone un repo Git URL.
   - Filtre les extensions supportees (`.py`, `.sql`, `.js`, `.ts`).
   - Ignore les dossiers techniques (`.venv`, `node_modules`, `.git`, etc.).
- `ingestion/python_parser.py`
   - Extrait imports, fonctions top-level, classes, methodes, docstrings, lignes.
- `ingestion/sql_parser.py`
   - Parse schemas/table definitions et requetes (lineage lecture/ecriture,
      colonnes, joins) via `sqlglot`.
- `ingestion/treesitter_parser.py`
   - Extraction generique pour JS/TS/Python quand tree-sitter est disponible.
- `ingestion/parser_dispatcher.py`
   - Route automatiquement vers le parser adapte selon le langage.

### 2) Generation Markdown (LLM)

- `generation/doc_generator.py`
   - Utilise l'API Mistral (`MISTRAL_API_KEY` requise).
- `generation/assembler.py`
   - Assemble docs fonctions/classes/tables + synthese module/projet.
- `generation/exporter.py`
   - Exporte en Markdown (`README.md`, `INDEX.md`, docs par module).

### 3) RAG (chat)

- CLI: `rag/cli.py`
- Bot conversationnel: `rag/chatbot.py`
- Route FastAPI: `api/chat.py`
- Contexte graphe: `rag/graph_context.py`

## Limitations connues dans ce workspace

- `main.py` importe:
   - `embedding.indexer`
   - `graph.builder`
   - `graph.mermaid_exporter`
   - `graph.json_exporter`
- Ces modules ne sont pas presents actuellement dans les dossiers
   `embedding/` et `graph/` (qui contiennent seulement `__pycache__/`).
- Consequence: certaines commandes CLI declarees dans `main.py` ne sont pas
   executables telles quelles tant que ces modules ne sont pas restaures.

## Commandes CLI ciblees (quand tous les modules sont presents)

```bash
python main.py index --repo <path-ou-git-url>
python main.py generate --repo <path-ou-git-url>
python main.py graph --repo <path-ou-git-url>
python main.py full --repo <path-ou-git-url>
python main.py chat --graph data/output/graph/graph.json
```

## Tests

- Jeux de tests disponibles: `tests/ingestion/`
   - `test_repo_walker.py`
   - `test_python_parser.py`
   - `test_sql_parser.py`
   - `test_parser_dispatcher.py`
- Pas de tests automatises visibles pour `generation/`, `rag/` et `api/` dans
   l'etat actuel.

## Dependances principales

- Parsing: `tree-sitter`, `tree-sitter-languages`, `sqlglot`, `gitpython`
- LLM: `mistralai`
- API/config: `pydantic`, `python-dotenv`
- CLI output: `rich`
- Graph (declare): `networkx`

## Roadmap recommandee (prochaines etapes)

1. Restaurer/ajouter les modules `embedding/*` et `graph/*` manquants pour
    rendre `main.py` executable end-to-end.
2. Ajouter des tests sur `generation/`, `rag/` et `api/chat.py`.
3. Ajouter un mode de verification locale (sans appel LLM) pour valider le
    pipeline en CI.
4. Documenter un workflow de demarrage unique (env vars + commandes minimales).