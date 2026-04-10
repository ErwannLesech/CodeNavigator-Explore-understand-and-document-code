from src.codeNavigator.embedding.chunker import Chunk


SYSTEM_PROMPT = """Tu es un ingenieur logiciel senior charge de rediger de la documentation technique.
Ta mission est de produire une documentation claire, exacte, concise et utile dans le contexte du projet.
Regles:
- N'invente jamais un comportement non visible explicitement dans le code fourni
- Si une information est incertaine, indique-le clairement au lieu de supposer
- Reste factuel, concret, sans style marketing ni ton pompeux
- Garde le meme niveau de details sur tous les elements documentes
- Retourne uniquement la documentation en Markdown, sans preambule
"""


def prompt_for_function(chunk: Chunk) -> str:
    return f"""Genere la documentation de cette fonction Python.

## Analyse du code
{chunk.content}

## Format de sortie (strict)
### `{chunk.metadata.get("name", "unknown")}()`
**Contexte projet**: [ou cette fonction s'insere dans le module et pourquoi elle existe]

**Description**: [1 phrase, role principal]

**Entrees**:
| Nom | Type (si visible) | Description |
|-----|-------------------|-------------|
[1 ligne par argument, ou "Aucune" si vide]

**Sortie**: [valeur retournee, ou "None"]

**Dependances**: [appels/fonctions/modules relies, ou "Aucune"]

**Points d'attention**: [cas limites, effets de bord, preconditions, ou "Aucun"]
"""


def prompt_for_class(chunk: Chunk, method_docs: list[str] | None = None) -> str:
    methods_context = ""
    if method_docs:
        methods_context = "\n## Methodes deja documentees\n" + "\n---\n".join(
            method_docs[:5]
        )

    return f"""Genere la documentation de cette classe Python.

## Analyse du code
{chunk.content}
{methods_context}

## Format de sortie (strict)
### Class `{chunk.metadata.get("name", "unknown")}`
**Contexte projet**: [role de la classe dans le module/projet]

**Description**: [ce que represente la classe et son objectif]

**Herite de**: {", ".join(chunk.metadata.get("bases", [])) or "rien"}

**Entrees principales**: [parametres d'initialisation visibles, ou "Aucune"]

**Sortie/etat**: [etat porte par la classe ou objets produits, ou "Non applicable"]

**Dependances**: [classes/modules relies, ou "Aucune"]

**Points d'attention**:
- [maximum 4 points: invariants, limites, comportements notables]

**Resume des methodes**:
| Methode | Role |
|---------|------|
[1 ligne par methode publique]
"""


def prompt_for_table(chunk: Chunk) -> str:
    return f"""Genere la documentation de cette table SQL.

## Analyse du schema
{chunk.content}

## Format de sortie (strict)
### Table `{chunk.metadata.get("table_name", "unknown")}`
**Contexte projet**: [position de cette table dans le pipeline de donnees]

**Description**: [ce que la table stocke, infere depuis le schema]

**Entrees/structure**:
| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
[1 ligne par colonne]

**Sortie/usage**: [comment la table est exploitee en lecture (jointures, agrg, reporting), ou "Non precise"]

**Dependances**: [cles etrangeres, tables amont/aval, ou "Aucune"]

**Points d'attention**: [qualite de donnees, cardinalite, champs sensibles, ou "Aucun"]
"""


def prompt_for_module(
    file_path: str, function_docs: list[str], class_docs: list[str], imports: list[str]
) -> str:
    all_docs = "\n---\n".join(function_docs + class_docs)
    imports_str = "\n".join(imports[:15]) if imports else "Aucun"

    return f"""Genere une documentation de niveau module.

## Module: {file_path}
## Imports (top 15)
{imports_str}

## Composants documentes
{all_docs}

## Format de sortie (strict)
## Module `{file_path}`
**Contexte projet**: [place du module dans l'architecture globale]

**Description**: [1 paragraphe court: ce que fait le module et pourquoi il existe]

**Entrees**: [entrees principales exposees (fonctions/classes/API), ou "Aucune"]

**Sorties**: [objets, effets ou donnees produites, ou "Aucune"]

**Composants cles**:
| Nom | Type | Role |
|-----|------|------|
[1 ligne par fonction ou classe]

**Dependances**: [imports externes principaux et leur utilite]

**Points d'attention**: [limites, couplages forts, hypothese notable, ou "Aucun"]
"""


def prompt_for_project(modules_summary: list[dict]) -> str:
    modules_text = "\n\n".join(
        f"### {m['file']}\n{m['summary']}" for m in modules_summary
    )

    return f"""Genere une documentation README de niveau projet.

## Modules analyses
{modules_text}

## Format de sortie (strict)
# Vue d'ensemble du projet

## Contexte projet
[2-3 phrases: objectif global, cible utilisateur, probleme adresse]

## Description
[resume clair du fonctionnement global, sans detail inutile]

## Entrees
[sources d'entree principales: texte, fichiers, API, ou "Non precise"]

## Sorties
[artefacts produits: docs, graphes, index, API, etc.]

## Dependances
[dependances techniques majeures et leur role]

## Index des modules
| Module | Role |
|--------|------|
[1 ligne par module]

## Points d'attention
[limites connues, zones a forte complexite, ou "Aucun"]
"""


RAG_SYSTEM_PROMPT = """Tu es CodeNavigator, un assistant IA specialise dans l'explication de codebases.
Tu reponds aux questions uniquement a partir du contexte fourni.

Regles:
- Base ta reponse strictement sur le contexte recupere, sans invention
- Si le contexte est insuffisant, indique-le explicitement
- Cite toujours tes sources avec le format [Source N]
- Reste technique, clair et concis
- Reponds dans la meme langue que la question
"""


def prompt_rag(query: str, context: str, graph_context: str = "") -> str:
    graph_section = ""
    if graph_context:
        graph_section = f"\n## Contexte de dependances (graphe de connaissances)\n{graph_context}\n"

    return f"""## Contexte recupere
{context}
{graph_section}
## Question
{query}

Reponds uniquement avec le contexte ci-dessus. Cite les sources avec [Source N]."""

