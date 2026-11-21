import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { apiCall, apiLogin, expect, openAs, resetDemo, test, zainabClaim } from './helpers'

// Journey 9: basics on every citizen screen at 390 px: PROTOTYPE banner, Urdu is RTL,
// tap targets >= 48 px, no horizontal scroll, visible keyboard focus, axe (serious/critical).

const MIN_TAP = 48
const findings: Record<string, unknown> = {}

async function audit(page: Page, name: string): Promise<void> {
  await expect(page.locator('.prototype-banner')).toContainText('PROTOTYPE')
  const result = await page.evaluate((min) => {
    const urNotRtl = [...document.querySelectorAll('[lang="ur"]')].filter((el) => el.getAttribute('dir') !== 'rtl' && getComputedStyle(el).direction !== 'rtl').length
    const urTotal = document.querySelectorAll('[lang="ur"]').length
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
    return { urNotRtl, urTotal, overflow, small }
  }, MIN_TAP)
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const serious = axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target.join(' ') }))
  findings[name] = { ...result, axe: serious }
  expect.soft(result.urNotRtl, `${name}: Urdu elements without RTL`).toBe(0)
  expect.soft(result.overflow, `${name}: horizontal scroll px at 390`).toBeLessThanOrEqual(0)
}

test.describe('J9 Accessibility and basics (390 px)', () => {
  test.beforeAll(async ({ request }) => {
    await resetDemo(request)
  })
  test.afterAll(() => {
    const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../results')
    fs.mkdirSync(dir, { recursive: true })
    fs.writeFileSync(path.join(dir, 'a11y.json'), JSON.stringify(findings, null, 2))
  })

  test('citizen screens: banner, RTL, overflow, tap targets, axe', async ({ page, request }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Demo accounts (mock)' }).click()
    await audit(page, 'login')

    const z = await apiLogin(request, 'zainab')
    await apiCall(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    await openAs(page, z)
    await audit(page, 'citizen-home')

    await page.getByRole('button', { name: /Start a new pension claim/ }).click()
    await audit(page, 'wizard-step1')
    await page.getByRole('button', { name: /Next/ }).click()
    await audit(page, 'wizard-dob')
    await page.getByRole('button', { name: /Back/ }).click()
    await page.getByRole('button', { name: /Back/ }).click()

    await page.locator('.claim-item').first().click()
    await expect(page.locator('.verdict')).toBeVisible()
    await audit(page, 'case-result')
    await page.getByRole('button', { name: /Back/ }).last().click()

    await page.getByRole('button', { name: /Is this message a scam/ }).click()
    await audit(page, 'scam-shield')
    await page.getByRole('button', { name: 'Fill demo scam SMS (mock)' }).click()
    await page.getByRole('button', { name: /Check this message/ }).click()
    await expect(page.locator('.report-card')).toBeVisible({ timeout: 60_000 })
    await audit(page, 'scam-verdict')
    await page.getByRole('button', { name: /Back/ }).first().click()

    await page.getByRole('button', { name: /^.*Change payout account$/ }).click()
    await audit(page, 'safeswitch')
    await page.getByRole('button', { name: /Back/ }).first().click()

    await page.getByRole('button', { name: /My data/ }).click()
    await audit(page, 'my-data')
    test.info().annotations.push({ type: 'a11y', description: JSON.stringify(findings).slice(0, 3000) })
  })

  test('keyboard focus is visible on the login form', async ({ page }) => {
    await page.goto('/')
    const styles: string[] = []
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press('Tab')
      styles.push(await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null
        if (!el || el === document.body) return 'body'
        const s = getComputedStyle(el)
        const visible = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none')
        return `${el.tagName}.${el.className.toString().split(' ')[0]}:${visible ? 'visible' : 'NONE'}`
      }))
    }
    test.info().annotations.push({ type: 'focus', description: styles.join(' | ') })
    expect(styles.filter((s) => s.endsWith('NONE'))).toEqual([])
  })
})
