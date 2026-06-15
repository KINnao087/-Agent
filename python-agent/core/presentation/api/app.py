from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.contracts import router as contract_router
from .routes.reviews import router as reviews_router


def create_app() -> FastAPI:
    """创建 FastAPI 应用。"""
    app = FastAPI(title="Contract Review API", version="0.2.0")
    # CORS: 允许 Java 后端和 Vue 前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(contract_router)
    app.include_router(reviews_router)
    return app


app = create_app()
