// NeedBridge API client. New product workflows use the PostgreSQL-backed /api/v2 routes.
async function read(res) {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((body.errors || ['Something went wrong. Please try again.']).join(' '))
  return body
}

const send = (url, data) => fetch(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
}).then(read)

export const getCategories = () => fetch('/api/v2/categories').then(read)
let categoryCache
async function categoryId(slug) {
  categoryCache ||= getCategories()
  const categories = await categoryCache
  const match = categories.find((c) => c.slug === slug)
  if (!match) throw new Error('Please choose a valid resource category.')
  return match.id
}

export const getNeeds = (area, category) => {
  const params = new URLSearchParams({ near_area: area, ...(category && { category_slug: category }) })
  return fetch('/api/v2/requirements?' + params).then(read)
}
export const getMatches = () => fetch('/api/v2/matches').then(read)
export const createOffer = (d) => send('/api/v2/offers', d)
export const getOffers = () => fetch('/api/v2/offers').then(read)
export const respondOffer = (id, action) => send(`/api/v2/offers/${id}/respond`, { action })
export const scheduleHandover = (id, scheduledAt) => send(`/api/v2/handovers/${id}/schedule`, { scheduled_at: scheduledAt })
export const confirmHandover = (id, quantity) => send(`/api/v2/handovers/${id}/confirm`, { quantity_received: Number(quantity) })
export const cancelHandover = (id) => send(`/api/v2/handovers/${id}/cancel`, {})
export const postDonation = async (d) => send('/api/v2/donations', {
  title: d.item, description: d.description, category_id: await categoryId(d.category),
  quantity_total: Number(d.quantity), condition: d.condition,
  age_min: d.age_min === '' ? null : Number(d.age_min),
  age_max: d.age_max === '' ? null : Number(d.age_max), area: d.area,
})
export const postRequest = async (d) => send('/api/v2/requirements', {
  title: d.item, description: d.description, category_id: await categoryId(d.category),
  quantity_requested: Number(d.quantity_needed),
  age_min: d.age_min === '' ? null : Number(d.age_min),
  age_max: d.age_max === '' ? null : Number(d.age_max), area: d.area,
})
export const uploadDonationPhoto = (donationId, file) => {
  const data = new FormData()
  data.append('file', file)
  return fetch(`/api/v2/donations/${donationId}/photos`, { method: 'POST', body: data }).then(read)
}

// Accounts use a secure session cookie. Organisation members are verified separately.
export const getMe = () => fetch('/api/v2/auth/me').then(read)
export const getDashboard = () => fetch('/api/v2/dashboard').then(read)
export const getNotifications = () => fetch('/api/v2/notifications').then(read)
export const markNotificationRead = (id) => send(`/api/v2/notifications/${id}/read`, {})
export const markAllNotificationsRead = () => send('/api/v2/notifications/read-all', {})
export const signup = (d) => send('/api/v2/auth/signup', {
  ...d, role: d.role === 'org' ? 'org_member' : d.role,
})
export const login = (d) => send('/api/v2/auth/login', d)
export const logout = () => send('/api/v2/auth/logout', {})

// Institution verification and administration.
export const uploadVerificationDocument = (organisationId, file, documentType) => {
  const data = new FormData()
  data.append('file', file)
  data.append('document_type', documentType)
  return fetch(`/api/v2/organisations/${organisationId}/verification-documents`, { method: 'POST', body: data }).then(read)
}
export const getPending = () => fetch('/api/v2/admin/organisations').then(read)
export const reviewOrganisation = (id, action, note = '') => send(`/api/v2/admin/organisations/${id}`, { action, note })
export const reviewDocument = (id, action, note = '') => send(`/api/v2/admin/verification-documents/${id}`, { action, note })

// Manage only listings owned by the signed-in donor or institution.
export const getMyListings = () => fetch('/api/v2/my-listings').then(read)
export const updateListing = (kind, id, data) => fetch(`/api/v2/listings/${kind}/${id}`, {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
}).then(read)
export const changeListingStatus = (kind, id, action) => send(`/api/v2/listings/${kind}/${id}/status`, { action })

// Community trust and safety.
export const submitReport = (target_type, target_id, reason, details = '') => send('/api/v2/reports', { target_type, target_id, reason, details })
export const getReports = () => fetch('/api/v2/admin/reports').then(read)
export const reviewReport = (id, action, note = '') => send(`/api/v2/admin/reports/${id}`, { action, note })
export const getListingActivity = (kind, id) => fetch(`/api/v2/listings/${kind}/${id}/activity`).then(read)

// Profiles and private contact coordination.
export const getProfile = () => fetch('/api/v2/profile').then(read)
export const updateProfile = (data) => fetch('/api/v2/profile', {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
}).then(read)
export const getOfferContacts = (id) => fetch(`/api/v2/offers/${id}/contacts`).then(read)
export const getAdminAccounts = () => fetch('/api/v2/admin/accounts').then(read)
export const setAccountActive = (id, active) => send(`/api/v2/admin/accounts/${id}/status`, { active })
