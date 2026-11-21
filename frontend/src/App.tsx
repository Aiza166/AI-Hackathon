import { Suspense, lazy, useEffect, useState } from 'react'
import { SESSION_ENDED_EVENT, setToken, signOutOnServer } from './api/client'
import type { Role, SessionUser } from './api/types'
import { PrototypeBanner } from './components/PrototypeBanner'
import { Icon } from './lib/icons'
import { clearMe } from './lib/meCache'
import { clearOwnerData, unsentCount } from './lib/outbox'
import { CitizenHome } from './pages/CitizenHome'
import { Login } from './pages/Login'

// Staff screens load on demand so the citizen shell stays small on a cheap phone.
const OfficerHome = lazy(() => import('./pages/OfficerHome').then((m) => ({ default: m.OfficerHome })))
const AdminHome = lazy(() => import('./pages/AdminHome').then((m) => ({ default: m.AdminHome })))
const AuditorHome = lazy(() => import('./pages/AuditorHome').then((m) => ({ default: m.AuditorHome })))

const USER_KEY = 'sahara.user'

const ROLE_LABEL: Record<Role, string> = {
  citizen: 'Citizen',
  helper: 'Community helper',
  officer: 'Pension officer',
  admin: 'Administrator',
  auditor: 'Auditor',
}

function loadUser(): SessionUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as SessionUser) : null
  } catch {
    return null
  }
}

function HomeFor({ user, onSignInAgain }: { user: SessionUser; onSignInAgain: () => void }) {
  switch (user.role) {
    case 'citizen':
    case 'helper':
      return <CitizenHome user={user} onSignInAgain={onSignInAgain} />
    case 'officer':
      return <OfficerHome />
    case 'admin':
      return <AdminHome />
    case 'auditor':
      return <AuditorHome />
  }
}

function isStaff(role: Role): boolean {
  return role === 'officer' || role === 'admin' || role === 'auditor'
}

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(loadUser)

  function handleLogin(next: SessionUser): void {
    sessionStorage.setItem(USER_KEY, JSON.stringify(next))
    setUser(next)
  }

  const [unsent, setUnsent] = useState(0) // > 0: sign-out confirm is showing

  // Ends the session but keeps claims saved on this phone (used when the session expired).
  function endSession(): void {
    clearMe()
    setToken(null)
    sessionStorage.removeItem(USER_KEY)
    setUnsent(0)
    setUser(null)
  }

  // Sign-out on a shared phone deletes this user's drafts and unsent claims. Unsent claims need a confirm.
  // A 401 on a signed-in request (expired or revoked session): back to sign-in, claims kept on the phone.
  useEffect(() => {
    window.addEventListener(SESSION_ENDED_EVENT, endSession)
    return () => window.removeEventListener(SESSION_ENDED_EVENT, endSession)
  }, [])

  async function handleLogout(): Promise<void> {
    if (user && !isStaff(user.role)) {
      const count = await unsentCount(user.id)
      if (count > 0) {
        setUnsent(count)
        return
      }
      await clearOwnerData(user.id)
    }
    signOutOnServer()
    endSession()
  }

  async function confirmLogout(): Promise<void> {
    if (user) await clearOwnerData(user.id)
    signOutOnServer()
    endSession()
  }

  if (!user) {
    return (
      <>
        <PrototypeBanner />
        <Login onLogin={handleLogin} />
      </>
    )
  }

  const staff = isStaff(user.role)
  return (
    <>
      <PrototypeBanner />
      <header className={staff ? 'topbar topbar-staff' : 'topbar'}>
        <div className="topbar-inner">
          <span className="wordmark">
            <span lang="ur" dir="rtl" className="wordmark-ur">سہارا</span>
            <span className="wordmark-en">Sahara</span>
          </span>
          <span className="who">
            <span className="who-name">{user.name}</span>
            <span className="who-role">{ROLE_LABEL[user.role]}</span>
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void handleLogout()} aria-label="Sign out">
            <Icon name="logout" size={20} />
            <span>Sign out</span>
          </button>
        </div>
      </header>
      <main className={staff ? 'shell shell-staff' : 'shell shell-citizen'}>
        {unsent > 0 && <SignOutConfirm count={unsent} onConfirm={() => void confirmLogout()} onCancel={() => setUnsent(0)} />}
        <Suspense fallback={<p className="loading" role="status">Loading…</p>}>
          <HomeFor user={user} onSignInAgain={endSession} />
        </Suspense>
      </main>
    </>
  )
}

interface SignOutConfirmProps {
  count: number
  onConfirm: () => void
  onCancel: () => void
}

function SignOutConfirm({ count, onConfirm, onCancel }: SignOutConfirmProps) {
  const ur = count === 1
    ? '1 دعویٰ ابھی نہیں بھیجا گیا۔ سائن آؤٹ کرنے سے یہ مٹ جائے گا۔'
    : `${count} دعوے ابھی نہیں بھیجے گئے۔ سائن آؤٹ کرنے سے یہ مٹ جائیں گے۔`
  const en = count === 1 ? '1 claim not sent yet. Signing out deletes it.' : `${count} claims not sent yet. Signing out deletes them.`
  return (
    <div className="confirm" role="alertdialog" aria-labelledby="signout-title">
      <p id="signout-title">
        <span lang="ur" dir="rtl" className="note-ur">{ur}</span>
        {en}
      </p>
      <div className="row">
        <button type="button" className="btn btn-secondary btn-big" onClick={onCancel}>
          <span lang="ur" dir="rtl">سائن ان رہیں</span>
          <span className="btn-en">Stay signed in</span>
        </button>
        <button type="button" className="btn btn-danger btn-big" onClick={onConfirm}>
          <span lang="ur" dir="rtl">سائن آؤٹ اور مٹا دیں</span>
          <span className="btn-en">Sign out and delete</span>
        </button>
      </div>
    </div>
  )
}
