from __future__ import annotations

from fastapi import FastAPI

from .routes.contracts import router as contract_router


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="Contracts API", version="0.1.0")
    app.include_router(contract_router)
    return app


app = create_app()

