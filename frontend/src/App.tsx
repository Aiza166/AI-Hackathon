import { PrototypeBanner } from './components/PrototypeBanner'

// Phase 0 placeholder: role entry points. Real pages arrive in Phase 1.
const ROLES = [
  { key: 'citizen', icon: '\u{1F3E0}', label: 'Citizen' },
  { key: 'helper', icon: '\u{1F91D}', label: 'Helper' },
  { key: 'officer', icon: '\u{1F5C2}', label: 'Officer' },
  { key: 'admin', icon: '⚙', label: 'Admin' },
  { key: 'auditor', icon: '\u{1F50D}', label: 'Auditor' },
] as const

export default function App() {
  return (
    <>
      <PrototypeBanner />
      <main className="page">
        <h1>Sahara</h1>
        <p>Survivor pension claims (prototype)</p>
        <div className="role-grid">
          {ROLES.map((role) => (
            <button key={role.key} className="role-card" type="button">
              <span className="icon" aria-hidden="true">{role.icon}</span>
              <span>{role.label}</span>
            </button>
          ))}
        </div>
      </main>
    </>
  )
}
