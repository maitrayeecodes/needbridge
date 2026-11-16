// Lets any component scroll smoothly to a section by its id
let lenis = null
export const setLenis = (l) => { lenis = l }

export function goTo(id) {
  const el = document.getElementById(id)
  if (!el) return
  if (lenis) lenis.scrollTo(el, { offset: -72 })
  else el.scrollIntoView({ behavior: 'smooth' })
}