import os, json, pathlib

root = pathlib.Path(".").resolve()
backend = root / "backend"
frontend = root / "frontend"

# --- cartelle ---
for d in [
    backend / "app" / "api" / "v1",
    backend / "app" / "core",
    backend / "app" / "indicators",
    backend / "app" / "data_sources",
    backend / "app" / "services",
    backend / "tests",
    frontend / "src" / "components",
]:
    d.mkdir(parents=True, exist_ok=True)

# --- .gitignore ---
(root / ".gitignore").write_text("""\
# Python
__pycache__/
*.pyc
.venv/
.env

# Node
node_modules/
dist/
""")

# --- backend files ---
(backend / "requirements.txt").write_text("""\
fastapi==0.115.0
uvicorn==0.30.3
pydantic==2.8.2
python-dotenv==1.0.1
pandas==2.2.2
numpy==1.26.4
yfinance==0.2.40
SQLAlchemy==2.0.32
APScheduler==3.10.4
""")

(backend / ".env.example").write_text("""\
APP_NAME=Oraculum
APP_ENV=dev
API_V1_STR=/api/v1
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
""")

(backend / "app" / "core" / "config.py").write_text("""\
from pydantic import BaseModel
import os

class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "Oraculum")
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
settings = Settings()
""")

(backend / "app" / "indicators" / "wysocki.py").write_text("""\
import numpy as np
import pandas as pd

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / (down.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def _z(x: pd.Series) -> pd.Series:
    m, s = x.mean(), x.std(ddof=0)
    if s == 0 or np.isnan(s):
        return pd.Series(np.zeros(len(x)), index=x.index)
    return (x - m) / s

def compute_wysocki_indicator(df: pd.DataFrame, events_mod: float = 0.0) -> float:
    close = df['Close']; vol = df['Volume']
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    rsi14 = _rsi(close, 14)
    breakout_55 = (close / close.rolling(55).max()).fillna(0.0)
    vol_surge = (vol / vol.rolling(20).mean()).fillna(1.0)

    MOM = (
        0.35 * _z(close.pct_change(20).fillna(0)) +
        0.25 * _z(close.pct_change(60).fillna(0)) +
        0.15 * _z(breakout_55) +
        0.15 * _z(vol_surge) +
        0.10 * _z((rsi14 - 50)/50.0)
    ).iloc[-1]

    drawdown = (close / close.cummax()) - 1.0
    trend_persist = ((ma20 > ma50) & (ma50 > ma200)).astype(int).rolling(20).mean().fillna(0)
    VAL = (0.6 * _z(-drawdown) + 0.4 * _z(trend_persist)).iloc[-1]

    gap = (close.pct_change().abs() > 0.05).rolling(20).sum().fillna(0)
    vol_trend = _z(vol.rolling(20).mean().pct_change().fillna(0))
    FLOW = (0.7 * vol_trend + 0.3 * _z(gap)).iloc[-1]

    MACRO = 0.0; RISK = 0.0
    core = 0.25*VAL + 0.30*MOM + 0.20*FLOW + 0.15*MACRO + 0.10*RISK
    raw = core + 0.50*events_mod
    score = float(100.0 * (1.0 / (1.0 + np.exp(-raw))))
    return max(0.0, min(100.0, score))
""")

(backend / "app" / "data_sources" / "market.py").write_text("""\
import pandas as pd
import yfinance as yf

def fetch_prices(ticker: str, start: str = None, end: str = None) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False, interval='1d')
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise RuntimeError(f"No data for {ticker}")
    df = df[['Open','High','Low','Close','Adj Close','Volume']].copy()
    df.index = pd.to_datetime(df.index)
    return df

def load_events_modifier(ticker: str, when: str = None) -> float:
    return 0.0
""")

(backend / "app" / "services" / "wi_service.py").write_text("""\
from typing import List, Dict
import pandas as pd
from app.data_sources.market import fetch_prices, load_events_modifier
from app.indicators.wysocki import compute_wysocki_indicator

def compute_wi_for_tickers(tickers: List[str], start: str = None, end: str = None) -> List[Dict]:
    results = []
    for t in tickers:
        try:
            df = fetch_prices(t, start=start, end=end)
            ev = load_events_modifier(t)
            score = compute_wysocki_indicator(df, events_mod=ev)
            results.append({"ticker": t, "wi": round(score, 2)})
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
    return results

def backtest_rank_then_forward_return(tickers: List[str], rank_date: str, to: str) -> Dict:
    rdate = pd.to_datetime(rank_date); fwd = pd.to_datetime(to)
    rows = []
    for t in tickers:
        try:
            df = fetch_prices(t, start=(rdate - pd.Timedelta(days=400)).strftime('%Y-%m-%d'), end=to).sort_index()
            df_cut = df.loc[:rdate]
            if df_cut.empty: raise ValueError("no history up to rank date")
            wi = compute_wysocki_indicator(df_cut, events_mod=0.0)
            px_start = df.iloc[df.index.get_indexer([rdate], method='nearest')[0]]['Close']
            px_end   = df.iloc[df.index.get_indexer([fwd],   method='nearest')[0]]['Close']
            ret = (px_end - px_start) / px_start
            rows.append({"ticker": t, "wi": round(wi,2), "ret_fwd": round(float(ret),4)})
        except Exception as e:
            rows.append({"ticker": t, "error": str(e)})
    valid = [r for r in rows if 'wi' in r]; valid.sort(key=lambda x: x['wi'], reverse=True)
    return {"rank_date": rank_date, "to": to, "results": rows, "ranking": valid}
""")

(backend / "app" / "api" / "v1" / "routes.py").write_text("""\
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
""")

(backend / "app" / "main.py").write_text("""\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.routes import router as api_v1_router

app = FastAPI(title=settings.APP_NAME)
origins = [o.strip() for o in settings.BACKEND_CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"app": settings.APP_NAME, "env": settings.APP_ENV}
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
""")

# --- frontend files ---
(frontend / "package.json").write_text(json.dumps({
  "name": "oraculum-frontend",
  "private": True,
  "version": "0.0.2",
  "type": "module",
  "scripts": {"dev":"vite","build":"vite build","preview":"vite preview"},
  "dependencies":{"react":"^18.2.0","react-dom":"^18.2.0"},
  "devDependencies":{"vite":"^5.4.0","@types/react":"^18.3.3","@types/react-dom":"^18.3.0"}
}, indent=2))

(frontend / "index.html").write_text("""\
<!doctype html><html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Oraculum</title></head>
<body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>
""")

(frontend / "src" / "main.jsx").write_text("""\
import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
createRoot(document.getElementById('root')).render(<App />)
""")

(frontend / "src" / "components" / "Gauge.jsx").write_text("""\
import React from 'react'
export default function Gauge({ value=50, label='WI' }){
  const v = Math.max(0, Math.min(100, value))
  const color = v > 80 ? '#2e7d32' : v > 60 ? '#43a047' : v > 40 ? '#fb8c00' : v > 20 ? '#e53935' : '#b71c1c'
  return (
    <div style={{ border:'1px solid #ddd', borderRadius:12, padding:12, width:260 }}>
      <div style={{ fontSize:12, opacity:.7 }}>{label}</div>
      <div style={{ fontSize:48, textAlign:'center' }}>{Math.round(v)}</div>
      <div style={{ height:8, background:'#eee', borderRadius:4, overflow:'hidden' }}>
        <div style={{ width:`${v}%`, height:8, background:color }} />
      </div>
    </div>
  )
}
""")

(frontend / "src" / "App.jsx").write_text("""\
import React, { useEffect, useState } from 'react'
import Gauge from './components/Gauge.jsx'
const DEFAULTS = ['APP','NVDA','MSFT','AAPL','META','GOOGL','JPM','XOM','LMT','TSLA']
export default function App() {
  const [tickers, setTickers] = useState(DEFAULTS.join(','))
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const loadWI = () => {
    setLoading(true)
    const params = tickers.split(',').map(t => `tickers=${t.trim()}`).join('&')
    fetch(`/api/v1/wi?${params}`).then(r=>r.json()).then(d => setRows(d.data || [])).finally(()=>setLoading(false))
  }
  useEffect(() => { loadWI() }, [])
  return (
    <div style={{ padding: 20, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Oraculum – Wysocki Indicator v0.1</h1>
      <div style={{ display: 'flex', gap: 8 }}>
        <input style={{ flex:1, padding:8 }} value={tickers} onChange={e=>setTickers(e.target.value)} placeholder="APP,NVDA,MSFT..." />
        <button onClick={loadWI} disabled={loading}>{loading ? 'Carico...' : 'Calcola'}</button>
      </div>
      <div style={{ marginTop: 20, display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(260px,1fr))', gap:12 }}>
        {rows.map((r,i)=> (
          <div key={i} style={{ display:'flex', gap:12, alignItems:'center', border:'1px solid #eee', borderRadius:12, padding:12 }}>
            <Gauge value={r.wi || 0} label={r.ticker} />
            <div style={{ fontSize:12, opacity:.7 }}>
              {r.error ? <div style={{color:'red'}}>Errore: {r.error}</div> : <div>Score generato con dati di mercato correnti via yfinance.</div>}
            </div>
          </div>
        ))}
      </div>
      <p style={{ marginTop: 24, opacity:.7 }}>Nota: WI v0.1 è semplificato (MOM + proxy VAL/FLOW). Eventi/Macro saranno aggiunti come modificatori.</p>
    </div>
  )
}
""")

(frontend / "vite.config.js").write_text("""\
import { defineConfig } from 'vite'
export default defineConfig({ server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } } })
""")

# --- root README ---
(root / "README.md").write_text("""\
# Oraculum – Wysocki Indicator MVP

## Avvio rapido
### Backend
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

### Frontend
cd frontend
npm install
npm run dev

### Endpoints
GET /api/v1/health
GET /api/v1/wi?tickers=APP&tickers=NVDA
GET /api/v1/wi/backtest?tickers=APP&rank_date=2024-01-15&to=2024-06-15
""")

print("OK - Oraculum files created")
