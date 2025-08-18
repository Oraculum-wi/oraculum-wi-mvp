import numpy as np
import pandas as pd
from app.data_sources.market import fetch_prices  # usa il nostro fetch con fallback


# ----------------------------
# Utilità di base
# ----------------------------
def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / (down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _z(x: pd.Series) -> pd.Series:
    """Z-score robusto (se stdev=0 o NaN -> serie di zeri)."""
    m = float(x.mean()) if len(x) else 0.0
    s = float(x.std(ddof=0)) if len(x) else 0.0
    if s == 0.0 or np.isnan(s):
        return pd.Series(np.zeros(len(x)), index=x.index)
    return (x - m) / s


def _safe_pct_change(s: pd.Series, n: int) -> pd.Series:
    try:
        return s.pct_change(n).fillna(0)
    except Exception:
        return pd.Series(np.zeros(len(s)), index=s.index)


# ----------------------------
# Fattore MACRO (robusto)
# ----------------------------
def _macro_factor(end_date: pd.Timestamp) -> float:
    """
    MACRO robusto senza ^VIX né yfinance diretto.
    Usa fetch_prices (con fallback interno) per SPY e TLT.
    La volatilità è proxy: std mobile a 20g dei rendimenti di SPY (con segno negativo).
    """
    lookback_days = 220
    start = (end_date - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end   = (end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        spy_df = fetch_prices("SPY", start=start, end=end)
        tlt_df = fetch_prices("TLT", start=start, end=end)
    except Exception:
        return 0.0  # in caso estremo, neutralizza l'impatto

    if spy_df is None or tlt_df is None or spy_df.empty or tlt_df.empty:
        return 0.0

    spy = spy_df["Close"].astype(float)
    tlt = tlt_df["Close"].astype(float)

    # trend: z-score dei rendimenti su 60g (SPY) e 30g (TLT)
    spy60 = _z(_safe_pct_change(spy, 60)).iloc[-1]
    tlt30 = _z(_safe_pct_change(tlt, 30)).iloc[-1]

    # proxy di volatilità: std mobile 20g dei rendimenti di SPY (più alta = peggio)
    vol_proxy = spy.pct_change().rolling(20).std().fillna(0.0)
    volz = _z(vol_proxy).iloc[-1]

    macro = 0.6 * spy60 + 0.3 * tlt30 + 0.1 * (-volz)
    return float(macro)


# ----------------------------
# Indicatore principale
# ----------------------------
def compute_wysocki_indicator(df: pd.DataFrame, events_mod: float = 0.0) -> dict:
    """
    Calcola il Wysocki Indicator e ritorna:
      {
        "score": 0..100,
        "signal": "BUY"|"HOLD"|"SELL",
        "components": { "MOM":..., "VAL":..., "FLOW":..., "MACRO":... }
      }
    """
    # Controlli minimi
    for col in ("Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"Manca la colonna {col}")
    if len(df) < 60:
        return {
            "score": 50.0,
            "signal": "HOLD",
            "components": {"MOM": 0.0, "VAL": 0.0, "FLOW": 0.0, "MACRO": 0.0}
        }

    close = df["Close"].astype(float)
    vol   = df["Volume"].astype(float)

    ma20  = close.rolling(20).mean()
    ma50  = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    rsi14 = _rsi(close, 14)

    breakout_55 = (close / close.rolling(55).max()).fillna(0.0)
    vol_surge   = (vol / vol.rolling(20).mean()).fillna(1.0)

    # MOMENTUM
    MOM = (
        0.35 * _z(_safe_pct_change(close, 20)).iloc[-1] +
        0.25 * _z(_safe_pct_change(close, 60)).iloc[-1] +
        0.15 * _z(breakout_55).iloc[-1] +
        0.15 * _z(vol_surge).iloc[-1] +
        0.10 * _z(((rsi14 - 50.0) / 50.0).fillna(0)).iloc[-1]
    )

    # VAL (drawdown + persistenza trend MA20>MA50>MA200)
    drawdown      = (close / close.cummax()) - 1.0
    trend_flags   = ((ma20 > ma50) & (ma50 > ma200)).fillna(False).astype(int)
    trend_persist = trend_flags.rolling(20).mean().fillna(0.0)
    VAL = 0.6 * _z(-drawdown).iloc[-1] + 0.4 * _z(trend_persist).iloc[-1]

    # FLOW (trend volumi + gap frequenti)
    gap_count = (close.pct_change().abs() > 0.05).rolling(20).sum().fillna(0.0)
    vol_trend = vol.rolling(20).mean().pct_change().fillna(0.0)
    FLOW = 0.7 * _z(vol_trend).iloc[-1] + 0.3 * _z(gap_count).iloc[-1]

    # MACRO (robusto, vedi sopra)
    MACRO = _macro_factor(close.index[-1])

    # Core score (logit → 0..100)
    core = 0.25 * VAL + 0.30 * MOM + 0.20 * FLOW + 0.15 * MACRO + 0.10 * float(events_mod)
    raw  = core
    score = float(100.0 * (1.0 / (1.0 + np.exp(-raw))))
    score = max(0.0, min(100.0, score))

    # Segnale discreto (soglie di default; lato UI usi soglie personalizzabili)
    signal = "BUY" if score >= 70 else ("SELL" if score <= 39 else "HOLD")

    return {
        "score": round(score, 2),
        "signal": signal,
        "components": {
            "MOM": round(float(MOM), 3),
            "VAL": round(float(VAL), 3),
            "FLOW": round(float(FLOW), 3),
            "MACRO": round(float(MACRO), 3),
        }
    }
