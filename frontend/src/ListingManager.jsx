import { useEffect, useState } from 'react'
import { changeListingStatus, getMyListings, updateListing, getListingActivity } from './api'

const actions = (row) => {
  if (row.status === 'paused') return [{ id: 'resume', label: 'Resume', style: 'p' }]
  if (row.kind === 'donation') {
    if (['active', 'partially_fulfilled'].includes(row.status)) return [
      { id: 'pause', label: 'Pause', style: 'o' }, { id: 'withdraw', label: 'Withdraw', style: 'o' },
    ]
  } else if (['open', 'partially_fulfilled'].includes(row.status)) return [
    { id: 'pause', label: 'Pause', style: 'o' }, { id: 'close', label: 'Close requirement', style: 'o' },
  ]
  return []
}

export default function ListingManager({ user, version = 0, onChange }) {
  const [rows, setRows] = useState([])
  const [editing, setEditing] = useState('')
  const [draft, setDraft] = useState({})
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')
  const [activity, setActivity] = useState({})

  const load = () => getMyListings().then((items) => { setRows(items); setError('') }).catch((e) => setError(e.message))
  useEffect(() => { let live = true; getMyListings().then((items) => { if (live) setRows(items) }).catch((e) => { if (live) setError(e.message) }); return () => { live = false } }, [user?.id, version])

  const startEdit = (row) => {
    setEditing(row.id)
    setDraft({ title: row.title, description: row.description || '', area: row.area, quantity: row.quantity_total })
    setError(''); setMessage('')
  }
  const save = async (row) => {
    setBusy(row.id); setError(''); setMessage('')
    try {
      await updateListing(row.kind, row.id, {
        title: draft.title, description: draft.description, area: draft.area,
        [row.kind === 'donation' ? 'quantity_total' : 'quantity_requested']: Number(draft.quantity),
      })
      setEditing(''); setMessage('Listing updated.'); await load(); onChange?.()
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const changeStatus = async (row, action) => {
    setBusy(row.id); setError(''); setMessage('')
    try { await changeListingStatus(row.kind, row.id, action); setMessage(`Listing ${action === 'close' ? 'closed' : action === 'withdraw' ? 'withdrawn' : `${action}d`}.`); await load(); onChange?.() }
    catch (e) { setError(e.message) } finally { setBusy('') }
  }

  return (
    <section className="blk" id="my-listings">
      <div className="wrap">
        <div className="rv"><span className="kick">Manage your contributions</span><h2>Your <em>listings</em></h2><p className="sub">Edit details, pause availability or close listings. Changes are blocked while an offer is pending or accepted, so agreed handovers stay consistent.</p></div>
        {error && <p className="err" role="alert">{error}</p>}
        {message && <p className="dn" role="status">{message}</p>}
        {!rows.length && !error && <div className="empty"><h3>No listings yet</h3><p className="dn">Your donations or institution requirements will appear here after you publish them.</p></div>}
        <div className="grid">
          {rows.map((row) => {
            const isEditing = editing === row.id
            return <article className="card listing-card" key={`${row.kind}-${row.id}`}>
              <div className="notification-meta"><span className="badge">{row.kind === 'donation' ? 'Donation' : 'Requirement'}</span><span className="badge">{row.status.replaceAll('_', ' ')}</span></div>
              {isEditing ? <div className="listing-edit">
                <label className="f">Title<input maxLength="120" value={draft.title} onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))} /></label>
                <label className="f">Description<textarea rows="3" value={draft.description} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} /></label>
                <label className="f">Area<input value={draft.area} onChange={(e) => setDraft((d) => ({ ...d, area: e.target.value }))} /></label>
                <label className="f">Total quantity<input type="number" min={Math.max(1, row.quantity_reserved + row.quantity_completed)} value={draft.quantity} onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))} /></label>
                <div className="row"><button className="btn p" type="button" disabled={!!busy} onClick={() => save(row)}>Save changes</button><button className="btn o" type="button" disabled={!!busy} onClick={() => setEditing('')}>Cancel</button></div>
              </div> : <>
                <h3>{row.title}</h3><p>{row.category} · {row.area}</p>
                {row.description && <p>{row.description}</p>}
                <p className="dn">Total: {row.quantity_total} · Reserved: {row.quantity_reserved} · Completed: {row.quantity_completed} · Remaining: {row.quantity_remaining}</p>
                <button className="btn o" type="button" onClick={async () => { if (activity[row.id]) { setActivity((a) => ({ ...a, [row.id]: null })); return } try { const entries = await getListingActivity(row.kind, row.id); setActivity((a) => ({ ...a, [row.id]: entries })) } catch (e) { setError(e.message) } }}> {activity[row.id] ? 'Hide activity' : 'View activity'} </button>
                {activity[row.id] && <div className="listing-activity"><b>Listing history</b>{activity[row.id].length === 0 ? <p className="dn">No activity recorded yet.</p> : activity[row.id].map((entry, i) => <p key={`${entry.action}-${i}`} className="dn">{entry.action.replaceAll('.', ' ').replaceAll('_', ' ')} · {new Date(entry.created_at).toLocaleString()}</p>)}</div>}
                <div className="row"><button className="btn o" type="button" disabled={!!busy || ['withdrawn', 'closed', 'completed', 'rejected'].includes(row.status)} onClick={() => startEdit(row)}>Edit</button>
                  {actions(row).map((a) => <button key={a.id} className={`btn ${a.style}`} type="button" disabled={!!busy} onClick={() => changeStatus(row, a.id)}>{a.label}</button>)}
                </div>
              </>}
            </article>
          })}
        </div>
      </div>
    </section>
  )
}
