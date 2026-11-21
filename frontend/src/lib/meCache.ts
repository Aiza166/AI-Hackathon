import type { Me } from '../api/types'

// Last good GET /api/v1/me for the signed-in citizen, so after a reload with no signal she can
// still open the claim saved on this phone (drafts are keyed by her CNIC). Kept in sessionStorage
// (gone when the tab closes, cleared on sign-out), scoped to one user id, and limited to what the
// home screen needs: her id, role, name, and her own person id / CNIC / name. Nothing else.

const KEY = 'sahara.me.v1'

type Cached = { userId: string; me: Me }

function storage(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null
  } catch {
    return null // storage blocked (private mode, sandboxed frame)
  }
}

function minimal(me: Me): Me {
  const person = me.person ? { id: me.person.id, cnic: me.person.cnic, name: me.person.name } : null
  return { id: me.id, role: me.role, name: me.name, person }
}

export function saveMe(userId: string, me: Me): void {
  if (me.id !== userId) return // never cache someone else's profile under this user
  try {
    storage()?.setItem(KEY, JSON.stringify({ userId, me: minimal(me) } satisfies Cached))
  } catch {
    // Quota or blocked storage: offline resume is a convenience, the app works without it.
  }
}

function isMe(value: unknown): value is Me {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  if (typeof v.id !== 'string' || typeof v.role !== 'string') return false
  if (v.person === null) return true
  const p = v.person as Record<string, unknown> | undefined
  return typeof p === 'object' && p !== null && typeof p.id === 'string' && typeof p.cnic === 'string' && typeof p.name === 'string'
}

export function loadMe(userId: string): Me | null {
  try {
    const raw = storage()?.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<Cached>
    if (parsed.userId !== userId || !isMe(parsed.me) || parsed.me.id !== userId) return null
    return minimal(parsed.me)
  } catch {
    return null
  }
}

export function clearMe(): void {
  try {
    storage()?.removeItem(KEY)
  } catch {
    // nothing to clear
  }
}
