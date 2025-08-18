import io
import threading
import pandas as pd
import yfinance as yf
import requests
from functools import lru_cache

# -------------------------------
# In-memory cache semplice (thread-safe)
# -------------------------------
_cache_lock = threading.Lock()
_cache: dict[tuple, pd.DataFrame] = {}

def _from_cache(key: tuple):
    with _cache_lock:
        return _cache.get(key)

def _to_cache(key: tuple, df: pd.DataFrame):
    with _cache_lock:
        _cache[key] = df

# -------------------------------
# Yahoo (primaria)
# -------------------------------
def _try_yahoo(ticker: str, start: str = None, end: str = None) -> pd.DataFrame | None:
    try:
        df = yf.download(
            ticker, start=start, end=end,
            auto_adjust=False, progress=False, interval="1d",
            threads=False
        )
        if isinstance(df, pd.DataFrame) and not df.empty:
            cols = ['Open','High','Low','Close','Adj Close','Volume']
            df = df[cols].copy()
            df.index = pd.to_datetime(df.index)
            return df
    except Exception:
        pass
    return None

# -------------------------------
# Stooq (fallback)
# -------------------------------
def _try_stooq(ticker: str, start: str = None, end: str = None) -> pd.DataFrame | None:
    t = ticker.lower()
    if "." not in t:
        t = f"{t}.us"  # mapping semplice per titoli USA
    url = f"https://stooq.com/q/d/l/?s={t}&i=d"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        if not r.text or r.text.strip() == "":
            return None
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty:
            return None
        df.rename(columns=str.title, inplace=True)  # Date, Open, High, Low, Close, Volume
        df["Adj Close"] = df["Close"]
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        df = df[['Open','High','Low','Close','Adj Close','Volume']].copy()
        # filtro su start/end se passati
        if start:
            df = df.loc[df.index >= pd.to_datetime(start)]
        if end:
            df = df.loc[df.index <  pd.to_datetime(end) + pd.Timedelta(days=1)]
        return df.sort_index()
    except Exception:
        return None

# -------------------------------
# API pubblica per il resto del codice
# -------------------------------
def fetch_prices(ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
    key = (ticker.upper(), start or "", end or "")
    hit = _from_cache(key)
    if hit is not None and isinstance(hit, pd.DataFrame) and not hit.empty:
        return hit

    df = _try_yahoo(ticker, start, end)
    if df is None or df.empty:
        df = _try_stooq(ticker, start, end)
    if df is None or df.empty:
        raise RuntimeError(f"No data for {ticker} (Yahoo & Stooq failed)")

    _to_cache(key, df)
    return df

def load_events_modifier(ticker: str, when: str = None) -> float:
    # TODO: integrazione eventi reali; per ora neutro
    return 0.0
