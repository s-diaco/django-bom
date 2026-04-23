import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'

interface LocationState {
  from?: {
    pathname?: string
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const locationState = location.state as LocationState | null
  const redirectPath = locationState?.from?.pathname || '/'

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')
    setSubmitting(true)

    try {
      await login(username, password)
      navigate(redirectPath, { replace: true })
    } catch {
      setErrorMessage('Login failed. Verify username/password and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="shell auth-shell">
      <section className="panel login-panel">
        <p className="eyebrow">django-bom</p>
        <h1>Sign In</h1>
        <p className="muted">Use your existing Django user account. Session starts with JWT.</p>

        <form onSubmit={onSubmit} className="form-grid">
          <label>
            Username
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {errorMessage && <p className="error">{errorMessage}</p>}

          <button disabled={submitting} type="submit">
            {submitting ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </section>
    </main>
  )
}