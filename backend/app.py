from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.chat import router as chat_router


DOCS_OUTPUT_DIR = Path(os.getenv("DOCS_OUTPUT_DIR", "data/output/docs"))
MODULES_DIR = DOCS_OUTPUT_DIR / "modules"
GRAPH_JSON_PATH = Path(os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json"))


class HealthResponse(BaseModel):
    status: str


class DocModule(BaseModel):
    name: str
    path: str


class DocsListResponse(BaseModel):
    modules: list[DocModule]


class DocContentResponse(BaseModel):
    content: str


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def _list_doc_modules() -> list[DocModule]:
    if not MODULES_DIR.exists() or not MODULES_DIR.is_dir():
        return []

    modules: list[DocModule] = []
    for path in sorted(MODULES_DIR.glob("*.md"), key=lambda p: p.name.lower()):
        modules.append(DocModule(name=path.name, path=str(path.relative_to(DOCS_OUTPUT_DIR))))
    return modules


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
        return DocsListResponse(modules=_list_doc_modules())

    @app.get(
        "/api/docs/{module_name}",
        response_model=DocContentResponse,
        status_code=status.HTTP_200_OK,
    )
    async def get_doc(module_name: str) -> DocContentResponse:
        module_path = _safe_module_path(module_name)
        content = module_path.read_text(encoding="utf-8")
        return DocContentResponse(content=content)

    @app.get("/api/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
    async def get_graph() -> GraphResponse:
        return _read_graph()

    return app


app = create_app()
