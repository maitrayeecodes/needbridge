import { useEffect, useState } from 'react'
import { getDashboard } from './api'

const labels = {
  donations_total: 'Donations listed', donations_active: 'Active listings',
  items_available: 'Items still available', items_donated: 'Items donated',
  offers_sent: 'Offers sent', offers_to_review: 'Offers to review', handovers_completed: 'Completed handovers',
  requirements_total: 'Requirements posted', requirements_open: 'Open requirements',
  items_still_needed: 'Items still needed', items_received: 'Items received',
  invitations_sent: 'Invitations sent', pending_organisations: 'Institutions to review',
  verified_organisations: 'Verified institutions', open_disputes: 'Open disputes',
  unread_notifications: 'Unread notifications',
}

export default function DashboardPanel({ user, version = 0 }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    getDashboard().then((value) => { if (live) { setData(value); setError('') } })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [version, user?.id])
  if (error) return <section className="blk"><div className="wrap"><p className="err" role="alert">Dashboard: {error}</p></div></section>
  if (!data) return <section className="blk"><div className="wrap"><p>Loading your dashboard…</p></div></section>
  const stats = Object.entries(data.metrics || {}).filter(([key]) => key !== 'unread_notifications')
  return (
    <section className="blk alt" id="dashboard">
      <div className="wrap">
        <div className="rv">
          <span className="kick">Your NeedBridge space</span>
          <h2>{data.role === 'admin' ? 'Platform' : 'Your'} <em>dashboard</em></h2>
          <p className="sub">{data.role === 'org_member' ? `${data.organisation?.name || 'Your institution'} · ${data.organisation?.verification_status?.replaceAll('_', ' ') || ''}` : data.role === 'donor' ? 'A clear view of the resources you are sharing and the connections you are making.' : 'A quick overview of institution verification and platform trust.'}</p>
        </div>
        <div className="grid dashboard-grid">
          {stats.map(([key, value]) => (
            <article className="card dashboard-stat" key={key}>
              <span className="kick">{labels[key] || key.replaceAll('_', ' ')}</span>
              <strong>{Number(value).toLocaleString('en-IN')}</strong>
            </article>
          ))}
        </div>
        <p className="dn" style={{ marginTop: '1rem' }}>You have {data.metrics?.unread_notifications || 0} unread notification(s).</p>
      </div>
    </section>
  )
}
