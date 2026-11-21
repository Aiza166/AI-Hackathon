import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Shared helpers: API login (with back-off for the 10/minute login limit), demo reset,
// session injection, claim wizard driver, console-error capture and screenshots.

const HERE = path.dirname(fileURLToPath(import.meta.url))
export const REPO = path.resolve(HERE, '../../..')
export const SAMPLE_DOCS = path.join(REPO, 'backend', 'sample_docs')
export const SCREENS = path.join(REPO, 'docs', 'test-screens')
const RESULTS = path.resolve(HERE, '../results')

export const PIN = '1234'
export const PERSONAS = {
  zainab: '00000000001',
  rukhsana: '00000000002',
  ayesha: '00000000010',
  kamran: '00000000020',
  admin: '00000000030',
  auditor: '00000000040',
  bilal: '00000000005',
  hina: '00000000006',
} as const
export type Persona = keyof typeof PERSONAS

// Mock data of the demo widow (from the seed and ClaimWizard demo prefill).
export const ZAINAB = {
  cnic: '9000000000022',
  name: 'Zainab Bibi',
  dob: '1962-06-01',
  deceasedName: 'Muhammad Aslam',
  deceasedCnic: '9000000000011',
  iban: 'PK00MOCK0000000000000001',
}

export interface Session {
  token: string
  user: { id: string; name: string; role: string }
}

const LOGIN_RETRY_WAIT_MS = 62_000
const LOGIN_MAX_TRIES = 4

export async function apiLogin(request: APIRequestContext, who: Persona): Promise<Session> {
  for (let attempt = 1; attempt <= LOGIN_MAX_TRIES; attempt++) {
    const res = await request.post('/api/v1/auth/login', { data: { phone: PERSONAS[who], pin: PIN } })
    if (res.status() === 429) {
      await new Promise((r) => setTimeout(r, LOGIN_RETRY_WAIT_MS))
      continue
    }
    expect(res.status(), `login ${who}`).toBe(200)
    const body = await res.json()
    return { token: body.data.access_token, user: body.data.user }
  }
  throw new Error(`login for ${who} kept hitting the rate limit`)
}

export async function apiCall<T = unknown>(
  request: APIRequestContext,
  session: Session,
  method: 'GET' | 'POST' | 'PATCH',
  url: string,
  data?: unknown,
): Promise<{ status: number; body: { success: boolean; data: T; error: { code: string; message: string } | null } }> {
  const res = await request.fetch(url, { method, data, headers: { Authorization: `Bearer ${session.token}` }, timeout: 60_000 })
  return { status: res.status(), body: await res.json().catch(() => ({ success: false, data: null, error: null })) }
}

/** Restore the seeded demo world. User IDs change, so log in again afterwards. */
export async function resetDemo(request: APIRequestContext): Promise<void> {
  const admin = await apiLogin(request, 'admin')
  const res = await apiCall(request, admin, 'POST', '/api/v1/admin/seed/reset')
  expect(res.status, 'demo reset').toBe(200)
  // Faults live in the DB; reset should clear them, but make sure raast is back to ok.
  await apiCall(request, await apiLogin(request, 'admin'), 'POST', '/api/v1/admin/faults', { service: 'raast', mode: 'ok' })
}

/** Open the app already signed in (skips the UI login to stay under the login rate limit). */
export async function openAs(page: Page, session: Session): Promise<void> {
  await page.goto('/')
  await page.evaluate(([token, user]) => {
    sessionStorage.setItem('sahara.token', token)
    sessionStorage.setItem('sahara.user', user)
  }, [session.token, JSON.stringify(session.user)])
  await page.reload()
  await expect(page.getByRole('button', { name: /Sign out/ })).toBeVisible()
}

export function zainabClaim(dob: string | null, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    claimant_cnic: ZAINAB.cnic,
    claimant_name: ZAINAB.name,
    claimant_dob: dob,
    relation_claimed: 'widow',
    deceased_cnic: ZAINAB.deceasedCnic,
    deceased_name: ZAINAB.deceasedName,
    payout_iban: ZAINAB.iban,
    documents: ['death_certificate', 'claimant_cnic', 'frc', 'nikah_nama'],
    ...extra,
  }
}

export interface WizardInput {
  dob: string // '' = leave blank
  useDemoButton: boolean // "Fill demo data (mock)" on the name step
}

const next = (page: Page) => page.getByRole('button', { name: /Next/ }).click()

/** Drive the 7-step claim wizard up to (and including) "Send claim". */
export async function fillWizard(page: Page, input: WizardInput): Promise<void> {
  await page.getByRole('button', { name: /Start a new pension claim/ }).click()
  await expect(page.getByText('1 / 7')).toBeVisible()
  await page.getByRole('button', { name: /Widow/ }).click()
  await next(page)
  await expect(page.getByText('2 / 7')).toBeVisible()
  if (input.dob) await page.locator('input[type="date"]').fill(input.dob)
  await next(page)
  if (input.useDemoButton) {
    await page.getByRole('button', { name: 'Fill demo data (mock)' }).click()
    await next(page)
    await next(page)
    await next(page)
    await next(page)
  } else {
    await page.getByLabel('Name of the deceased').fill(ZAINAB.deceasedName)
    await next(page)
    await page.locator('input[inputmode="numeric"][maxlength="13"]').fill(ZAINAB.deceasedCnic)
    await next(page)
    for (const name of ['Death certificate', 'Your CNIC', 'Family certificate (FRC)', 'Nikah nama']) {
      await page.getByRole('button', { name: new RegExp(name.replace(/[()]/g, '\\$&')) }).click()
    }
    await next(page)
    await page.getByLabel('IBAN of an account in your own name').fill(ZAINAB.iban)
    await next(page)
  }
  await expect(page.getByText('7 / 7')).toBeVisible()
}

export async function sendClaim(page: Page): Promise<void> {
  await page.getByRole('button', { name: /Send claim/ }).click()
}

/** Upload one sample document on the photo step and wait for the server's reading. */
export async function uploadDoc(page: Page, kind: string, file: string): Promise<{ status: number; body: any }> {
  const responsePromise = page.waitForResponse(
    (r) => r.url().includes('/documents') && r.request().method() === 'POST' && !r.url().includes('/confirm'),
    { timeout: 90_000 },
  )
  await page.locator(`#doc-${kind}`).setInputFiles(path.join(SAMPLE_DOCS, file))
  const sendAnyway = page.getByRole('button', { name: 'Send anyway' })
  const res = await Promise.race([
    responsePromise,
    sendAnyway.waitFor({ timeout: 10_000 }).then(async () => {
      await sendAnyway.click()
      return responsePromise
    }).catch(() => responsePromise),
  ])
  return { status: res.status(), body: await res.json().catch(() => null) }
}

export async function shot(page: Page, name: string, fullPage = false): Promise<string> {
  fs.mkdirSync(SCREENS, { recursive: true })
  const file = path.join(SCREENS, `${name}.png`)
  await page.screenshot({ path: file, fullPage, animations: 'disabled' })
  return `docs/test-screens/${name}.png`
}

// Ignore noise that is not an app bug: missing optional audio clips (dev server) and
// expected 4xx responses the UI handles on purpose (asserted separately in the tests).
const CONSOLE_IGNORE = [/Failed to load resource: the server responded with a status of 4\d\d/, /net::ERR_INTERNET_DISCONNECTED/, /Download the React DevTools/]

interface Fixtures {
  consoleErrors: string[]
}

export const test = base.extend<Fixtures>({
  consoleErrors: [
    async ({ page }, use, testInfo) => {
      const errors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() !== 'error') return
        const text = msg.text()
        if (!CONSOLE_IGNORE.some((re) => re.test(text))) errors.push(text.slice(0, 300))
      })
      page.on('pageerror', (err) => errors.push(`pageerror: ${err.message.slice(0, 300)}`))
      await use(errors)
      fs.mkdirSync(RESULTS, { recursive: true })
      const file = path.join(RESULTS, 'console-errors.json')
      const all = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {}
      all[testInfo.titlePath.slice(1).join(' > ')] = errors
      fs.writeFileSync(file, JSON.stringify(all, null, 2))
      await testInfo.attach('console-errors', { body: errors.join('\n') || '(none)', contentType: 'text/plain' })
    },
    { auto: true },
  ],
})

export { expect }
