import type { Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { apiLogin, expect, openAs, resetDemo, sendClaim, shot, test } from './helpers'

// Journey 12: every citizen and helper screen at 360 px (the narrowest common Android width),
// one step further than J9 (390 px): no sideways scroll, Urdu is RTL, every tap target is
// at least 48 x 48 px, and the strict Content-Security-Policy blocks nothing the app needs.
// Problems are soft failures, so one run lists all of them. Findings: results/narrow-360.json.

const MIN_TAP = 48
const findings: Record<string, unknown> = {}

test.use({ viewport: { width: 360, height: 780 } })

/** Collect CSP violations ("Refused to ...") from the page and the console. */
async function watchCsp(page: Page): Promise<string[]> {
  const refused: string[] = []
  page.on('console', (msg) => {
    if (/Refused to/i.test(msg.text())) refused.push(msg.text().slice(0, 200))
  })
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      const w = window as unknown as { __csp?: string[] }
      w.__csp = [...(w.__csp ?? []), `${e.violatedDirective} ${e.blockedURI}`]
    })
  })
  return refused
}

async function audit(page: Page, name: string): Promise<void> {
  await expect(page.locator('.prototype-banner')).toContainText('PROTOTYPE')
  const result = await page.evaluate((min) => {
    const urdu = [...document.querySelectorAll('[lang="ur"]')]
    const urNotRtl = urdu.filter((el) => getComputedStyle(el).direction !== 'rtl').length
    const overflow = document.documentElement.scrollWidth - window.innerWidth
    const small = [...document.querySelectorAll('button, a[href], input:not(.sr-only), select, textarea, label.btn, [role="switch"], [role="tab"]')]
      .filter((el) => {
        const r = el.getBoundingClientRect()
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'
      })
      .map((el) => {
        const r = el.getBoundingClientRect()
        const label = (el.getAttribute('aria-label') || (el as HTMLElement).innerText || el.getAttribute('placeholder') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40)
        return { label, w: Math.round(r.width), h: Math.round(r.height), cls: (el.className || '').toString().slice(0, 40) }
      })
      .filter((t) => t.h < min || t.w < min)
    const csp = (window as unknown as { __csp?: string[] }).__csp ?? []
    return { urTotal: urdu.length, urNotRtl, overflow, small, csp }
  }, MIN_TAP)
  findings[name] = result
  expect.soft(result.overflow, `${name}: sideways scroll (px) at 360`).toBeLessThanOrEqual(0)
  expect.soft(result.urNotRtl, `${name}: Urdu elements not right-to-left`).toBe(0)
  expect.soft(result.small, `${name}: tap targets under ${MIN_TAP} px`).toEqual([])
  expect.soft(result.csp, `${name}: blocked by the Content-Security-Policy`).toEqual([])
}

const next = (page: Page) => page.getByRole('button', { name: /Next/ }).click()

test.describe('J12 Phone width 360 px', () => {
  test.beforeAll(async ({ request }) => {
    await resetDemo(request)
  })
  test.afterEach(() => {
    // Merge, do not overwrite: a failed test restarts the worker, which starts with empty findings.
    const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../results')
    const file = path.join(dir, 'narrow-360.json')
    fs.mkdirSync(dir, { recursive: true })
    const earlier = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {}
    fs.writeFileSync(file, JSON.stringify({ ...earlier, ...findings }, null, 2))
  })

  test('citizen: login, every wizard step, photo step, result, Scam Shield modes, SafeSwitch, My data', async ({ page, request }) => {
    const refused = await watchCsp(page)
    await page.goto('/')
    await audit(page, 'login')
    await page.getByRole('button', { name: 'Demo accounts (mock)' }).click()
    await audit(page, 'login-demo-open')

    await openAs(page, await apiLogin(request, 'zainab'))
    await audit(page, 'citizen-home')
    await shot(page, 'j12-01-citizen-home')

    // Every wizard step, one question per screen
    await page.getByRole('button', { name: /Start a new pension claim/ }).click()
    await audit(page, 'wizard-1-relation')
    await page.getByRole('button', { name: /Widow/ }).click()
    await next(page)
    await audit(page, 'wizard-2-dob')
    await page.locator('input[type="date"]').fill('1962-06-01')
    await next(page)
    await audit(page, 'wizard-3-name')
    await page.getByRole('button', { name: 'Fill demo data (mock)' }).click()
    await next(page)
    await audit(page, 'wizard-4-cnic')
    await next(page)
    await audit(page, 'wizard-5-papers')
    await next(page)
    await audit(page, 'wizard-6-account')
    await next(page)
    await expect(page.getByText('7 / 7')).toBeVisible()
    await audit(page, 'wizard-7-review')
    await shot(page, 'j12-02-review')
    await sendClaim(page)

    await expect(page.getByText('Take a photo of each paper')).toBeVisible()
    await audit(page, 'photo-step')
    await page.getByRole('button', { name: /Continue/ }).click()
    await expect(page.locator('.verdict')).toBeVisible()
    await audit(page, 'case-result')
    await shot(page, 'j12-03-result')
    await page.getByRole('button', { name: /Back/ }).last().click()

    // Scam Shield: the three ways in, then a verdict
    await page.getByRole('button', { name: /Is this message a scam/ }).click()
    await audit(page, 'scam-message')
    await page.getByRole('button', { name: /Screenshot/ }).first().click()
    await audit(page, 'scam-screenshot')
    await page.getByRole('button', { name: /Phone call/ }).first().click()
    await audit(page, 'scam-call')
    await page.getByRole('button', { name: /Message or link/ }).first().click()
    await page.getByRole('button', { name: 'Fill demo scam SMS (mock)' }).click()
    await page.getByRole('button', { name: /Check this message/ }).click()
    await expect(page.locator('.report-card')).toBeVisible({ timeout: 60_000 })
    await audit(page, 'scam-verdict')
    await shot(page, 'j12-04-scam-verdict')
    await page.getByRole('button', { name: /Back/ }).first().click()

    // SafeSwitch: form and a held change waiting for her PIN
    await page.getByRole('button', { name: /^.*Change payout account$/ }).click()
    await audit(page, 'safeswitch-form')
    await page.getByRole('button', { name: 'Demo: Own wallet' }).click()
    await page.getByRole('button', { name: /Check account and request change/ }).click()
    await expect(page.getByRole('button', { name: /Confirm with my PIN/ })).toBeVisible({ timeout: 30_000 })
    await audit(page, 'safeswitch-held')
    await shot(page, 'j12-05-safeswitch')
    await page.getByRole('button', { name: /Back/ }).first().click()

    await page.getByRole('button', { name: /My data/ }).click()
    await audit(page, 'my-data')
    await shot(page, 'j12-06-my-data', true)

    expect.soft(refused, 'console: "Refused to ..." (CSP)').toEqual([])
  })

  test('helper: family list, acting-for banner', async ({ page, request }) => {
    const refused = await watchCsp(page)
    await openAs(page, await apiLogin(request, 'ayesha'))
    await expect(page.getByRole('heading', { name: /Families \(\d+\)/ })).toBeVisible()
    await audit(page, 'helper-home')
    await page.getByPlaceholder('Search by name').fill('Zainab')
    await page.getByRole('button', { name: /Zainab Bibi/ }).click()
    await expect(page.locator('.acting')).toContainText('Zainab Bibi')
    await audit(page, 'helper-acting-for')
    await shot(page, 'j12-07-helper')
    expect.soft(refused, 'console: "Refused to ..." (CSP)').toEqual([])
  })
})
