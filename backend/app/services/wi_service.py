from typing import List, Dict
import pandas as pd

# Import RELATIVI per evitare warning in VS Code/Pylance e funzionare dentro il package "app"
from ..data_sources.market import fetch_prices, load_events_modifier
from ..indicators.wysocki import compute_wysocki_indicator


def compute_wi_for_tickers(
    tickers: List[str],
    start: str | None = None,
    end: str | None = None
) -> List[Dict]:
    """
    Calcola il WI per una lista di ticker.
    Ritorna una lista di dict con:
      { "ticker", "wi", "signal", "components" } oppure { "ticker", "error" }.
    """
    results: List[Dict] = []
    for t in tickers:
        try:
            df = fetch_prices(t, start=start, end=end)
            ev = load_events_modifier(t)
            pack = compute_wysocki_indicator(df, events_mod=ev)

            # v0.2: pack è un dict; fallback se fosse un float
            if isinstance(pack, dict):
                results.append({
                    "ticker": t,
                    "wi": pack.get("score", 0.0),
                    "signal": pack.get("signal"),
                    "components": pack.get("components"),
                })
            else:
                results.append({"ticker": t, "wi": float(pack)})
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
    return results


def backtest_rank_then_forward_return(
    tickers: List[str],
    rank_date: str,
    to: str
) -> Dict:
    """
    Per ciascun ticker:
      - calcola il WI usando lo storico fino a 'rank_date' incluso,
      - prende il Close a 'rank_date' (nearest) e a 'to' (nearest),
      - calcola il rendimento forward (ret_fwd) come frazione (es. 0.1234 = +12.34%).
    Ritorna:
      {
        "rank_date": ..., "to": ...,
        "results": [ {ticker, wi, ret_fwd} | {ticker, error} ],
        "ranking": results ordinati per wi desc (solo con 'wi')
      }
    """
    rdate = pd.to_datetime(rank_date)
    fwd   = pd.to_datetime(to)

    rows: List[Dict] = []
    for t in tickers:
        try:
            # buffer di ~400 giorni per rolling/MA
            start_hist = (rdate - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
            df = fetch_prices(t, start=start_hist, end=to).sort_index()
            if df is None or df.empty:
                raise ValueError("no data")

            # storico fino a rank_date incluso
            df_up_to_rank = df.loc[:rdate]
            if df_up_to_rank.empty:
                raise ValueError("no history up to rank date")

            pack = compute_wysocki_indicator(df_up_to_rank, events_mod=0.0)
            wi = float(pack["score"]) if isinstance(pack, dict) else float(pack)

            # prezzi start/end (nearest)
            i_start = df.index.get_indexer([rdate], method="nearest")[0]
            i_end   = df.index.get_indexer([fwd],   method="nearest")[0]
            px_start = float(df.iloc[i_start]["Close"])
            px_end   = float(df.iloc[i_end]["Close"])

            ret = (px_end / px_start) - 1.0  # frazione (es. 0.05 = +5%)
            rows.append({
                "ticker": t,
                "wi": round(wi, 2),
                "ret_fwd": round(float(ret), 4)
            })
        except Exception as e:
            rows.append({"ticker": t, "error": str(e)})

    valid = [r for r in rows if "wi" in r]
    valid.sort(key=lambda x: x["wi"], reverse=True)

    return {
        "rank_date": rank_date,
        "to": to,
        "results": rows,
        "ranking": valid
    }
