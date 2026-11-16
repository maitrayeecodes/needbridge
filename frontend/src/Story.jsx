import { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { goTo } from './scroll'
import rich from './assets/rich_house.jpg'
import poor from './assets/community_school.jpg'
import roomRich from './assets/rich_kid_room.webp'
import roomPoor from './assets/classroom_interior.jpg'
import boy from './assets/boy.png'
import classmates from './assets/classroom_students.webp'

gsap.registerPlugin(ScrollTrigger)

export default function Story() {
  const root = useRef(null)

  useLayoutEffect(() => {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const $ = (s) => root.current.querySelector(s)

    // Camera framing keeps the donor home and recipient school centred consistently.
    const focus = (sel) => {
      const e = $(sel), W = innerWidth, H = innerHeight
      const scale = reduce ? 1 : Math.min(W / e.offsetWidth, H / e.offsetHeight) * 1.05
      return {
        scale,
        x: W / 2 - (e.offsetLeft + e.offsetWidth / 2) * scale,
        y: H / 2 - (e.offsetTop + e.offsetHeight / 2) * scale,
      }
    }

    // The dotted bridge from the first house to the second, redrawn when the window changes size
    const drawArc = () => {
      const a = $('#rich'), b = $('#poor')
      $('#svg').setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`)
      $('#arc').setAttribute('d',
        `M${a.offsetLeft + a.offsetWidth / 2} ${a.offsetTop - 40} Q${innerWidth / 2} ${innerHeight * 0.1} ${b.offsetLeft + b.offsetWidth / 2} ${b.offsetTop - 40}`)
    }
    drawArc()
    ScrollTrigger.addEventListener('refreshInit', drawArc)

    const ctx = gsap.context(() => {
      const world = $('#world'), arc = $('#arc'), t = { p: 0 }
      gsap.set(world, { transformOrigin: '0 0', filter: 'blur(0px)' })
      gsap.set('.cap, .room, .bubble, #gift, #veil, #slogan, #arc', { opacity: 0 })
      gsap.set('#scroll-cue', { opacity: 1, y: 0 })
      gsap.set('#slogan', { scale: 0.92 })

      const tl = gsap.timeline({
        defaults: { ease: 'none' },
        scrollTrigger: {
          trigger: root.current, start: 'top top', end: () => '+=' + innerHeight * 11,
          pin: true, scrub: 0.6, anticipatePin: 1, invalidateOnRefresh: true,
          onUpdate: (s) => { $('#bar').style.width = s.progress * 100 + '%' },
        },
      })

      tl.to('#c1', { opacity: 1, duration: 0.4 }, 0.1).to('#c1', { opacity: 0, duration: 0.3 }, 1.2)
        .to('#scroll-cue', { opacity: 0, y: 18, duration: 0.45 }, 0.75)
        // 1. zoom into the first house, then into the pink room
        .to(world, { x: () => focus('#rich').x, y: () => focus('#rich').y, scale: () => focus('#rich').scale, duration: 1.6, ease: 'power2.inOut' }, 1)
        .fromTo('#r1', { opacity: 0, scale: 1.15 }, { opacity: 1, scale: 1, duration: 0.7 }, 2.5)
        .fromTo('#boy', { y: 60, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7 }, 3)
        .to('#b1', { opacity: 1, y: 0, duration: 0.5 }, 3.8)
        .to('#boy', { y: -8, duration: 0.6, yoyo: true, repeat: 1 }, 4.2)
        // 2. back out, the gift crosses the bridge
        .to('#r1', { opacity: 0, duration: 0.6 }, 5.4)
        .to('#c2', { opacity: 1, duration: 0.4 }, 5.2).to('#c2', { opacity: 0, duration: 0.3 }, 6)
        .to(world, { x: 0, y: 0, scale: 1, duration: 1.4, ease: 'power2.inOut' }, 5.6)
        .to(arc, { opacity: 1, duration: 0.3 }, 6.9).to('#gift', { opacity: 1, duration: 0.2 }, 7)
        .to('#c3', { opacity: 1, duration: 0.4 }, 7).to('#c3', { opacity: 0, duration: 0.3 }, 8.4)
        .to(t, { p: 1, duration: 1.4, ease: 'power1.inOut', onUpdate: () => {
          const q = arc.getPointAtLength(arc.getTotalLength() * t.p)
          gsap.set('#gift', { x: q.x, y: q.y })
        } }, 7)
        .to('#gift', { opacity: 0, duration: 0.2 }, 8.4)
        // 3. zoom into the recipient school, then travel inside a classroom
        .to(world, { x: () => focus('#poor').x, y: () => focus('#poor').y, scale: () => focus('#poor').scale, duration: 1.4, ease: 'power2.inOut' }, 8.3)
        .to('#c4', { opacity: 1, duration: 0.4 }, 8.4).to('#c4', { opacity: 0, duration: 0.3 }, 9.4)
        .fromTo('#r2', { opacity: 0 }, { opacity: 1, duration: 0.45 }, 9.7)
        .fromTo('#r2 .bg', { scale: 1.2 }, { scale: 1, duration: 1.15, ease: 'power2.out' }, 9.65)
        .fromTo('#classmates', { y: 46, opacity: 0, scale: 0.94 }, { y: 0, opacity: 1, scale: 1, duration: 0.8, ease: 'back.out(1.2)' }, 10.05)
        .to('#b2', { opacity: 1, y: 0, duration: 0.45 }, 10.85)
        // 4. zoom out, both houses blurred, the slogan appears
        .to('#r2', { opacity: 0, duration: 0.8 }, 12.2)
        .to(world, { x: 0, y: 0, scale: 1, duration: 1.6, ease: 'power2.inOut' }, 12.2)
        .to(world, { filter: 'blur(6px)', duration: 1 }, 13.4)
        .to('#veil', { opacity: 1, duration: 1 }, 13.4)
        .to('#slogan', { opacity: 1, scale: 1, duration: 0.8 }, 14)
        .to({}, { duration: 1.4 }, 14.8)
    }, root)

    return () => {
      ScrollTrigger.removeEventListener('refreshInit', drawArc)
      ctx.revert()
    }
  }, [])

  return (
    <>
      <div className="band" id="story">
        <h2>Follow a useful item <em>to someone who needs it</em></h2>
        <p>From homes to schools and community organisations, see how one useful item finds a new purpose.</p>
      </div>
      <section className="stage" ref={root} aria-label="Story: a family shares useful school supplies with a nearby school community">
        <div className="bar" id="bar" />
        <a className="skip" href="#needs" onClick={(e) => { e.preventDefault(); goTo('needs') }}>Skip story</a>
        <div className="scroll-cue" id="scroll-cue" aria-label="Scroll down to experience the animated story">
          <span className="scroll-cue-mouse" aria-hidden="true"><i /></span>
          <span className="scroll-cue-copy"><b>Keep scrolling</b><small>to bring the story to life</small></span>
          <span className="scroll-cue-arrows" aria-hidden="true"><i>⌄</i><i>⌄</i></span>
        </div>

        <div className="world" id="world">
          <div className="divider" />
          <img className="house rich" id="rich" alt="A family home where useful items are ready to be shared" src={rich} />
          <img className="house poor" id="poor" alt="A nearby government school where students can receive useful donations" src={poor} />
          <svg className="bridge" id="svg" aria-hidden="true">
            <path id="arc" fill="none" stroke="#e0b866" strokeWidth="5" strokeLinecap="round" strokeDasharray="2 14" />
            <g id="gift" opacity="0">
              <rect x="-16" y="-14" width="32" height="28" rx="4" fill="#c4923a" />
              <rect x="-3" y="-14" width="6" height="28" fill="#f7f3ee" />
              <rect x="-16" y="-3" width="32" height="6" fill="#f7f3ee" />
            </g>
          </svg>
        </div>

        <div className="room" id="r1">
          <img className="bg" alt="A bright pink child's bedroom" src={roomRich} />
          <img className="kid" id="boy" alt="A boy kneeling beside a box of toys" src={boy} />
          <p className="bubble" id="b1">These things are still useful. I hope they reach students who need them.</p>
        </div>
        <div className="room" id="r2">
          <img className="bg" alt="Inside a bright classroom with a chalkboard and learning materials" src={roomPoor} />
          <img className="kid classmates" id="classmates" alt="Two schoolchildren sitting together with books" src={classmates} />
          <p className="bubble" id="b2">These will help us learn!</p>
        </div>

        <div className="veil" id="veil" />
        <div className="slogan" id="slogan"><p><span>Give.</span> <span>Connect.</span> <span>Smile.</span></p><small>That is NeedBridge.</small></div>
        <p className="cap" id="c1">A family has useful things to share.</p>
        <p className="cap" id="c2">Books, bags, toys and stationery are ready to share.</p>
        <p className="cap" id="c3">NeedBridge connects donors with nearby schools and NGOs.</p>
        <p className="cap" id="c4">Every useful item can make a difference.</p>
      </section>
    </>
  )
}