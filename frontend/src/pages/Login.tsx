import { useState } from 'react'
import { errorText, post, setToken } from '../api/client'
import type { LoginResult, SessionUser } from '../api/types'

// Demo personas (all mock). Shown only so judges can switch roles quickly.
const DEMO_USERS = [
  { phone: '00000000001', label: 'Zainab (widow)', icon: '\u{1F469}' },
  { phone: '00000000002', label: 'Rukhsana (competing claim)', icon: '\u{1F9D5}' },
  { phone: '00000000010', label: 'Ayesha (helper)', icon: '\u{1F91D}' },
  { phone: '00000000020', label: 'Kamran (officer)', icon: '\u{1F5C2}' },
  { phone: '00000000030', label: 'Admin', icon: '⚙' },
  { phone: '00000000040', label: 'Auditor', icon: '\u{1F50D}' },
]

interface LoginProps {
  onLogin: (user: SessionUser) => void
}

export function Login({ onLogin }: LoginProps) {
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function signIn(usePhone: string, usePin: string): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      const result = await post<LoginResult>('/api/v1/auth/login', { phone: usePhone, pin: usePin })
      setToken(result.data.access_token)
      onLogin(result.data.user)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="page">
      <h1>Sahara</h1>
      <p lang="ur" className="urdu">پنشن کے دعوے میں مدد</p>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault()
          void signIn(phone, pin)
        }}
      >
        <label>
          Phone <span lang="ur">فون نمبر</span>
          <input inputMode="numeric" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          PIN <span lang="ur">پن</span>
          <input inputMode="numeric" type="password" autoComplete="current-password" value={pin} onChange={(e) => setPin(e.target.value)} />
        </label>
        <button className="primary" type="submit" disabled={busy}>Sign in</button>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
      <h2>Demo users (PIN 1234)</h2>
      <div className="role-grid">
        {DEMO_USERS.map((u) => (
          <button key={u.phone} className="role-card" type="button" disabled={busy} onClick={() => void signIn(u.phone, '1234')}>
            <span className="icon" aria-hidden="true">{u.icon}</span>
            <span>{u.label}</span>
          </button>
        ))}
      </div>
    </main>
  )
}
