import { Suspense, lazy, useState } from 'react'
import { setToken } from './api/client'
import type { Role, SessionUser } from './api/types'
import { PrototypeBanner } from './components/PrototypeBanner'
import { Icon } from './lib/icons'
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

function HomeFor({ user }: { user: SessionUser }) {
  switch (user.role) {
    case 'citizen':
    case 'helper':
      return <CitizenHome user={user} />
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

  function handleLogout(): void {
    setToken(null)
    sessionStorage.removeItem(USER_KEY)
    setUser(null)
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
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout} aria-label="Sign out">
            <Icon name="logout" size={20} />
            <span>Sign out</span>
          </button>
        </div>
      </header>
      <main className={staff ? 'shell shell-staff' : 'shell shell-citizen'}>
        <Suspense fallback={<p className="loading" role="status">Loading…</p>}>
          <HomeFor user={user} />
        </Suspense>
      </main>
    </>
  )
}
