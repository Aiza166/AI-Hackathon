import type { Page } from '@playwright/test'
import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test } from './helpers'

// Journey 4: Scam Shield. Fee scam -> LIKELY_SCAM + report card (1799, PTA);
// genuine-looking message; the same scam "from 8171" is still LIKELY_SCAM.

const GENUINE = 'Your pension claim SP-1001 has been received. Status updates will come only from PENSION-GOV. Never pay any fee. Visit pension.gov.example for status.'
const FEE_SCAM_8171 = 'BISP: Aap ki Benazir aur pension raqam release ho gayi. Rs 2000 fee is number par Easypaisa karein aur OTP code batayein.'

async function check(page: Page, text: string, sender: string, onCall: boolean | null): Promise<string> {
  await page.getByLabel(/Paste or type the message/).fill(text)
  if (sender) await page.getByLabel(/Sender number or name/).fill(sender)
  if (onCall !== null) await page.getByRole('button', { name: onCall ? /Yes/ : /No/ }).first().click()
  const res = page.waitForResponse((r) => r.url().includes('/api/v1/scam/check'))
  await page.getByRole('button', { name: /Check this message/ }).click()
  const body = await (await res).json()
  await expect(page.locator('.verdict')).toBeVisible()
  return body.data.verdict as string
}

test.describe('J4 Scam Shield', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('fee scam, genuine message, sender 8171', async ({ page, request }) => {
    await openAs(page, await apiLogin(request, 'zainab'))
    await page.getByRole('button', { name: /Is this message a scam/ }).click()
    await expect(page.getByRole('heading', { name: /Scam Shield/ })).toBeVisible()

    // 1. Demo fee scam, someone on the phone
    await page.getByRole('button', { name: 'Fill demo scam SMS (mock)' }).click()
    await page.getByRole('button', { name: /Yes/ }).first().click()
    const r1 = page.waitForResponse((r) => r.url().includes('/api/v1/scam/check'))
    await page.getByRole('button', { name: /Check this message/ }).click()
    expect((await (await r1).json()).data.verdict).toBe('LIKELY_SCAM')
    await expect(page.getByText('This looks like a scam. Do not send money or share a code.')).toBeVisible()
    await expect(page.locator('.reason-list .bi-ur').first()).toHaveAttribute('dir', 'rtl')
    const report = page.locator('.report-card')
    await expect(report).toContainText('1799')
    await expect(report).toContainText(/PTA/)
    await expect(report.locator('a[href^="tel:1799"]')).toHaveCount(1)
    await shot(page, 'j4-01-likely-scam', true)

    // 2. Genuine-looking message from the official sender
    await page.getByRole('button', { name: /Check another message/ }).click()
    const v2 = await check(page, GENUINE, 'PENSION-GOV', false)
    test.info().annotations.push({ type: 'genuine-verdict', description: v2 })
    expect.soft(['LOOKS_GENUINE', 'NOT_SURE']).toContain(v2)
    await expect(page.locator('.report-card')).toHaveCount(v2 === 'LIKELY_SCAM' ? 1 : 0)
    await shot(page, 'j4-02-genuine')

    // 3. Fee/OTP scam claiming to come from 8171: content outweighs sender ID
    await page.getByRole('button', { name: /Check another message/ }).click()
    const v3 = await check(page, FEE_SCAM_8171, '8171', false)
    expect(v3).toBe('LIKELY_SCAM')
    await expect(page.locator('.report-card')).toContainText('0800-26477') // BISP route only when BISP is mentioned

    // Scam map counts for the officer
    const officer = await apiLogin(request, 'kamran')
    const map = await apiCall<any>(request, officer, 'GET', '/api/v1/scam/map?days=7')
    expect(map.body.data.total_checked).toBeGreaterThanOrEqual(3)
    // Citizen must not read the scam map
    const z = await apiLogin(request, 'zainab')
    expect((await apiCall(request, z, 'GET', '/api/v1/scam/map?days=7')).status).toBe(403)
  })

  test('borderline message is NOT_SURE, never silently safe', async ({ page, request }) => {
    await openAs(page, await apiLogin(request, 'zainab'))
    await page.getByRole('button', { name: /Is this message a scam/ }).click()
    const v = await check(page, 'Salam, aap ke pension case ke baare mein office se call aayegi. Apna CNIC tayyar rakhein.', '03001234567', null)
    test.info().annotations.push({ type: 'borderline-verdict', description: v })
    expect.soft(v).toBe('NOT_SURE')
  })
})
