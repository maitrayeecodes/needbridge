import { useEffect, useState } from 'react'
import { getProfile, updateProfile } from './api'

export default function ProfilePanel({ user, onUpdated }) {
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState({})
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { getProfile().then((p) => { setProfile(p); setForm({ name:p.name, phone:p.phone || '', organisation_name:p.organisation?.name || '', description:p.organisation?.description || '', area:p.organisation?.area || '', contact_phone:p.organisation?.contact_phone || '' }) }).catch((e) => setError(e.message)) }, [user?.id])
  const change = (key, value) => setForm((x) => ({ ...x, [key]: value }))
  const submit = async (e) => { e.preventDefault(); setBusy(true); setError(''); setMessage(''); try { const payload = { name: form.name, phone: form.phone }; if (profile.organisation?.member_role === 'owner' || profile.organisation?.member_role === 'manager') Object.assign(payload, { organisation_name: form.organisation_name, description: form.description, area: form.area, contact_phone: form.contact_phone }); await updateProfile(payload); const p = await getProfile(); setProfile(p); setMessage('Your profile has been updated.'); onUpdated?.() } catch (e) { setError(e.message) } finally { setBusy(false) } }
  if (!profile) return <section className="blk"><div className="wrap">{error ? <p className="err">{error}</p> : <p>Loading profile…</p>}</div></section>
  return <section className="blk alt" id="profile"><div className="wrap"><div className="rv"><span className="kick">Your account</span><h2>Profile & <em>details</em></h2><p className="sub">Keep your contact information current so accepted donations can be coordinated smoothly.</p></div>
    {error && <p className="err" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <form className="card profile-form" onSubmit={submit}>
      <label className="f">Your name<input required minLength="2" maxLength="100" value={form.name || ''} onChange={(e)=>change('name',e.target.value)} /></label>
      <label className="f">Email address<input value={profile.email} readOnly /></label>
      <label className="f">Your contact number<input type="tel" maxLength="30" value={form.phone || ''} onChange={(e)=>change('phone',e.target.value)} placeholder="Add a phone number" /></label>
      {profile.organisation && <><hr/><h3>Institution details</h3><p className="dn">Verification: {profile.organisation.verification_status.replaceAll('_',' ')}</p>
        <label className="f">Institution name<input disabled={!['owner','manager'].includes(profile.organisation.member_role)} required maxLength="160" value={form.organisation_name || ''} onChange={(e)=>change('organisation_name',e.target.value)} /></label>
        <label className="f">About the institution<textarea disabled={!['owner','manager'].includes(profile.organisation.member_role)} rows="3" maxLength="2000" value={form.description || ''} onChange={(e)=>change('description',e.target.value)} /></label>
        <label className="f">Service area<input disabled={!['owner','manager'].includes(profile.organisation.member_role)} required value={form.area || ''} onChange={(e)=>change('area',e.target.value)} /></label>
        <label className="f">Institution contact number<input disabled={!['owner','manager'].includes(profile.organisation.member_role)} type="tel" maxLength="30" value={form.contact_phone || ''} onChange={(e)=>change('contact_phone',e.target.value)} /></label>
      </>}
      <button className="btn p" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button>
    </form>
  </div></section>
}
