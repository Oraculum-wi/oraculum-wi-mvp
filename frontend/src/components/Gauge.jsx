import React, { useEffect, useState } from 'react'

// stessi stop della sfumatura della barra
const STOPS = [
  { p: 0,   c: '#b71c1c' }, // rosso scuro
  { p: 15,  c: '#e53935' },
  { p: 35,  c: '#fb8c00' }, // arancio
  { p: 50,  c: '#fdd835' }, // giallo
  { p: 70,  c: '#7cb342' }, // lime
  { p: 85,  c: '#43a047' }, // verde
  { p: 100, c: '#2e7d32' }  // verde scuro
]

// interpolazione lineare tra due colori hex
function lerpColor(hex1, hex2, t) {
  const a = hex1.match(/\w\w/g).map(h => parseInt(h, 16))
  const b = hex2.match(/\w\w/g).map(h => parseInt(h, 16))
  const m = a.map((ai,i) => Math.round(ai + (b[i]-ai)*t))
  return '#' + m.map(x => x.toString(16).padStart(2,'0')).join('')
}

// colore esatto alla posizione percentuale v (0..100) usando gli stop
function colorAt(v) {
  const x = Math.max(0, Math.min(100, Number(v) || 0))
  let left = STOPS[0], right = STOPS[STOPS.length-1]
  for (let i=0; i<STOPS.length-1; i++) {
    if (x >= STOPS[i].p && x <= STOPS[i+1].p) {
      left = STOPS[i]; right = STOPS[i+1]; break
    }
  }
  const span = right.p - left.p || 1
  const t = (x - left.p) / span
  return lerpColor(left.c, right.c, t)
}

export default function Gauge({ value = 50, label = 'WI' }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0))
  const numColor = colorAt(v)

  // animazione sobria del numero: fade-out → aggiorna → fade-in (tot ~300ms)
  const [shownValue, setShownValue] = useState(Math.round(v))
  const [opacity, setOpacity] = useState(1)

  useEffect(() => {
    setOpacity(0)                 // fade out
    const mid = setTimeout(() => {
      setShownValue(Math.round(v))// aggiorna cifra
      setOpacity(1)               // fade in
    }, 150)                       // metà del tempo totale
    return () => clearTimeout(mid)
  }, [v])

  // gradiente fisso sull’intera track
  const gradient =
    'linear-gradient(90deg,' + STOPS.map(s => `${s.c} ${s.p}%`).join(',') + ')'

  return (
    <div style={{ border: '1px solid #eee', borderRadius: 12, padding: 12, width: 260 }}>
      <div style={{ fontSize: 12, opacity: .7 }}>{label}</div>

      {/* numero: colore dalla sfumatura + fade 0.3s */}
      <div
        style={{
          fontSize: 48,
          textAlign: 'center',
          lineHeight: 1,
          color: numColor,
          opacity,
          transition: 'opacity 300ms ease, color 300ms ease'
        }}
      >
        {shownValue}
      </div>

      {/* Track: gradiente 0→100 + overlay grigio per la parte non riempita.
          L’overlay si muove con transizione (width 300ms). */}
      <div
        style={{
          position: 'relative',
          height: 12,
          borderRadius: 6,
          overflow: 'hidden',
          background: gradient,
          boxShadow: 'inset 0 0 0 1px rgba(0,0,0,.05)',
          marginTop: 6
        }}
        aria-label="score-bar"
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: `${100 - v}%`,
            height: '100%',
            background: '#eee',
            transition: 'width 300ms ease'
          }}
        />
      </div>

      <div style={{ marginTop: 6, fontSize: 11, display: 'flex', justifyContent: 'space-between', opacity: .5 }}>
        <span>0</span><span>100</span>
      </div>
    </div>
  )
}
