from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import List
import io
import csv

from ..services.backtest_service import run_backtest

router = APIRouter(prefix="/api/v1", tags=["backtest"])

@router.get("/backtest")
def backtest(
    tickers: List[str] = Query(...),
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str   = Query(..., description="YYYY-MM-DD"),
    sell_th: int = 40,
    buy_th: int = 70,
    format: str = "json",
):
    result = run_backtest(tickers, start, end, sell_th, buy_th)
    if format.lower() != "csv":
        return result

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ticker","wi_start","signal_start","start_date","end_date","start_close","end_close","perf_pct"])
    for r in result.get("data", []):
        if "error" in r:
            writer.writerow([r.get("ticker"), "", "", "", "", "", "", f"ERROR: {r['error']}"])
        else:
            writer.writerow([
                r.get("ticker",""),
                r.get("wi_start",""),
                r.get("signal_start",""),
                r.get("start_date",""),
                r.get("end_date",""),
                r.get("start_close",""),
                r.get("end_close",""),
                r.get("perf_pct","")
            ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="backtest_{start}_{end}.csv"'}
    )
