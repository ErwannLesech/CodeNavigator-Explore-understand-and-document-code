from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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


class PipelineRunRequest(BaseModel):
    repo: str
    output_docs: str = "data/output/docs"
    output_graph: str = "data/output/graph"
    recreate: bool = False
    dialect: str = "mysql"
    dry_run: bool = False


class PipelineStartResponse(BaseModel):
    job_id: str
    status: str


class PipelineEvent(BaseModel):
    timestamp: str
    stage: str
    message: str
    progress: float
    details: dict[str, Any] | None = None


class PipelineStatusResponse(BaseModel):
    job_id: str | None
    status: str
    started_at: str | None
    finished_at: str | None
    progress: float
    current_stage: str
    error: str | None
    request: dict[str, Any] | None
    stats: dict[str, Any]
    outputs: dict[str, str]
    events: list[PipelineEvent]


class QdrantInfoResponse(BaseModel):
    host: str
    port: int
    url: str
    reachable: bool
    active_collection: str
    collections: list[str]


class QdrantOpenResponse(BaseModel):
    status: str
    url: str
