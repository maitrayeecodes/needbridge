import { useEffect, useMemo, useState } from 'react'
import { getNotifications, markAllNotificationsRead, markNotificationRead } from './api'

const relativeTime = (value) => {
  const date = new Date(value)
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function NotificationPanel({ user, version = 0, onChange }) {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const unread = useMemo(() => items.filter((n) => !n.read).length, [items])
  const load = () => getNotifications().then((rows) => { setItems(rows); setError('') }).catch((e) => setError(e.message))

  useEffect(() => { let live = true; getNotifications().then((rows) => { if (live) setItems(rows) }).catch((e) => { if (live) setError(e.message) }); return () => { live = false } }, [user?.id, version])

  const markOne = async (id) => {
    setBusy(true); setError('')
    try { await markNotificationRead(id); await load(); onChange?.() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const markAll = async () => {
    setBusy(true); setError('')
    try { await markAllNotificationsRead(); await load(); onChange?.() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  return (
    <section className="blk" id="notifications">
      <div className="wrap">
        <div className="rv notification-heading">
          <div><span className="kick">Stay in the loop</span><h2>Your <em>notifications</em></h2><p className="sub">Updates about offers, verification and handovers connected to your account.</p></div>
          {unread > 0 && <button className="btn o" type="button" disabled={busy} onClick={markAll}>Mark all as read ({unread})</button>}
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        {!items.length && !error && <div className="empty"><h3>You're all caught up</h3><p className="dn">New offer and handover updates will appear here.</p></div>}
        <div className="notification-list">
          {items.map((item) => (
            <article className={`notification-item${item.read ? '' : ' unread'}`} key={item.id}>
              <span className="notification-dot" aria-hidden="true" />
              <div className="notification-copy"><div className="notification-meta"><b>{item.title}</b><time dateTime={item.created_at}>{relativeTime(item.created_at)}</time></div><p>{item.body}</p></div>
              {!item.read && <button className="btn o notification-action" type="button" disabled={busy} onClick={() => markOne(item.id)}>Mark read</button>}
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
