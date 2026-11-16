import { useEffect, useRef, useState } from 'react'
import { AREAS, CATS } from './data'
import { postDonation, postRequest, uploadDonationPhoto } from './api'

const blank = { item: '', category: 'notebooks', qty: 1, condition: 'good', age_min: 6, age_max: 12, area: 'Cidco' }

// mode = 'offer' (a donor gives something) or 'need' (an organisation asks for something)
export default function FormDialog({ mode, need, user, onClose, onSaved }) {
  const ref = useRef(null)
  const [f, setF] = useState(blank)
  const [error, setError] = useState('')
  const [doneId, setDoneId] = useState(null)
  const [photo, setPhoto] = useState(null)
  const [photoWarning, setPhotoWarning] = useState('')
  const [busy, setBusy] = useState(false)
  const offer = mode === 'offer'

  useEffect(() => {
    const d = ref.current
    if (mode && !d.open) {
      setError(''); setDoneId(null); setPhoto(null); setPhotoWarning('')
      setF(need ? { ...blank, item: need.item, category: need.category, age_min: need.age_min, age_max: need.age_max, area: need.area } : blank)
      d.showModal()
    }
    if (!mode && d.open) d.close()
  }, [mode, need])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const shared = { item: f.item, category: f.category, age_min: f.age_min, age_max: f.age_max, area: f.area }
      if (offer && photo && photo.size > 5 * 1024 * 1024) throw new Error('Photo must be 5 MB or smaller.')
      const res = offer
        ? await postDonation({ ...shared, quantity: f.qty, condition: f.condition })
        : await postRequest({ ...shared, quantity_needed: f.qty })
      if (offer && photo) {
        try { await uploadDonationPhoto(res.id, photo) }
        catch (photoError) { setPhotoWarning(`Your donation was saved, but the photo could not be uploaded: ${photoError.message}`) }
      }
      setDoneId(res.id)
      onSaved()
    } catch (x) {
      setError(x.message === 'Failed to fetch' ? 'Can’t reach the server. Is uvicorn running?' : x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="fd-title">
      {doneId ? (
        <div>
          <h3 id="fd-title">{offer ? 'Thank you for giving.' : 'Need saved.'}</h3>
          <p className="dn">
            {offer
              ? `Saved as ${doneId}. It can now be matched with verified institutional needs.`
              : `Saved as ${doneId}. Your organisation’s need is now visible to donors.`}
          </p>
          {photoWarning && <p className="err" role="status">{photoWarning}</p>}
          <div className="dr"><button className="btn p" onClick={onClose}>Close</button></div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate>
          <h3 id="fd-title">{offer ? 'Offer an item' : 'Post a need'}</h3>
          <p className="dn">{offer ? `Giving as ${user?.name}. Someone will be glad of this.` : `Posting as ${user?.name}. Your verified organisation’s need will be visible to donors.`}</p>
          <label className="f">Item<input value={f.item} onChange={set('item')} maxLength={60} placeholder="e.g. Ruled notebooks" /></label>
          <div className="two">
            <label className="f">Category
              <select value={f.category} onChange={set('category')}>{CATS.map((c) => <option key={c[0]} value={c[0]}>{c[1]}</option>)}</select>
            </label>
            <label className="f">{offer ? 'Quantity' : 'Quantity needed'}<input type="number" min="1" max="500" value={f.qty} onChange={set('qty')} /></label>
          </div>
          <div className="two">
            <label className="f">Youngest age<input type="number" min="3" max="18" value={f.age_min} onChange={set('age_min')} /></label>
            <label className="f">Oldest age<input type="number" min="3" max="18" value={f.age_max} onChange={set('age_max')} /></label>
          </div>
          <div className="two">
            {offer && (
              <label className="f">Condition
                <select value={f.condition} onChange={set('condition')}><option value="new">New</option><option value="good">Good</option><option value="fair">Fair</option></select>
              </label>
            )}
            <label className="f">Area
              <select value={f.area} onChange={set('area')}>{AREAS.map((a) => <option key={a}>{a}</option>)}</select>
            </label>
          </div>
          {offer && <label className="f">Item photo (optional · JPG, PNG or WebP · max 5 MB)
            <input type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
          </label>}
          <p className="err" role="alert">{error}</p>
          <div className="dr">
            <button className="btn o" type="button" onClick={onClose}>Cancel</button>
            <button className="btn p" type="submit" disabled={busy}>{busy ? 'Saving…' : offer ? 'Save offer' : 'Post need'}</button>
          </div>
        </form>
      )}
    </dialog>
  )
}