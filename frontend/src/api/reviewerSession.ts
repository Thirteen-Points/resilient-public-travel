// Controlled local-demo credential. Never persisted, bundled, or put in a URL.
let credential = ''
let revision = 0
const listeners = new Set<() => void>()
export const getReviewToken = () => credential
export const reviewerRevision = () => revision
export function setReviewToken(value: string) {
  credential = value.trim()
  revision++
  listeners.forEach(listener => listener())
}
export function subscribeReviewer(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
