import { useState } from 'react'
import { errorText, post, setToken } from '../api/client'
import type { LoginResult, SessionUser } from '../api/types'
import { ErrorNote, ListenButton } from '../components/ui'
import { Icon } from '../lib/icons'

// Demo personas (all mock). Only in builds made with VITE_SHOW_DEMO_ACCOUNTS=true.
// One tap signs in with VITE_DEMO_PIN (the public demo PIN) when it is set at build time.
// Officer and admin have their own PINs that are never in the bundle: their buttons only
// fill in the phone number.
const SHOW_DEMO = import.meta.env.VITE_SHOW_DEMO_ACCOUNTS === 'true'
const DEMO_PIN: string = import.meta.env.VITE_DEMO_PIN ?? ''
const DEMO_USERS = [
  { phone: '00000000001', label: 'Zainab', role: 'Widow', icon: 'widow', privileged: false },
  { phone: '00000000002', label: 'Rukhsana', role: 'Competing claim', icon: 'people', privileged: false },
  { phone: '00000000010', label: 'Ayesha', role: 'Helper', icon: 'helper', privileged: false },
  { phone: '00000000020', label: 'Kamran', role: 'Officer', icon: 'person', privileged: true },
  { phone: '00000000030', label: 'Admin', role: 'Rules + console', icon: 'rules', privileged: true },
  { phone: '00000000040', label: 'Auditor', role: 'Read-only log', icon: 'eye', privileged: false },
]
const DEMO_KEY = 'sahara.demoOpen'
const WELCOME_UR = 'سہارا میں خوش آمدید۔ اپنا فون نمبر اور پن لکھیں۔'

function readDemoOpen(): boolean {
  try {
    return sessionStorage.getItem(DEMO_KEY) === '1'
  } catch {
    return false
  }
}

interface LoginProps {
  onLogin: (user: SessionUser) => void
}

export function Login({ onLogin }: LoginProps) {
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [demoOpen, setDemoOpen] = useState(readDemoOpen)

  function toggleDemo(): void {
    const next = !demoOpen
    setDemoOpen(next)
    try {
      sessionStorage.setItem(DEMO_KEY, next ? '1' : '0')
    } catch {
      // storage blocked: the toggle still works for this page view
    }
  }

  function pickDemo(demoPhone: string, privileged: boolean): void {
    if (!privileged && DEMO_PIN) {
      void signIn(demoPhone, DEMO_PIN)
      return
    }
    setPhone(demoPhone)
    setPin('')
  }

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
    <main className="login">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-head">
          <div>
            <h1 id="login-title" className="login-mark">
              <span lang="ur" dir="rtl">سہارا</span>
              <span className="login-mark-en">Sahara</span>
            </h1>
            <p className="login-sub">
              <span lang="ur" dir="rtl">پنشن کا دعویٰ، آسان طریقے سے</span>
              <span className="bi-en">Survivor pension claims, step by step</span>
            </p>
          </div>
          <ListenButton audioKey="prompt_welcome" text={WELCOME_UR} />
        </div>

        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault()
            void signIn(phone, pin)
          }}
        >
          <label className="field">
            <span className="field-label">
              <Icon name="phone" size={22} />
              <span lang="ur" dir="rtl">فون نمبر</span>
              <span className="bi-en">Phone number</span>
            </span>
            <input
              className="input input-big"
              inputMode="numeric"
              autoComplete="tel"
              placeholder="03XX XXXXXXX"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, ''))}
              required
            />
          </label>
          <label className="field">
            <span className="field-label">
              <Icon name="lock" size={22} />
              <span lang="ur" dir="rtl">پن</span>
              <span className="bi-en">4-digit PIN</span>
            </span>
            <input
              className="input input-big input-pin"
              inputMode="numeric"
              type="password"
              autoComplete="off"
              maxLength={8}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/[^\d]/g, ''))}
              required
            />
          </label>
          <ErrorNote message={error} />
          <button className="btn btn-primary btn-block btn-big" type="submit" disabled={busy}>
            <span lang="ur" dir="rtl">داخل ہوں</span>
            <span>{busy ? 'Signing in…' : 'Sign in'}</span>
          </button>
        </form>

        {SHOW_DEMO && (
          <div className="demo">
            <button type="button" className="demo-toggle" aria-expanded={demoOpen} aria-controls="demo-list" onClick={toggleDemo}>
              <Icon name={demoOpen ? 'close' : 'people'} size={18} />
              {demoOpen ? 'Hide demo accounts' : 'Demo accounts (mock)'}
            </button>
            {demoOpen && (
              <div id="demo-list" className="demo-panel">
                <p className="demo-hint">
                  Mock personas for judges and testing. Officer and admin fill in the phone only: type their PIN yourself.
                </p>
                <div className="demo-grid">
                  {DEMO_USERS.map((u) => (
                    <button key={u.phone} className="demo-persona" type="button" disabled={busy} onClick={() => pickDemo(u.phone, u.privileged)}>
                      <Icon name={u.icon} size={26} />
                      <span className="demo-name">{u.label}</span>
                      <span className="demo-role">{u.role}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  )
}
