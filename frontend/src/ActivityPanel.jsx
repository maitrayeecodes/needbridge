import { useEffect, useState } from 'react'
import { cancelHandover, confirmHandover, getOffers, getOfferContacts, respondOffer, scheduleHandover } from './api'

export default function ActivityPanel({ user, version, onChange }) {
  const [rows, setRows] = useState([])
  const [received, setReceived] = useState({})
  const [scheduleTimes, setScheduleTimes] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [contacts, setContacts] = useState({})

  const load = () => getOffers().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load() }, [version])

  const act = async (key, fn, success) => {
    setBusy(key); setError(''); setMessage('')
    try { await fn(); setMessage(success); await load(); onChange?.() }
    catch (e) { setError(e.message) }
    finally { setBusy('') }
  }

  if (!rows.length && !error) return null
  return (
    <section className="blk" id="activity">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Your NeedBridge activity</span>
          <h2>Offers and <em>handovers</em></h2>
          <p className="sub">Accept or decline incoming offers, coordinate the handover, and confirm only what was actually received.</p>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
        <div className="grid">
          {rows.map((offer) => {
            const h = offer.handover
            const qty = received[h?.id] ?? h?.quantity_agreed ?? offer.quantity
            const pendingIncoming = offer.status === 'pending' && offer.incoming
            const canConfirm = h && ['proposed', 'scheduled', 'in_progress', 'awaiting_confirmation'].includes(h.status) && !h.confirmed_by_me
            const canCancel = h && ['proposed', 'scheduled', 'in_progress'].includes(h.status) && h.confirmation_count === 0
            return (
              <article className="card" key={offer.id}>
                <span className="badge">{offer.status.replaceAll('_', ' ')}</span>
                <h3>{offer.donation_title} → {offer.requirement_title}</h3>
                <p>{offer.organisation} · {offer.quantity} item(s)</p>
                {pendingIncoming && <p className="dn">This offer is waiting for your response.</p>}
                {offer.status === 'pending' && !offer.incoming && <p className="dn">Waiting for the other party to respond.</p>}
                {pendingIncoming && <div className="row">
                  <button className="btn p" disabled={!!busy} onClick={() => act(offer.id, () => respondOffer(offer.id, 'accept'), 'Offer accepted. You can now coordinate the handover.')}>Accept</button>
                  <button className="btn o" disabled={!!busy} onClick={() => act(offer.id, () => respondOffer(offer.id, 'decline'), 'Offer declined.')}>Decline</button>
                </div>}
                {h && <>
                  <p>Handover: <b>{h.status.replaceAll('_', ' ')}</b> · {h.confirmation_count}/2 confirmations</p>
                  {offer.status === 'accepted' && <div className="contact-box"><button className="btn o" type="button" disabled={!!busy} onClick={() => act(offer.id, async () => { const c = await getOfferContacts(offer.id); setContacts((x) => ({ ...x, [offer.id]: c })) }, 'Contact details loaded for this accepted offer.')}>View handover contact</button>{contacts[offer.id] && <div><b>{contacts[offer.id].name}</b>{contacts[offer.id].organisation && <p>{contacts[offer.id].organisation}</p>}<p>{contacts[offer.id].phone || 'No phone number shared'} · {contacts[offer.id].email || 'No email available'}</p><small>{contacts[offer.id].note}</small></div>}</div>}
                  {h.scheduled_at && <p>Proposed time: {new Date(h.scheduled_at).toLocaleString()}</p>}
                  {['proposed', 'scheduled'].includes(h.status) && <div className="row" style={{ alignItems: 'end' }}>
                    <label className="f">Handover date and time
                      <input type="datetime-local" value={scheduleTimes[h.id] || ''}
                        onChange={(e) => setScheduleTimes((x) => ({ ...x, [h.id]: e.target.value }))} />
                    </label>
                    <button className="btn o" disabled={!!busy || !scheduleTimes[h.id]}
                      onClick={() => act(h.id, () => scheduleHandover(h.id, new Date(scheduleTimes[h.id]).toISOString()), 'Handover time sent to the other party.')}>Schedule handover</button>
                  </div>}
                  {canConfirm && <div className="row" style={{ alignItems: 'end' }}>
                    <label className="f">Quantity actually received
                      <input type="number" min="0" max={h.quantity_agreed} value={qty}
                        onChange={(e) => setReceived((x) => ({ ...x, [h.id]: e.target.value }))} />
                    </label>
                    <button className="btn p" disabled={!!busy || qty === '' || Number(qty) < 0 || Number(qty) > h.quantity_agreed}
                      onClick={() => act(h.id, () => confirmHandover(h.id, qty), 'Your handover confirmation has been recorded.')}>Confirm receipt</button>
                  </div>}
                  {h.confirmed_by_me && h.status === 'awaiting_confirmation' && <p className="dn">You confirmed. Waiting for the other party.</p>}
                  {h.status === 'disputed' && <p className="err">The two parties reported different quantities. This needs admin resolution.</p>}
                  {canCancel && <button className="btn o" disabled={!!busy} onClick={() => act(h.id, () => cancelHandover(h.id), 'Handover cancelled. Reserved quantity has been released.')}>Cancel handover</button>}
                  {h.status === 'completed' && <p className="dn">Both parties confirmed the handover.</p>}
                  {h.status === 'partially_completed' && <p className="dn">Both parties confirmed a partial receipt of {h.quantity_received} item(s).</p>}
                </>}
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
