from fastapi import APIRouter, Query
from typing import List
from app.services.wi_service import compute_wi_for_tickers, backtest_rank_then_forward_return

router = APIRouter()

@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

@router.get("/wi", tags=["wi"])
def get_wi(tickers: List[str] = Query(..., description="tickers=NVDA&tickers=AAPL")):
    return {"data": compute_wi_for_tickers(tickers)}

@router.get("/wi/backtest", tags=["wi"])
def get_wi_backtest(tickers: List[str] = Query(...), rank_date: str = Query(...), to: str = Query(...)):
    return backtest_rank_then_forward_return(tickers, rank_date, to)
