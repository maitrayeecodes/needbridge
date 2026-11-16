import { useEffect, useState } from 'react'
import { getPending, reviewDocument, reviewOrganisation, getReports, reviewReport, getAdminAccounts, setAccountActive } from './api'

export default function Admin({ onChange }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [reports, setReports] = useState([])
  const [reportNote, setReportNote] = useState({})
  const [accounts, setAccounts] = useState([])

  const load = () => Promise.all([getPending(), getReports(), getAdminAccounts()]).then(([orgs, reportsData, accountData]) => { setRows(orgs); setReports(reportsData); setAccounts(accountData) }).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const act = async (key, action, callback) => {
    setBusy(key); setError('')
    try { await callback(); await load(); onChange() }
    catch (e) { setError(e.message) }
    finally { setBusy('') }
  }

  return (
    <section className="blk alt" id="admin">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Admin</span>
          <h2>Institutions waiting for <em>verification</em></h2>
          <p className="sub">Review official documents privately. An institution can be verified only after at least one document has been approved.</p>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        <div className="rv" style={{ marginTop: '3rem' }}><span className="kick">Account administration</span><h2>Community <em>accounts</em></h2><p className="sub">Suspend access when an account presents a verified safety concern. Institution accounts suspended here also have their organisation verification status suspended.</p></div>
        <div className="grid">{accounts.map((account) => <article className="card" key={account.id}><span className="badge">{account.is_active ? 'active' : 'suspended'}</span><h3>{account.name}</h3><p>{account.email} · {account.role === 'org_member' ? 'Institution' : 'Donor'}</p><button className={account.is_active ? 'btn o' : 'btn p'} disabled={!!busy} onClick={() => act(account.id, account.is_active ? 'suspend' : 'reactivate', () => setAccountActive(account.id, !account.is_active))}>{account.is_active ? 'Suspend account' : 'Reactivate account'}</button></article>)}</div>
        <div className="rv" style={{ marginTop: '3rem' }}><span className="kick">Trust & safety</span><h2>Community <em>reports</em></h2><p className="sub">Review concerns raised about public listings and institutions. Reporter identities are not exposed to the reported party.</p></div>
        <div className="grid">
          {reports.filter((r) => ['open', 'in_review'].includes(r.status)).length === 0 && <div className="empty"><b>No open reports.</b><p>New community reports will appear here.</p></div>}
          {reports.filter((r) => ['open', 'in_review'].includes(r.status)).map((r) => <article className="card" key={r.id}>
            <div className="notification-meta"><span className="badge">{r.status.replace('_', ' ')}</span><span className="badge">{r.target_type}</span></div>
            <h3>{r.target_name}</h3><p><b>Reason:</b> {r.reason.replaceAll('_', ' ')} · <b>Reported by:</b> {r.reporter}</p>
            {r.details && <p>{r.details}</p>}
            <label className="f">Review note<textarea rows="2" maxLength="1000" value={reportNote[r.id] || ''} onChange={(e) => setReportNote((n) => ({ ...n, [r.id]: e.target.value }))} /></label>
            <div className="row"><button className="btn o" disabled={!!busy} onClick={() => act(r.id, 'in-review', () => reviewReport(r.id, 'in_review', reportNote[r.id] || ''))}>Mark in review</button><button className="btn p" disabled={!!busy} onClick={() => act(r.id, 'resolve', () => reviewReport(r.id, 'resolve', reportNote[r.id] || ''))}>Resolve</button><button className="btn o" disabled={!!busy} onClick={() => act(r.id, 'dismiss', () => reviewReport(r.id, 'dismiss', reportNote[r.id] || ''))}>Dismiss</button></div>
          </article>)}
        </div>
        <div className="grid">
          {rows === null && <p>Loading…</p>}
          {rows && rows.length === 0 && <div className="empty"><b>Nothing to review.</b><p>New institution registrations will appear here.</p></div>}
          {rows && rows.map((org) => {
            const approved = org.documents.some((d) => d.review_status === 'approved')
            return (
              <article className="card" key={org.id}>
                <span className="badge w">{org.verification_status.replace('_', ' ')}</span>
                <h3>{org.name}</h3>
                <p>{org.type.replace('_', ' ')} · {org.area}</p>
                {org.description && <p>{org.description}</p>}
                <p>{org.contact_phone || 'No contact number supplied'}</p>
                <h4>Submitted documents</h4>
                {!org.documents.length && <p className="dn">No documents uploaded yet.</p>}
                {org.documents.map((doc) => (
                  <div className="row" key={doc.id} style={{ alignItems: 'center', marginBottom: '.5rem' }}>
                    <span>{doc.document_type.replaceAll('_', ' ')} · {doc.review_status}</span>
                    <a href={doc.file_url} target="_blank" rel="noreferrer">View privately</a>
                    {doc.review_status === 'pending' && <>
                      <button className="btn p" disabled={!!busy} onClick={() => act(doc.id, 'approve', () => reviewDocument(doc.id, 'approve'))}>Approve doc</button>
                      <button className="btn o" disabled={!!busy} onClick={() => act(doc.id, 'reject', () => reviewDocument(doc.id, 'reject'))}>Reject doc</button>
                    </>}
                  </div>
                ))}
                <div className="row">
                  <button className="btn p" disabled={!approved || !!busy} onClick={() => act(org.id, 'verify', () => reviewOrganisation(org.id, 'verify'))}>Verify institution</button>
                  <button className="btn o" disabled={!!busy} onClick={() => act(org.id, 'reject-org', () => reviewOrganisation(org.id, 'reject'))}>Reject institution</button>
                </div>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
