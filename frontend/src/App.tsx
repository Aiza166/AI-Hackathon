import { useState } from 'react'
import { setToken } from './api/client'
import type { SessionUser } from './api/types'
import { PrototypeBanner } from './components/PrototypeBanner'
import { AuditorHome } from './pages/AuditorHome'
import { CitizenHome } from './pages/CitizenHome'
import { Login } from './pages/Login'
import { OfficerHome } from './pages/OfficerHome'

const USER_KEY = 'sahara.user'

function loadUser(): SessionUser | null {
  const raw = sessionStorage.getItem(USER_KEY)
  return raw ? (JSON.parse(raw) as SessionUser) : null
}

function HomeFor({ user }: { user: SessionUser }) {
  switch (user.role) {
    case 'citizen':
    case 'helper':
      return <CitizenHome user={user} />
    case 'officer':
      return <OfficerHome />
    case 'auditor':
    case 'admin':
      return <AuditorHome />
  }
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

  return (
    <>
      <PrototypeBanner />
      {user ? (
        <main className="page">
          <header className="row">
            <strong>Sahara</strong>
            <span className="muted">{user.name} · {user.role}</span>
            <button type="button" onClick={handleLogout}>Sign out</button>
          </header>
          <HomeFor user={user} />
        </main>
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </>
  )
}
