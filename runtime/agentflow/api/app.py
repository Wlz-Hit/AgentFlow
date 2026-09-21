"""FastAPI application factory.

Startup stays here so ``agentflow.core`` never depends on FastAPI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentflow.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="AgentFlow Runtime", version="0.0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    return app
