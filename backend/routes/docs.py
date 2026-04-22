from fastapi import APIRouter, status

from backend.schemas import (
    DocContentResponse,
    DocsListResponse,
    DocsSearchResponse,
    RelatedDocsResponse,
)
from backend.services.docs_service import (
    list_doc_modules,
    list_global_docs,
    safe_doc_path,
    search_docs,
)
from backend.services.graph_service import related_docs as find_related_docs

router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.get("", response_model=DocsListResponse, status_code=status.HTTP_200_OK)
async def list_docs() -> DocsListResponse:
    global_docs = list_global_docs()
    modules = list_doc_modules()
    return DocsListResponse(documents=[*global_docs, *modules], modules=modules)


@router.get(
    "/search",
    response_model=DocsSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_docs_route(q: str) -> DocsSearchResponse:
    return DocsSearchResponse(query=q, results=search_docs(q))


@router.get(
    "/related/{module_name}",
    response_model=RelatedDocsResponse,
    status_code=status.HTTP_200_OK,
)
async def related_docs_route(module_name: str) -> RelatedDocsResponse:
    related = find_related_docs(module_name)
    return RelatedDocsResponse(module_name=module_name, related=related)


@router.get(
    "/{module_name}",
    response_model=DocContentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_doc(module_name: str) -> DocContentResponse:
    module_path = safe_doc_path(module_name)
    content = module_path.read_text(encoding="utf-8")
    return DocContentResponse(content=content)
