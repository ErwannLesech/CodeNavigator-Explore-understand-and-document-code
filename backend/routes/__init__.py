from backend.routes.docs import router as docs_router
from backend.routes.graph import router as graph_router
from backend.routes.health import router as health_router
from backend.routes.models import router as models_router
from backend.routes.pipeline import router as pipeline_router
from backend.routes.qdrant import router as qdrant_router

__all__ = [
    "docs_router",
    "graph_router",
    "health_router",
    "models_router",
    "pipeline_router",
    "qdrant_router",
]
