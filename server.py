from fastapi import FastAPI
from core.api.routes.contracts import router as contract_router

app = FastAPI(title="Contracts API", version="0.1.0")
app.include_router(contract_router)

