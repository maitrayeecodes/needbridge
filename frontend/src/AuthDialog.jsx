import { useEffect, useRef, useState } from 'react'
import { AREAS } from './data'
import { login, signup } from './api'

// config = null (closed) or { mode: 'login' | 'signup', role: 'donor' | 'org' }
export default function AuthDialog({ config, onClose, onDone }) {
  const ref = useRef(null)
  const [mode, setMode] = useState('signup')
  const [f, setF] = useState({ role: 'donor', name: '', organisation_name: '', organisation_type: 'school', email: '', password: '', area: 'Cidco' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'

  useEffect(() => {
    const d = ref.current
    if (config && !d.open) {
      setMode(config.mode)
      setF((x) => ({ ...x, role: config.role || 'donor', password: '' }))
      setError('')
      d.showModal()
    }
    if (!config && d.open) d.close()
  }, [config])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const user = isSignup ? await signup(f) : await login({ email: f.email, password: f.password })
      onDone(user)
    } catch (x) {
      setError(x.message === 'Failed to fetch' ? 'Can’t reach the server. Is uvicorn running?' : x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="au-title">
      <form onSubmit={submit} noValidate>
        <h3 id="au-title">{isSignup ? 'Create your account' : 'Welcome back'}</h3>
        <p className="dn">{isSignup ? 'It takes a minute. Children never need accounts.' : 'Log in to offer items or post needs.'}</p>

        {isSignup && (
          <div className="seg" role="group" aria-label="I am">
            <button type="button" aria-pressed={f.role === 'donor'} onClick={() => setF({ ...f, role: 'donor' })}>I want to give</button>
            <button type="button" aria-pressed={f.role === 'org'} onClick={() => setF({ ...f, role: 'org' })}>School or NGO</button>
          </div>
        )}
        {isSignup && (
          <label className="f">Your full name
            <input value={f.name} onChange={set('name')} maxLength={100} autoComplete="name" />
          </label>
        )}
        {isSignup && f.role === 'org' && (
          <>
            <label className="f">School or organisation name
              <input value={f.organisation_name} onChange={set('organisation_name')} maxLength={160} placeholder="e.g. Asha School" />
            </label>
            <label className="f">Organisation type
              <select value={f.organisation_type} onChange={set('organisation_type')}>
                <option value="school">School</option><option value="ngo">NGO</option>
                <option value="community_group">Community group</option><option value="other">Other</option>
              </select>
            </label>
          </>
        )}
        <label className="f">Email<input type="email" value={f.email} onChange={set('email')} autoComplete="email" /></label>
        <label className="f">Password{isSignup ? ' (at least 8 characters)' : ''}
          <input type="password" value={f.password} onChange={set('password')} autoComplete={isSignup ? 'new-password' : 'current-password'} />
        </label>
        {isSignup && (
          <label className="f">Your area
            <select value={f.area} onChange={set('area')}>{AREAS.map((a) => <option key={a}>{a}</option>)}</select>
          </label>
        )}

        <p className="err" role="alert">{error}</p>
        <div className="dr">
          <button className="btn o" type="button" onClick={onClose}>Cancel</button>
          <button className="btn p" type="submit" disabled={busy}>{busy ? 'Please wait…' : isSignup ? 'Create account' : 'Log in'}</button>
        </div>
        <p className="dn" style={{ marginTop: '1rem' }}>
          {isSignup ? 'Already have an account? ' : 'New here? '}
          <button type="button" className="sw" onClick={() => { setMode(isSignup ? 'login' : 'signup'); setError('') }}>
            {isSignup ? 'Log in' : 'Create an account'}
          </button>
        </p>
      </form>
    </dialog>
  )
}