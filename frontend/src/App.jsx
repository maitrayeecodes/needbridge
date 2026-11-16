import { useEffect, useState } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import { CATS, ICONS } from './data'
import { goTo, setLenis } from './scroll'
import Icon from './Icon'
import Story from './Story'
import HowItWorks from './HowItWorks'
import Needs from './Needs'
import Matches from './Matches'
import FormDialog from './FormDialog'
import AuthDialog from './AuthDialog'
import Admin from './Admin'
import VerificationPanel from './VerificationPanel'
import ActivityPanel from './ActivityPanel'
import DashboardPanel from './DashboardPanel'
import NotificationPanel from './NotificationPanel'
import ListingManager from './ListingManager'
import ProfilePanel from './ProfilePanel'
import { getMe, logout } from './api'
import rich from './assets/rich_house.jpg'
import poor from './assets/poor_house.jpeg'
import boy from './assets/boy.png'
import girl from './assets/girl.png'

gsap.registerPlugin(ScrollTrigger)

function Logo() {
  return (
    <svg className="mk" width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">
      <rect className="mk-r" width="36" height="36" rx="10" />
      <path className="mk-h" transform="translate(9.5 7) scale(.7)" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
      <path d="M8 28.5h20" stroke="#c4923a" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

export default function App() {
  const [cat, setCat] = useState('')
  const [form, setForm] = useState({ mode: null, need: null })
  const [version, setVersion] = useState(0)
  const [menu, setMenu] = useState(false)
  const [user, setUser] = useState(null)
  const [auth, setAuth] = useState(null)
  const [pending, setPending] = useState(null)
  const [notice, setNotice] = useState('')

  // Who is logged in? The server remembers us with a cookie.
  useEffect(() => { getMe().then(setUser).catch(() => setUser(null)) }, [])
  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(''), 7000)
    return () => clearTimeout(t)
  }, [notice])

  // Smooth scrolling
  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const lenis = new Lenis({ duration: 1.2 })
    setLenis(lenis)
    lenis.on('scroll', ScrollTrigger.update)
    const tick = (t) => lenis.raf(t * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)
    return () => { gsap.ticker.remove(tick); lenis.destroy(); setLenis(null) }
  }, [])

  // Gentle fade-in for section headings
  useEffect(() => {
    document.documentElement.classList.add('js')
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target) }
    }), { threshold: 0.15 })
    document.querySelectorAll('.rv').forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  const nav = (id) => (e) => { e.preventDefault(); setMenu(false); goTo(id) }
  // Open the offer/need form for a logged-in person with the right role, otherwise ask them to log in first
  const launch = (u, mode, need) => {
    const want = mode === 'offer' ? 'donor' : 'org_member'
    if (u.role === want) {
      if (mode === 'need' && u.organisation?.verification_status !== 'verified') {
        setNotice('Your institution must complete verification before posting needs. Upload an official document in the verification section below.')
        return
      }
      return setForm({ mode, need })
    }
    setNotice(u.role === 'donor'
      ? 'You are signed in as a donor. Log out and sign up as a school or NGO to post needs.'
      : u.role === 'org_member'
        ? 'You are signed in as a school or NGO. Log out and sign up as a donor to offer items.'
        : 'Admin accounts review requests and cannot post here.')
  }
  const open = (mode, need = null) => {
    if (user) return launch(user, mode, need)
    setPending({ mode, need })
    setAuth({ mode: 'signup', role: mode === 'offer' ? 'donor' : 'org' })
  }
  const signedIn = (u) => {
    setUser(u); setAuth(null)
    if (pending) { const p = pending; setPending(null); launch(u, p.mode, p.need) }
  }
  const doLogout = () => { logout().finally(() => { setUser(null); setNotice('You are logged out.') }); setMenu(false) }
  const close = () => setForm({ mode: null, need: null })
  const toggleTheme = () => {
    const d = document.documentElement
    const dark = d.dataset.theme ? d.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
    d.dataset.theme = dark ? 'light' : 'dark'
  }

  return (
    <>
      <header>
        <div className="wrap">
          <a className="logo" href="#top" onClick={nav('top')} aria-label="NeedBridge home"><Logo /><i>need</i>bridge</a>
          <nav className={menu ? 'open' : ''} aria-label="Main">
            <a href="#top" className="on" onClick={nav('top')}>Home</a>
            <a href="#story" onClick={nav('story')}>Our story</a>
            <a href="#how" onClick={nav('how')}>How it works</a>
            <a href="#needs" onClick={nav('needs')}>Browse needs</a>
            <a href="#trust" onClick={nav('trust')}>Trust</a>
            <button className="nlog" type="button" onClick={() => { setMenu(false); user ? doLogout() : setAuth({ mode: 'login' }) }}>{user ? `Log out (${user.name})` : 'Log in'}</button>
          </nav>
          <div className="hr">
            <button className="ic" type="button" onClick={toggleTheme} aria-label="Switch light or dark theme">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 14A8 8 0 1110 4a6 6 0 0010 10z" /></svg>
            </button>
            {user && <span className="who">{user.name}<small>{user.role === 'org_member' ? 'School or NGO' : user.role}</small></span>}
            {user
              ? <button className="btn o lg" type="button" onClick={doLogout}>Log out</button>
              : <button className="btn o lg" type="button" onClick={() => setAuth({ mode: 'login' })}>Log in</button>}
            {!user && <button className="btn o lg" type="button" onClick={() => open('need')}>Post a need</button>}
            <button className="btn p" type="button" onClick={() => open(user?.role === 'org_member' ? 'need' : 'offer')}>
              {user?.role === 'org_member' ? 'Post a need' : 'Offer an item'}
            </button>
            <button className="ic menu" type="button" onClick={() => setMenu(!menu)} aria-label="Open menu" aria-expanded={menu}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
            </button>
          </div>
        </div>
      </header>
      {notice && <div className="notice" role="status">{notice}</div>}

      <main id="top">
        <section className="hero">
          <div className="wrap">
            <div>
              <span className="pill">Free for donors · Verified organisations</span>
              <h1>Give what you’ve outgrown. <em>Reach a child who needs it.</em></h1>
              <p className="lead">NeedBridge connects useful things sitting unused at home with verified schools and NGOs that need them — from books and toys to clothing, footwear and everyday essentials.</p>
              <p className="mic">Somewhere nearby, a child is wishing for exactly what is gathering dust at home.</p>
              <div className="cta">
                <button className="btn p big" type="button" onClick={() => open('offer')}>Offer an item</button>
                <a className="btn o big" href="#story" onClick={nav('story')}>See the story</a>
              </div>
            </div>
            <div className="art" role="img" aria-label="A boy packing a box of toys and a girl smiling with hers, joined by a bridge of giving">
              <img className="bg l" src={rich} alt="" />
              <img className="bg r" src={poor} alt="" />
              <svg viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true">
                <path d="M20 78Q150 -40 280 78" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeDasharray="3 8" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
              </svg>
              <div className="pin a">You have something useful</div>
              <div className="pin b">Someone nearby needs it</div>
              <img className="kid k1" src={boy} alt="" />
              <img className="kid k2" src={girl} alt="" />
            </div>
          </div>
          <div className="wrap">
            <div className="cats" role="group" aria-label="Browse by category">
              {CATS.map((c) => (
                <button key={c[0]} type="button" onClick={() => { setCat(c[0]); goTo('needs') }}><Icon d={c[2]} />{c[1]}</button>
              ))}
            </div>
            <div className="trio">
              <div><i><Icon d={ICONS.shield} /></i><p style={{ margin: 0 }}><b>Verified organisations</b><span>Checked before a need goes live.</span></p></div>
              <div><i><Icon d={ICONS.pin} /></i><p style={{ margin: 0 }}><b>Matched near you</b><span>Needs sorted by your area.</span></p></div>
              <div><i><Icon d={ICONS.check} /></i><p style={{ margin: 0 }}><b>Confirmed handovers</b><span>Both sides confirm the receipt.</span></p></div>
            </div>
          </div>
        </section>

        <Story />
        <HowItWorks />

        {user?.role === 'org_member' && user.organisation?.verification_status !== 'verified' && (
          <VerificationPanel user={user} onUploaded={() => getMe().then(setUser).catch(() => {})} />
        )}
        {user && <DashboardPanel user={user} version={version} />}
        {user && user.role !== 'admin' && <ProfilePanel user={user} onUpdated={() => getMe().then(setUser).catch(() => {})} />}
        {user && user.role !== 'admin' && <ListingManager user={user} version={version} onChange={() => setVersion((v) => v + 1)} />}
        {user && user.role !== 'admin' && <NotificationPanel user={user} version={version} onChange={() => setVersion((v) => v + 1)} />}
        {user && user.role !== 'admin' && <ActivityPanel user={user} version={version} onChange={() => setVersion((v) => v + 1)} />}
        {user?.role === 'admin' && <Admin onChange={() => setVersion((v) => v + 1)} />}


        <section className="blk category-discovery" id="explore">
          <div className="wrap">
            <div className="rv category-heading">
              <span className="kick">A second life starts here</span>
              <h2>What can you <em>pass forward?</em></h2>
              <p className="sub">Not just school supplies. Everyday things in good, usable condition can make a meaningful difference to a nearby community.</p>
            </div>
            <div className="category-grid">
              {CATS.map((c, i) => (
                <button className={`category-tile tile-${i % 6}`} key={c[0]} type="button"
                  onClick={() => { setCat(c[0]); goTo('needs') }}>
                  <span className="category-icon"><Icon d={c[2]} /></span>
                  <span className="category-name">{c[1]}</span>
                  <span className="category-action">Explore needs <b aria-hidden="true">↗</b></span>
                </button>
              ))}
              <button className="category-tile tile-more" type="button" onClick={() => { setCat(''); goTo('needs') }}>
                <span className="category-icon"><span className="more-dots">•••</span></span>
                <span className="category-name">And more useful things</span>
                <span className="category-action">See everything <b aria-hidden="true">↗</b></span>
              </button>
            </div>
            <div className="explore-note">
              <span aria-hidden="true">✳</span>
              <p><b>One simple idea:</b> if it is clean, safe and still useful, it may be exactly what someone nearby needs.</p>
              <button className="btn p" type="button" onClick={() => goTo('needs')}>Explore community needs</button>
            </div>
          </div>
        </section>


        

      

        <Needs cat={cat} setCat={setCat} onOffer={(n) => open('offer', n)} version={version} user={user} />
        {user && user.role !== 'admin' && <Matches version={version} user={user} onChange={() => setVersion((v) => v + 1)} />}

        <section className="blk" id="trust">
          <div className="wrap">
            <div className="rv"><span className="kick">Safety first</span><h2>Built on <em>trust</em>, for everyone</h2><p className="sub">Clear checks, privacy by default and handovers that are confirmed, not assumed.</p></div>
            <div className="tgrid">
              <div className="card"><h3>For donors</h3><ul><li>Organisations are reviewed before posting needs.</li><li>You see the real need before you give.</li><li>You can report a problem at any step.</li></ul></div>
              <div className="card"><h3>For schools and NGOs</h3><ul><li>Post exactly what your children need.</li><li>Accept or decline offers with a reason.</li><li>Keep a record of every item received.</li></ul></div>
              <div className="card"><h3>For children and families</h3><ul><li>Children never create accounts.</li><li>Requests are managed by the organisation.</li><li>No exact home addresses are shown publicly.</li></ul></div>
            </div>
          </div>
        </section>

        <section className="band" id="join" style={{ paddingBottom: '4rem' }}>
          <h2>You have something useful. <em>Someone needs it.</em></h2>
          <p>Choose how you want to join NeedBridge.</p>
          <div className="join">
            <button type="button" onClick={() => open('offer')}><b>I want to give</b><span>List items you no longer use.</span></button>
            <button type="button" onClick={() => open('need')}><b>I represent a school or NGO</b><span>Post what your children need.</span></button>
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap">
          <div><a className="logo" href="#top" onClick={nav('top')}><Logo /><i>need</i>bridge</a><p>Connecting what’s extra with what’s essential.</p></div>
          <div>
            <a href="#story" onClick={nav('story')}>Our story</a><br />
            <a href="#how" onClick={nav('how')}>How it works</a><br />
            <a href="#needs" onClick={nav('needs')}>Browse needs</a>
          </div>
        </div>
      </footer>

      <FormDialog mode={form.mode} need={form.need} user={user} onClose={close} onSaved={() => setVersion((v) => v + 1)} />
      <AuthDialog config={auth} onClose={() => { setAuth(null); setPending(null) }} onDone={signedIn} />
    </>
  )
}