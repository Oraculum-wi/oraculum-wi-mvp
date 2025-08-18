from typing import List, Dict
import pandas as pd
from datetime import timedelta

# ✅ IMPORT RELATIVI
from ..data_sources.market import fetch_prices
from ..indicators.wysocki import compute_wysocki_indicator


def _classify(score: float, sell_th: int, buy_th: int) -> str:
    if score >= buy_th:
        return "BUY"
    if score < sell_th:
        return "SELL"
    return "HOLD"


def _nearest_close(df: pd.DataFrame, when: pd.Timestamp) -> float:
    i = df.index.get_indexer([when], method="nearest")[0]
    return float(df.iloc[i]["Close"])


def run_backtest(
    tickers: List[str],
    start: str,
    end: str,
    sell_th: int = 40,
    buy_th: int = 70,
) -> Dict:
    """
    WI alla data start + performance fino a end, con stesso buffer storico per rolling.
    Ritorna anche i parametri usati e (nel router) aggiungiamo benchmark/CSV.
    """
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    hist_from = (start_dt - timedelta(days=260)).strftime("%Y-%m-%d")

    rows: List[Dict] = []
    for t in tickers:
        try:
            df = fetch_prices(t, start=hist_from, end=end)
            if df is None or df.empty:
                rows.append({"ticker": t, "error": "No data"})
                continue
            df = df.sort_index()

            df_start = df.loc[df.index >= start_dt]
            if df_start.empty:
                rows.append({"ticker": t, "error": "No data at start"})
                continue
            start_idx = df_start.index[0]

            df_up_to_start = df.loc[df.index <= start_idx].tail(260)
            pack = compute_wysocki_indicator(df_up_to_start, events_mod=0.0)
            wi_start = float(pack["score"]) if isinstance(pack, dict) else float(pack)
            signal_start = _classify(wi_start, sell_th, buy_th)

            close_start = _nearest_close(df, start_dt)
            df_end = df.loc[df.index <= end_dt]
            if df_end.empty:
                rows.append({"ticker": t, "error": "No data at end"})
                continue
            close_end = _nearest_close(df, end_dt)
            perf_pct = (close_end / close_start - 1.0) * 100.0

            rows.append(
                {
                    "ticker": t,
                    "wi_start": round(wi_start, 2),
                    "signal_start": signal_start,
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": end_dt.strftime("%Y-%m-%d"),
                    "start_close": round(close_start, 4),
                    "end_close": round(close_end, 4),
                    "perf_pct": round(perf_pct, 2),
                }
            )
        except Exception as e:
            rows.append({"ticker": t, "error": str(e)})

    return {
        "params": {"start": start, "end": end, "sell_th": sell_th, "buy_th": buy_th},
        "data": rows,
    }
