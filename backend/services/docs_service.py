from __future__ import annotations

import re

from backend.config import DOCS_OUTPUT_DIR, INDEX_PATH, MODULES_DIR, README_PATH
from backend.schemas import DocModule, DocsSearchResult


def list_doc_modules() -> list[DocModule]:
    source_by_doc = extract_source_paths_by_doc_name()
    modules: list[DocModule] = []
    for path in sorted(
        MODULES_DIR.glob("*.md"), key=lambda file_path: file_path.name.lower()
    ):
        modules.append(
            DocModule(
                name=path.name,
                path=str(path.relative_to(DOCS_OUTPUT_DIR)),
                source_path=source_by_doc.get(path.name),
            )
        )
    return modules


def list_global_docs() -> list[DocModule]:
    docs: list[DocModule] = []
    for path in [README_PATH, INDEX_PATH]:
        if path.exists() and path.is_file():
            docs.append(
                DocModule(
                    name=path.name,
                    path=str(path.relative_to(DOCS_OUTPUT_DIR)),
                    kind="global",
                )
            )
    return docs


def normalize_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").lower()


def extract_doc_links_from_index() -> dict[str, str]:
    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = normalize_path(match.group(1))
        doc_name = match.group(2)
        mapping[source_path] = doc_name
    return mapping


def extract_source_paths_by_doc_name() -> dict[str, str]:
    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = match.group(1).replace("\\", "/")
        doc_name = match.group(2)
        mapping[doc_name] = source_path
    return mapping


def safe_doc_path(doc_name: str):
    normalized_name = doc_name
    if not normalized_name.endswith(".md"):
        normalized_name = f"{normalized_name}.md"

    if normalized_name in {README_PATH.name, INDEX_PATH.name}:
        target = DOCS_OUTPUT_DIR / normalized_name
    else:
        target = MODULES_DIR / normalized_name

    return target


def build_snippet(content: str, query: str, window: int = 120) -> str:
    lowered = content.lower()
    index = lowered.find(query.lower())
    if index < 0:
        snippet = content[: window * 2]
    else:
        start = max(index - window, 0)
        end = min(index + len(query) + window, len(content))
        snippet = content[start:end]
    return " ".join(snippet.split())


def search_docs(query: str) -> list[DocsSearchResult]:
    query = query.strip()
    if not query:
        return []

    results: list[DocsSearchResult] = []
    source_by_doc = extract_source_paths_by_doc_name()
    for doc in [*list_global_docs(), *list_doc_modules()]:
        path = safe_doc_path(doc.name)
        content = path.read_text(encoding="utf-8")
        if query.lower() in content.lower() or query.lower() in doc.name.lower():
            results.append(
                DocsSearchResult(
                    name=doc.name,
                    path=doc.path,
                    kind=doc.kind,
                    snippet=build_snippet(content, query),
                    source_path=source_by_doc.get(doc.name),
                )
            )
    return results
