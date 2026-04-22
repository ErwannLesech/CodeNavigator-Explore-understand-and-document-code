from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.chat import router as chat_router
from backend.routes import (
    docs_router,
    graph_router,
    health_router,
    pipeline_router,
    qdrant_router,
)


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
    app.include_router(health_router)
    app.include_router(docs_router)
    app.include_router(graph_router)
    app.include_router(pipeline_router)
    app.include_router(qdrant_router)

    return app


app = create_app()
