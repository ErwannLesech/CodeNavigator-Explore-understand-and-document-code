from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.chat import router as chat_router


DOCS_OUTPUT_DIR = Path(os.getenv("DOCS_OUTPUT_DIR", "data/output/docs"))
MODULES_DIR = DOCS_OUTPUT_DIR / "modules"
GRAPH_JSON_PATH = Path(os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json"))
DIAGRAMS_DIR = Path(os.getenv("DIAGRAMS_DIR", "data/output/graph"))
README_PATH = DOCS_OUTPUT_DIR / "README.md"
INDEX_PATH = DOCS_OUTPUT_DIR / "INDEX.md"


class HealthResponse(BaseModel):
    status: str


class DocModule(BaseModel):
    name: str
    path: str
    kind: str = "module"
    source_path: str | None = None


class DocsListResponse(BaseModel):
    documents: list[DocModule]
    modules: list[DocModule]


class DocContentResponse(BaseModel):
    content: str


class DocsSearchResult(BaseModel):
    name: str
    path: str
    kind: str
    snippet: str
    source_path: str | None = None


class DocsSearchResponse(BaseModel):
    query: str
    results: list[DocsSearchResult]


class RelatedDocsResponse(BaseModel):
    module_name: str
    related: list[DocModule]


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class DiagramItem(BaseModel):
    name: str
    path: str


class DiagramsResponse(BaseModel):
    diagrams: list[DiagramItem]


class DiagramContentResponse(BaseModel):
    name: str
    content: str


def _list_doc_modules() -> list[DocModule]:
    if not MODULES_DIR.exists() or not MODULES_DIR.is_dir():
        return []

    source_by_doc = _extract_source_paths_by_doc_name()
    modules: list[DocModule] = []
    for path in sorted(MODULES_DIR.glob("*.md"), key=lambda p: p.name.lower()):
        modules.append(
            DocModule(
                name=path.name,
                path=str(path.relative_to(DOCS_OUTPUT_DIR)),
                source_path=source_by_doc.get(path.name),
            )
        )
    return modules


def _list_global_docs() -> list[DocModule]:
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


def _normalize_path(raw_path: str) -> str:
    return raw_path.replace("\\", "/").lower()


def _extract_doc_links_from_index() -> dict[str, str]:
    if not INDEX_PATH.exists() or not INDEX_PATH.is_file():
        return {}

    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = _normalize_path(match.group(1))
        doc_name = match.group(2)
        mapping[source_path] = doc_name
    return mapping


def _extract_source_paths_by_doc_name() -> dict[str, str]:
    if not INDEX_PATH.exists() or not INDEX_PATH.is_file():
        return {}

    mapping: dict[str, str] = {}
    content = INDEX_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*`([^`]+)`\s*\|\s*\[doc\]\(modules/([^\)]+)\)")
    for match in pattern.finditer(content):
        source_path = match.group(1).replace("\\", "/")
        doc_name = match.group(2)
        mapping[doc_name] = source_path
    return mapping


def _safe_module_path(module_name: str) -> Path:
    normalized_name = Path(module_name).name
    if normalized_name != module_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid module name.",
        )

    if not normalized_name.endswith(".md"):
        normalized_name = f"{normalized_name}.md"

    module_path = MODULES_DIR / normalized_name
    if not module_path.exists() or not module_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documentation module not found.",
        )

    return module_path


def _safe_doc_path(doc_name: str) -> Path:
    normalized_name = Path(doc_name).name
    if normalized_name != doc_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document name.",
        )

    if not normalized_name.endswith(".md"):
        normalized_name = f"{normalized_name}.md"

    if normalized_name in {README_PATH.name, INDEX_PATH.name}:
        target = DOCS_OUTPUT_DIR / normalized_name
    else:
        target = MODULES_DIR / normalized_name

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documentation file not found.",
        )

    return target


def _build_snippet(content: str, query: str, window: int = 120) -> str:
    lowered = content.lower()
    index = lowered.find(query.lower())
    if index < 0:
        snippet = content[: window * 2]
    else:
        start = max(index - window, 0)
        end = min(index + len(query) + window, len(content))
        snippet = content[start:end]
    return " ".join(snippet.split())


def _search_docs(query: str) -> list[DocsSearchResult]:
    query = query.strip()
    if not query:
        return []

    results: list[DocsSearchResult] = []
    source_by_doc = _extract_source_paths_by_doc_name()
    for doc in [*_list_global_docs(), *_list_doc_modules()]:
        path = _safe_doc_path(doc.name)
        content = path.read_text(encoding="utf-8")
        if query.lower() in content.lower() or query.lower() in doc.name.lower():
            results.append(
                DocsSearchResult(
                    name=doc.name,
                    path=doc.path,
                    kind=doc.kind,
                    snippet=_build_snippet(content, query),
                    source_path=source_by_doc.get(doc.name),
                )
            )
    return results


def _read_graph() -> GraphResponse:
    if not GRAPH_JSON_PATH.exists() or not GRAPH_JSON_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Graph file not found.",
        )

    try:
        payload = json.loads(GRAPH_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Graph file is invalid JSON.",
        ) from exc

    nodes = payload.get("nodes", [])
    edges = payload.get("edges", payload.get("links", []))

    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Graph payload format is invalid.",
        )

    return GraphResponse(nodes=nodes, edges=edges)


def _list_diagrams() -> list[DiagramItem]:
    if not DIAGRAMS_DIR.exists() or not DIAGRAMS_DIR.is_dir():
        return []

    diagrams: list[DiagramItem] = []
    for path in sorted(DIAGRAMS_DIR.glob("*.mermaid"), key=lambda p: p.name.lower()):
        diagrams.append(
            DiagramItem(name=path.name, path=str(path.relative_to(DIAGRAMS_DIR.parent)))
        )
    return diagrams


def _safe_diagram_path(diagram_name: str) -> Path:
    normalized_name = Path(diagram_name).name
    if normalized_name != diagram_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid diagram name.",
        )

    if not normalized_name.endswith(".mermaid"):
        normalized_name = f"{normalized_name}.mermaid"

    path = DIAGRAMS_DIR / normalized_name
    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagram not found.",
        )
    return path


def _related_docs(module_name: str) -> list[DocModule]:
    graph = _read_graph()
    mapping = _extract_doc_links_from_index()
    reverse_mapping = {doc_name: src for src, doc_name in mapping.items()}

    if module_name not in reverse_mapping:
        return []

    raw_source = reverse_mapping[module_name]
    module_node = next(
        (
            node
            for node in graph.nodes
            if node.get("type") == "module"
            and _normalize_path(str(node.get("label", ""))) == raw_source
        ),
        None,
    )
    if not module_node:
        return []

    module_id = str(module_node.get("id", ""))
    neighbor_module_labels: set[str] = set()
    for edge in graph.edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source == module_id or target == module_id:
            other_id = target if source == module_id else source
            other_node = next(
                (node for node in graph.nodes if str(node.get("id", "")) == other_id),
                None,
            )
            if other_node and other_node.get("type") == "module":
                neighbor_module_labels.add(_normalize_path(str(other_node.get("label", ""))))

    related: list[DocModule] = []
    for raw in sorted(neighbor_module_labels):
        doc_name = mapping.get(raw)
        if doc_name:
            related.append(
                DocModule(
                    name=doc_name,
                    path=f"modules/{doc_name}",
                    kind="module",
                    source_path=raw,
                )
            )
    return related


def create_app() -> FastAPI:
    app = FastAPI(title="CodeNavigator API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)

    @app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/api/docs", response_model=DocsListResponse, status_code=status.HTTP_200_OK)
    async def list_docs() -> DocsListResponse:
        globals_docs = _list_global_docs()
        modules = _list_doc_modules()
        return DocsListResponse(documents=[*globals_docs, *modules], modules=modules)

    @app.get(
        "/api/docs/search",
        response_model=DocsSearchResponse,
        status_code=status.HTTP_200_OK,
    )
    async def search_docs(q: str) -> DocsSearchResponse:
        return DocsSearchResponse(query=q, results=_search_docs(q))

    @app.get(
        "/api/docs/related/{module_name}",
        response_model=RelatedDocsResponse,
        status_code=status.HTTP_200_OK,
    )
    async def related_docs(module_name: str) -> RelatedDocsResponse:
        return RelatedDocsResponse(
            module_name=module_name,
            related=_related_docs(module_name),
        )

    @app.get(
        "/api/docs/{module_name}",
        response_model=DocContentResponse,
        status_code=status.HTTP_200_OK,
    )
    async def get_doc(module_name: str) -> DocContentResponse:
        module_path = _safe_doc_path(module_name)
        content = module_path.read_text(encoding="utf-8")
        return DocContentResponse(content=content)

    @app.get("/api/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
    async def get_graph() -> GraphResponse:
        return _read_graph()

    @app.get("/api/diagrams", response_model=DiagramsResponse, status_code=status.HTTP_200_OK)
    async def get_diagrams() -> DiagramsResponse:
        return DiagramsResponse(diagrams=_list_diagrams())

    @app.get(
        "/api/diagrams/{diagram_name}",
        response_model=DiagramContentResponse,
        status_code=status.HTTP_200_OK,
    )
    async def get_diagram(diagram_name: str) -> DiagramContentResponse:
        path = _safe_diagram_path(diagram_name)
        content = path.read_text(encoding="utf-8")
        return DiagramContentResponse(name=path.name, content=content)

    return app


app = create_app()
