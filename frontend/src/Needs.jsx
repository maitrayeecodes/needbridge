import { useEffect, useMemo, useState } from 'react'
import { AREAS, CATS, ICONS, WHY } from './data'
import { getNeeds, submitReport } from './api'

export default function Needs({ cat, setCat, onOffer, version, user }) {
  const [reporting, setReporting] = useState('')
  const [reportReason, setReportReason] = useState('suspicious')
  const [reportDetails, setReportDetails] = useState('')
  const [reportMessage, setReportMessage] = useState('')
  const [reportBusy, setReportBusy] = useState(false)
  const [area, setArea] = useState('Kranti Chowk')
  const [q, setQ] = useState('')
  const [radius, setRadius] = useState(0)
  const [sort, setSort] = useState('near')
  const [needs, setNeeds] = useState([])
  const [status, setStatus] = useState('loading')
  const [retry, setRetry] = useState(0)

  // Ask the Python server for the needs whenever the area, category or data changes
  useEffect(() => {
    let live = true
    setStatus('loading')
    getNeeds(area, cat)
      .then((d) => { if (live) { setNeeds(d); setStatus('ok') } })
      .catch(() => { if (live) setStatus('error') })
    return () => { live = false }
  }, [area, cat, version, retry])

  const shown = useMemo(() => needs
    .filter((n) => (!radius || n.distance_km <= radius) &&
      `${n.item} ${n.organization} ${n.area}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => sort === 'left' ? b.remaining - a.remaining : (a.distance_km ?? 99) - (b.distance_km ?? 99)),
  [needs, q, radius, sort])

  const reset = () => { setCat(''); setQ(''); setRadius(0); setSort('near'); setArea('Kranti Chowk') }

  return (
    <section className="blk" id="needs">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Browse needs</span>
          <h2>Needs waiting <em>near you</em></h2>
          <p className="sub">Real requests from verified organisations in Chhatrapati Sambhajinagar. Pick your area to see how far each one is.</p>
        </div>

        <div className="chips" role="group" aria-label="Category filter">
          <button className="chip" aria-pressed={cat === ''} onClick={() => setCat('')}>All</button>
          {CATS.map((c) => (
            <button key={c[0]} className="chip" aria-pressed={cat === c[0]} onClick={() => setCat(c[0])}>{c[1]}</button>
          ))}
        </div>

        <div className="filters">
          <form className="search" role="search" onSubmit={(e) => e.preventDefault()}>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notebooks, school bags…" aria-label="Search needs" />
          </form>
          <label className="fl">Your area
            <select value={area} onChange={(e) => setArea(e.target.value)}>{AREAS.map((a) => <option key={a}>{a}</option>)}</select>
          </label>
          <label className="fl">Within
            <select value={radius} onChange={(e) => setRadius(+e.target.value)}>
              <option value={0}>Any distance</option><option value={3}>3 km</option><option value={5}>5 km</option><option value={10}>10 km</option>
            </select>
          </label>
          <label className="fl">Sort
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="near">Nearest first</option><option value="left">Most still needed</option>
            </select>
          </label>
          <button className="btn o" type="button" onClick={reset}>Reset</button>
        </div>

        {status === 'ok' && <p id="count" aria-live="polite">{shown.length} need{shown.length === 1 ? '' : 's'} · distances from {area}</p>}
        {reportMessage && !reporting && <p className="dn" role="status">{reportMessage}</p>}

        <div className="grid">
          {status === 'loading' && <p>Loading needs…</p>}
          {status === 'error' && (
            <div className="empty">
              <b>Can’t reach the server.</b>
              <p>Start it in a terminal with: uvicorn backend.api:app --reload</p>
              <button className="btn o" onClick={() => setRetry(retry + 1)}>Try again</button>
            </div>
          )}
          {status === 'ok' && shown.length === 0 && (
            <div className="empty"><b>No needs match these filters.</b><p>Try a larger distance or another category.</p><button className="btn o" onClick={reset}>Reset filters</button></div>
          )}
          {status === 'ok' && shown.map((n) => (
            <article className="card" key={n.id}>
              <span className="badge">{n.remaining === 0 ? 'Fulfilled' : 'Verified organisation'}</span>
              <h3>{n.item}</h3>
              <p>{n.organization}</p>
              <p className="why">“{WHY[n.category]}”</p>
              <p className="loc">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d={ICONS.pin} /></svg>
                {n.area}, Chhatrapati Sambhajinagar · {n.distance_km < 0.5 ? 'In your area' : `about ${n.distance_km} km away`}
              </p>
              <p>Ages {n.age_min} to {n.age_max}</p>
              <div className="prog" role="img" aria-label={`${n.fulfilled} of ${n.needed} fulfilled`}>
                <i style={{ width: `${(n.fulfilled / n.needed) * 100}%` }} />
              </div>
              <p>{n.fulfilled} of {n.needed} fulfilled · {n.remaining} still needed</p>
              <div className="row">
                {n.remaining > 0 && <button className="btn p" onClick={() => onOffer(n)}>Offer this</button>}
                {user && user.role !== 'admin' && <button className="btn o" type="button" onClick={() => { setReporting(reporting === n.id ? '' : n.id); setReportMessage('') }}>Report listing</button>}
              </div>
              {reporting === n.id && <div className="listing-edit" aria-label="Report this requirement">
                <label className="f">Reason<select value={reportReason} onChange={(e) => setReportReason(e.target.value)}><option value="suspicious">Suspicious activity</option><option value="misleading">Misleading information</option><option value="inappropriate">Inappropriate content</option><option value="duplicate">Duplicate listing</option><option value="safety_concern">Safety concern</option><option value="other">Other</option></select></label>
                <label className="f">Additional details (optional)<textarea rows="2" maxLength="1000" value={reportDetails} onChange={(e) => setReportDetails(e.target.value)} /></label>
                <div className="row"><button className="btn p" type="button" disabled={reportBusy} onClick={async () => { setReportBusy(true); setReportMessage(''); try { const r = await submitReport('requirement', n.id, reportReason, reportDetails); setReportMessage(r.message); setReporting(''); setReportDetails('') } catch (e) { setReportMessage(e.message) } finally { setReportBusy(false) } }}>Submit report</button><button className="btn o" type="button" onClick={() => setReporting('')}>Cancel</button></div>
              </div>}
              {reportMessage && reporting === n.id && <p className="dn" role="status">{reportMessage}</p>}
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}