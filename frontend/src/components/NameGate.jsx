import { useState } from 'react'
import { resolveUserByName } from '../api'

// Name-login gate. The user must resolve to a known user before chat is usable.
// Only a resolved known user (from GET /api/users/resolve) ever becomes active;
// a typed name is never sent as an identity into chat/upload/image requests.
function NameGate({ onResolved }) {
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    if (submitting) return

    const trimmed = name.trim()
    if (!trimmed) {
      setError('Please enter your name.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const result = await resolveUserByName(trimmed)
      if (result.ok && result.user) {
        onResolved(result.user)
        return
      }
      if (result.status === 404) {
        setError('User not recognized. Check the name and try again.')
      } else if (result.status === 422) {
        setError('Please enter your name.')
      } else if (result.status === 401) {
        setError('API secret required or invalid.')
      } else {
        setError(`Could not sign in (error ${result.status}).`)
      }
    } catch {
      setError('Could not reach the server. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="name-gate">
      <form className="name-gate-card" onSubmit={handleSubmit}>
        <h1 className="name-gate-title">Project Anam</h1>
        <p className="name-gate-prompt">Who&apos;s chatting?</p>
        <input
          className="name-gate-input"
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Your name"
          autoFocus
          aria-label="Your name"
        />
        <button className="btn name-gate-submit" type="submit" disabled={submitting}>
          {submitting ? 'Checking...' : 'Continue'}
        </button>
        {error && <p className="name-gate-error" role="alert">{error}</p>}
      </form>
    </div>
  )
}

export default NameGate
