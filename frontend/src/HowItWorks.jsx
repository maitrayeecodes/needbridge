import { useState } from 'react'
import { HOW } from './data'
import { goTo } from './scroll'

export default function HowItWorks() {
  const [role, setRole] = useState('give')
  const [step, setStep] = useState(0)
  const steps = HOW[role]
  const c = steps[step]
  const last = step === steps.length - 1

  const pick = (r) => { setRole(r); setStep(0) }
  const next = () => (last ? goTo(role === 'give' ? 'needs' : 'join') : setStep(step + 1))
  const keys = (e) => {
    if (e.key === 'ArrowRight') next()
    if (e.key === 'ArrowLeft' && step > 0) setStep(step - 1)
  }

  return (
    <section className="blk alt" id="how">
      <div className="wrap">
        <div className="rv">
          <span className="kick">The workflow</span>
          <h2>How NeedBridge <em>works</em></h2>
          <p className="sub">Whether you are sharing something or representing an organisation, getting started is simple. Here is what happens next.</p>
        </div>
        <div className="tabs" role="tablist" aria-label="Choose your role">
          <button role="tab" aria-selected={role === 'give'} onClick={() => pick('give')}>I want to give</button>
          <button role="tab" aria-selected={role === 'org'} onClick={() => pick('org')}>I’m a school or NGO</button>
        </div>
        <div className="how">
          <ol className="hs" aria-label="Steps">
            {steps.map((s, i) => (
              <li key={s[0]}>
                <button type="button" aria-current={i === step} onClick={() => setStep(i)}>
                  <span>{i + 1}</span><b>{s[0]}</b><small>{s[1]}</small>
                </button>
              </li>
            ))}
          </ol>
          <div className="hp" tabIndex={0} onKeyDown={keys} aria-label="Step preview. Use left and right arrow keys to change step.">
            <div className="hb">
              <span>Step {step + 1} of {steps.length}</span>
              <div className="hbar"><i style={{ width: `${((step + 1) / steps.length) * 100}%` }} /></div>
            </div>
            <div aria-live="polite">
              <p className="ml">Your journey, step by step</p>
              <h3>{c[2]}</h3>
              {c[3].map((r) => <div className="mr" key={r[0]}><span>{r[0]}</span><b>{r[1]}</b></div>)}
              <p className="mn">{c[4]}</p>
            </div>
            <div className="hnav">
              <button className="btn o" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
              <button className="btn p" onClick={next}>
                {last ? (role === 'give' ? 'Browse needs' : 'Post your needs') : 'Next step'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}