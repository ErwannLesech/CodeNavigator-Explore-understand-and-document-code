from embedding.chunker import Chunk


SYSTEM_PROMPT = """You are a senior software engineer writing technical documentation.
Your task is to generate clear, accurate, and concise documentation based on code analysis.
Rules:
- Never invent behavior that is not explicitly visible in the provided code
- If something is unclear, say so explicitly rather than guessing
- Write in the same language as the instructions you receive
- Output only the documentation, no preamble or commentary
- Use Markdown formatting
"""


def prompt_for_function(chunk: Chunk) -> str:
    return f"""Generate documentation for this Python function.

## Code analysis
{chunk.content}

## Output format (strict)
### `{chunk.metadata.get("name", "unknown")}()`
**Description**: [one sentence, what it does]

**Arguments**:
| Name | Description |
|------|-------------|
[one row per argument, or "No arguments" if empty]

**Returns**: [what it returns, or "None"]

**Notes**: [edge cases, important behaviors, or "None"]
"""


def prompt_for_class(chunk: Chunk, method_docs: list[str] = None) -> str:
    methods_context = ""
    if method_docs:
        methods_context = "\n## Already documented methods\n" + "\n---\n".join(
            method_docs[:5]
        )

    return f"""Generate documentation for this Python class.

## Code analysis
{chunk.content}
{methods_context}

## Output format (strict)
### Class `{chunk.metadata.get("name", "unknown")}`
**Description**: [what this class represents or does]

**Inherits from**: {", ".join(chunk.metadata.get("bases", [])) or "nothing"}

**Responsibilities**:
- [bullet point per main responsibility, max 4]

**Methods summary**:
| Method | Description |
|--------|-------------|
[one row per public method]
"""


def prompt_for_table(chunk: Chunk) -> str:
    return f"""Generate documentation for this SQL table.

## Schema analysis
{chunk.content}

## Output format (strict)
### Table `{chunk.metadata.get("table_name", "unknown")}`
**Description**: [what this table stores, inferred from column names]

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
[one row per column]

**Relationships**:
[foreign keys as bullet points, or "No foreign keys"]

**Usage notes**: [inferred usage patterns, or "None"]
"""


def prompt_for_module(
    file_path: str, function_docs: list[str], class_docs: list[str], imports: list[str]
) -> str:
    all_docs = "\n---\n".join(function_docs + class_docs)
    imports_str = "\n".join(imports[:15]) if imports else "None"

    return f"""Generate a module-level documentation page.

## Module: {file_path}
## Imports (top 15)
{imports_str}

## Documented components
{all_docs}

## Output format (strict)
## Module `{file_path}`
**Purpose**: [one paragraph, what this module does and why it exists]

**Key components**:
| Name | Type | Role |
|------|------|------|
[one row per function or class]

**Dependencies**: [main external imports and why they are used]

**Entry points**: [functions meant to be called directly, or "None"]
"""


def prompt_for_project(modules_summary: list[dict]) -> str:
    modules_text = "\n\n".join(
        f"### {m['file']}\n{m['summary']}" for m in modules_summary
    )

    return f"""Generate a project-level README documentation.

## Modules analyzed
{modules_text}

## Output format (strict)
# Project Overview

## Purpose
[2-3 sentences: what this project does, who uses it, what problem it solves]

## Architecture
[paragraph describing how modules relate to each other]

## Module index
| Module | Role |
|--------|------|
[one row per module]

## Data flow
[paragraph or bullet points describing how data moves through the project]

## Getting started
[inferred setup steps based on imports and structure, clearly marked as inferred]
"""


RAG_SYSTEM_PROMPT = """You are CodeNavigator, an AI assistant specialized in explaining codebases.
You answer questions about the code based exclusively on the provided context.

Rules:
- Base your answer strictly on the provided context, never invent
- If the context does not contain enough information, say so explicitly
- Always cite your sources using [Source N] references
- Be concise and technical
- Answer in the same language as the question
"""


def prompt_rag(query: str, context: str, graph_context: str = "") -> str:
    graph_section = ""
    if graph_context:
        graph_section = f"\n## Dependency context (knowledge graph)\n{graph_context}\n"

    return f"""## Retrieved context
{context}
{graph_section}
## Question
{query}

Answer based solely on the context above. Cite sources with [Source N]."""
