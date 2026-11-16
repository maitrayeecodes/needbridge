import { useState } from 'react'
import { uploadVerificationDocument } from './api'

export default function VerificationPanel({ user, onUploaded }) {
  const [file, setFile] = useState(null)
  const [documentType, setDocumentType] = useState('registration_certificate')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const org = user?.organisation

  if (!org || org.verification_status === 'verified') return null

  const submit = async (event) => {
    event.preventDefault()
    if (!file) { setError('Choose a PDF, JPG or PNG document first.'); return }
    setBusy(true); setError(''); setMessage('')
    try {
      await uploadVerificationDocument(org.id, file, documentType)
      setFile(null)
      setMessage('Document uploaded securely. It is now waiting for NeedBridge admin review.')
      onUploaded?.()
    } catch (e) {
      setError(e.message)
    } finally { setBusy(false) }
  }

  return (
    <section className="blk alt" id="verification">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Institution verification</span>
          <h2>One step before your needs <em>go live</em></h2>
          <p className="sub">Your organisation is currently <b>{org.verification_status.replace('_', ' ')}</b>. Upload an official document so our team can review it. This file is private and is never shown to donors.</p>
        </div>
        <form className="card" onSubmit={submit} style={{ maxWidth: 620 }}>
          <label className="f">Document type
            <select value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
              <option value="registration_certificate">Registration certificate</option>
              <option value="trust_deed">Trust deed</option>
              <option value="school_recognition">School recognition document</option>
              <option value="other">Other official document</option>
            </select>
          </label>
          <label className="f">Choose document (PDF, JPG or PNG; maximum 10 MB)
            <input type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>
          {file && <p className="dn">Selected: {file.name}</p>}
          {error && <p className="err" role="alert">{error}</p>}
          {message && <p role="status">{message}</p>}
          <div className="dr"><button className="btn p" type="submit" disabled={busy}>{busy ? 'Uploading securely…' : 'Upload for verification'}</button></div>
        </form>
      </div>
    </section>
  )
}
