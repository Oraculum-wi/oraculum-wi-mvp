from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import wi as wi_router
from app.routers import backtest as backtest_router

app = FastAPI(title="Oraculum ♆ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(wi_router.router)
app.include_router(backtest_router.router)

@app.get("/")
def root():
    return {"status": "ok"}
