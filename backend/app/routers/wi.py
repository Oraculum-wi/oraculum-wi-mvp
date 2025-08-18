from fastapi import APIRouter, Query
from typing import List
from app.services.wi_service import compute_wi_for_tickers

router = APIRouter(prefix="/api/v1", tags=["wi"])

@router.get("/wi")
def wi(tickers: List[str] = Query(...)):
    data = compute_wi_for_tickers(tickers)
    return {"data": data}
