import { useEffect, useState } from 'react'
import { createOffer, getMatches } from './api'

// Suggestions are role-specific and explainable; people still decide whether to offer.
export default function Matches({ version, user, onChange }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [sent, setSent] = useState('')

  useEffect(() => {
    let live = true
    getMatches().then((data) => { if (live) { setRows(data); setError('') } })
      .catch((e) => { if (live) { setRows([]); setError(e.message) } })
    return () => { live = false }
  }, [version])

  const offer = async (match) => {
    setBusy(match.donation); setError(''); setSent('')
    try {
      await createOffer({ donation_id: match.donation, requirement_id: match.requirement, quantity: Math.min(match.available, match.needed) })
      setSent(user.role === 'donor' ? 'Your offer has been sent to the institution.' : 'Your invitation has been sent to the donor.')
      onChange?.()
    } catch (e) { setError(e.message) }
    finally { setBusy('') }
  }

  if (!rows.length && !error) return null
  return (
    <section className="blk alt">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Smart matching</span>
          <h2>Possible connections <em>nearby</em></h2>
          <p className="sub">Suggestions use category, age suitability, approximate area distance, item condition and quantity. You decide whether to send an offer.</p>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {sent && <p role="status">{sent}</p>}
        <div className="grid">
          {rows.map((r) => (
            <article className="card" key={r.donation + r.requirement}>
              <span className="badge">Match score {r.score}/100</span>
              <h3>{r.donation_title} ↔ {r.requirement_title}</h3>
              <p>{r.donation_area} → {r.requirement_area}</p>
              <ul>{r.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
              <p className="dn">{r.available} available · {r.needed} needed</p>
              <button className="btn p" disabled={!!busy} onClick={() => offer(r)}>
                {busy === r.donation ? 'Sending…' : user.role === 'donor' ? 'Offer this donation' : 'Invite this donor'}
              </button>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
