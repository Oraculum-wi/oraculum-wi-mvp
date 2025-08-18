import React, { useEffect, useState } from 'react'
import Gauge from './components/Gauge.jsx'

const DEFAULTS = ['APP','NVDA','MSFT','AAPL','META','GOOGL','JPM','XOM','LMT','TSLA']

function SignalBadge({ signal }) {
  const map = {
    BUY:   { bg:'#e8f5e9', fg:'#2e7d32', label:'BUY'  },
    HOLD:  { bg:'#fff8e1', fg:'#ef6c00', label:'HOLD' },
    SELL:  { bg:'#fdecea', fg:'#c62828', label:'SELL' },
  }
  const s = map[signal] || map.HOLD
  return <span style={{fontSize:12,padding:'2px 8px',borderRadius:999,background:s.bg,color:s.fg,fontWeight:600}}>{s.label}</span>
}

function Components({ c }) {
  if (!c) return null
  const Item = ({k,v}) => (
    <div style={{display:'flex',justifyContent:'space-between',fontSize:12}}>
      <span style={{opacity:.65}}>{k}</span>
      <span style={{fontFamily:'monospace'}}>{v}</span>
    </div>
  )
  return (
    <div style={{border:'1px solid #eee',borderRadius:8,padding:8,minWidth:140}}>
      <div style={{fontSize:11,opacity:.6,marginBottom:4}}>Componenti</div>
      <Item k="MOM" v={c.MOM}/><Item k="VAL" v={c.VAL}/><Item k="FLOW" v={c.FLOW}/><Item k="MACRO" v={c.MACRO}/>
    </div>
  )
}

function classify(score, sellTh, buyTh) {
  const v = Number(score) || 0
  if (v >= buyTh) return 'BUY'
  if (v < sellTh) return 'SELL'
  return 'HOLD'
}

export default function App() {
  const [tickers, setTickers] = useState(DEFAULTS.join(','))
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // soglie persistenti
  const readSaved = () => {
    try { const raw = localStorage.getItem('oraculumThresholds'); if (!raw) return {sell:40,buy:70}; const o=JSON.parse(raw); return {sell:o.sell??40,buy:o.buy??70} } catch { return {sell:40,buy:70} }
  }
  const [{ sell, buy }, setTh] = useState(readSaved())
  useEffect(()=>{ localStorage.setItem('oraculumThresholds', JSON.stringify({sell,buy})) },[sell,buy])

  const loadWI = () => {
    setLoading(true); setError('')
    const params = tickers.split(',').map(t=>t.trim()).filter(Boolean).map(t=>`tickers=${encodeURIComponent(t)}`).join('&')
    fetch(`/api/v1/wi?${params}`)
      .then(r=>r.ok?r.json():Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d=>setRows(d.data||[]))
      .catch(e=>setError(e.message||String(e)))
      .finally(()=>setLoading(false))
  }
  useEffect(()=>{ loadWI() },[])

  const setSell = v => setTh(t=>({ sell: Math.min(Math.max(0, Number(v)||0), (t.buy??70)-1), buy:t.buy }))
  const setBuy  = v => setTh(t=>({ sell: t.sell, buy: Math.max(Math.min(100, Number(v)||0), (t.sell??40)+1) }))

  // ===== Backtest state =====
  const today = new Date()
  const sixAgo = new Date(today.getFullYear(), today.getMonth()-6, today.getDate())
  const toISO = d => d.toISOString().slice(0,10)

  const [btStart, setBtStart] = useState(toISO(sixAgo))
  const [btEnd, setBtEnd]     = useState(toISO(today))
  const [btRows, setBtRows]   = useState([])
  const [btBM, setBtBM]       = useState(null)
  const [btLoading, setBtLoading] = useState(false)
  const [btError, setBtError] = useState('')

  const backtestURL = (fmt='json') => {
    const qsTickers = tickers.split(',').map(t=>t.trim()).filter(Boolean).map(t=>`tickers=${encodeURIComponent(t)}`).join('&')
    return `/api/v1/backtest?${qsTickers}&start=${btStart}&end=${btEnd}&sell_th=${sell}&buy_th=${buy}&format=${fmt}`
  }

  const runBacktest = () => {
    setBtLoading(true); setBtError('')
    fetch(backtestURL('json'))
      .then(r=>r.ok?r.json():Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d=>{
        const rows = (d.data||[]).sort((a,b)=>(b.perf_pct??-1)-(a.perf_pct??-1))
        setBtRows(rows)
        setBtBM(d.benchmark || null)
      })
      .catch(e=>setBtError(e.message||String(e)))
      .finally(()=>setBtLoading(false))
  }

  const exportCSV = () => {
    window.open(backtestURL('csv'), '_blank')
  }

  const perfCell = v => {
    const n = Number(v); if (isNaN(n)) return <span>-</span>
    const color = n > 0 ? '#2e7d32' : (n < 0 ? '#c62828' : '#555')
    return <span style={{color, fontWeight:600}}>{n.toFixed(2)}%</span>
  }

  // riepilogo per segnale
  const summary = (() => {
    const acc = { BUY:{n:0,sum:0}, HOLD:{n:0,sum:0}, SELL:{n:0,sum:0} }
    btRows.forEach(r=>{
      if (r && r.signal_start && typeof r.perf_pct === 'number') {
        const g = acc[r.signal_start] || (acc[r.signal_start]={n:0,sum:0})
        g.n += 1; g.sum += r.perf_pct
      }
    })
    const avg = k => acc[k].n ? (acc[k].sum/acc[k].n) : null
    return {
      BUY:  { n: acc.BUY.n,  avg: avg('BUY') },
      HOLD: { n: acc.HOLD.n, avg: avg('HOLD') },
      SELL: { n: acc.SELL.n, avg: avg('SELL') },
    }
  })()

  return (
    <div style={{ padding: 20, fontFamily: 'system-ui, sans-serif', maxWidth: 1200, margin:'0 auto' }}>
      <h1>Oraculum – Wysocki Indicator</h1>

      {/* Controlli principali */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr auto auto auto', gap:8, alignItems:'center' }}>
        <input style={{ padding:8, border:'1px solid #ddd', borderRadius:8 }}
               value={tickers} onChange={e=>setTickers(e.target.value)}
               placeholder="AAPL,MSFT,GOOGL,TSLA" />
        <div style={{display:'flex', alignItems:'center', gap:6}}>
          <label style={{fontSize:12, opacity:.7}}>SELL &lt;</label>
          <input type="number" min={0} max={99} value={sell}
                 onChange={e=>setSell(e.target.value)}
                 style={{width:64, padding:6, border:'1px solid #ddd', borderRadius:8}}/>
        </div>
        <div style={{display:'flex', alignItems:'center', gap:6}}>
          <label style={{fontSize:12, opacity:.7}}>BUY ≥</label>
          <input type="number" min={1} max={100} value={buy}
                 onChange={e=>setBuy(e.target.value)}
                 style={{width:64, padding:6, border:'1px solid #ddd', borderRadius:8}}/>
        </div>
        <button onClick={loadWI} disabled={loading} style={{ padding:'8px 12px', borderRadius:8 }}>
          {loading ? 'Calcolo…' : 'Calcola'}
        </button>
      </div>

      {/* DASHBOARD */}
      <div style={{ marginTop: 16, display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(360px,1fr))', gap:12 }}>
        {rows.map((r,i)=> {
          const sig = classify(r.wi, sell, buy)
          return (
            <div key={i} style={{ display:'flex', gap:12, alignItems:'center', border:'1px solid #eee', borderRadius:12, padding:12 }}>
              <Gauge value={r.wi || 0} label={r.ticker} />
              <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                <SignalBadge signal={sig} />
                {r.components && <Components c={r.components} />}
                {r.error && <div style={{color:'#c62828', fontSize:12}}>Errore: {r.error}</div>}
              </div>
            </div>
          )
        })}
      </div>

      {/* BACKTEST */}
      <h2 style={{ marginTop: 22 }}>Backtest</h2>
      <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
        <div style={{display:'flex', alignItems:'center', gap:6}}>
          <label style={{fontSize:12, opacity:.7}}>Start</label>
          <input type="date" value={btStart} onChange={e=>setBtStart(e.target.value)}
                 style={{padding:6, border:'1px solid #ddd', borderRadius:8}}/>
        </div>
        <div style={{display:'flex', alignItems:'center', gap:6}}>
          <label style={{fontSize:12, opacity:.7}}>End</label>
          <input type="date" value={btEnd} onChange={e=>setBtEnd(e.target.value)}
                 style={{padding:6, border:'1px solid #ddd', borderRadius:8}}/>
        </div>
        <button onClick={runBacktest} disabled={btLoading} style={{ padding:'8px 12px', borderRadius:8 }}>
          {btLoading ? 'Elaboro…' : 'Calcola backtest'}
        </button>
        <button onClick={exportCSV} disabled={btLoading || !btStart || !btEnd} style={{ padding:'8px 12px', borderRadius:8 }}>
          Esporta CSV
        </button>
        <span style={{opacity:.7, fontSize:12}}>Soglie: SELL &lt; {sell} · BUY ≥ {buy}</span>
      </div>

      {/* Benchmark e tabella */}
      {btRows.length > 0 && (
        <>
          {btBM && (
            <div style={{marginTop:8, fontSize:13, opacity:.8}}>
              Benchmark SPY sul periodo: <b>{typeof btBM.perf_pct==='number' ? `${btBM.perf_pct.toFixed(2)}%` : '-'}</b>
            </div>
          )}
          <div style={{ marginTop:8, border:'1px solid #eee', borderRadius:8, overflow:'hidden' }}>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:14 }}>
              <thead style={{ background:'#fafafa' }}>
                <tr>
                  <th style={{textAlign:'left', padding:8}}>Ticker</th>
                  <th style={{textAlign:'right', padding:8}}>WI@Start</th>
                  <th style={{textAlign:'center', padding:8}}>Segnale</th>
                  <th style={{textAlign:'right', padding:8}}>Start</th>
                  <th style={{textAlign:'right', padding:8}}>End</th>
                  <th style={{textAlign:'right', padding:8}}>Perf %</th>
                </tr>
              </thead>
              <tbody>
                {btRows.map((r,i)=> (
                  <tr key={i} style={{ borderTop:'1px solid #eee' }}>
                    <td style={{padding:8}}>{r.ticker}</td>
                    <td style={{padding:8, textAlign:'right'}}>{r.wi_start?.toFixed?.(2) ?? '-'}</td>
                    <td style={{padding:8, textAlign:'center'}}><SignalBadge signal={r.signal_start}/></td>
                    <td style={{padding:8, textAlign:'right'}}>{r.start_close ?? '-'}</td>
                    <td style={{padding:8, textAlign:'right'}}>{r.end_close ?? '-'}</td>
                    <td style={{padding:8, textAlign:'right'}}>{
                      typeof r.perf_pct==='number' ? (
                        <span style={{color: r.perf_pct>0 ? '#2e7d32' : (r.perf_pct<0 ? '#c62828' : '#555'), fontWeight:600}}>
                          {r.perf_pct.toFixed(2)}%
                        </span>
                      ) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Riepilogo per segnale */}
          <div style={{display:'flex', gap:12, marginTop:10, flexWrap:'wrap'}}>
            {['BUY','HOLD','SELL'].map(k => (
              <div key={k} style={{border:'1px solid #eee', borderRadius:8, padding:'8px 12px'}}>
                <div style={{fontSize:12, opacity:.6}}>{k}</div>
                <div style={{fontSize:22, fontWeight:700}}>{summary[k].n} titoli</div>
                <div style={{fontSize:12, opacity:.7}}>
                  Media: {summary[k].avg!=null ? `${summary[k].avg.toFixed(2)}%` : '-'}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {btError && (
        <div style={{ marginTop:10, padding:10, borderRadius:8, background:'#fdecea', color:'#c62828' }}>
          Backtest errore: {btError}
        </div>
      )}

      <p style={{ marginTop: 16, opacity:.7, fontSize:12 }}>
        Il WI iniziale è calcolato alla data Start usando lo storico precedente. La performance è (Close_end / Close_start - 1)×100.
      </p>
    </div>
  )
}
