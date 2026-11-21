import { apiCall, apiLogin, expect, fillWizard, resetDemo, sendClaim, shot, test, uploadDoc } from './helpers'

// Journey 1: Zainab signs in through the UI, files the claim (DOB step, photo step),
// is auto-approved with Urdu + English reasons, uses Listen, opens My data and takes consent back.

test.describe('J1 Zainab golden path', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('login, wizard with DOB + photos, AUTO_APPROVE, Listen, My data, consent take-back', async ({ page, request }) => {
    // UI login through the hidden demo toggle
    await page.goto('/')
    await expect(page.locator('.prototype-banner')).toContainText(/PROTOTYPE/i)
    await page.getByRole('button', { name: 'Demo accounts (mock)' }).click()
    await page.getByRole('button', { name: /Zainab/ }).click()
    await expect(page.getByRole('button', { name: /Sign out/ })).toBeVisible()
    await shot(page, 'j1-01-citizen-home')

    await fillWizard(page, { dob: '1962-06-01', useDemoButton: true })
    await expect(page.getByText('1962-06-01')).toBeVisible()
    await shot(page, 'j1-02-review')
    await sendClaim(page)

    // Photo step: upload the original CNIC front and death certificate
    await expect(page.getByText('Take a photo of each paper')).toBeVisible()
    const cnic = await uploadDoc(page, 'claimant_cnic', 'cnic_front_zainab.png')
    expect.soft(cnic.status, 'CNIC upload status').toBe(201)
    const death = await uploadDoc(page, 'death_certificate', 'death_certificate_aslam.png')
    expect.soft(death.status, 'death certificate upload status').toBe(201)
    test.info().annotations.push({ type: 'doc-results', description: JSON.stringify({ cnic: cnic.body?.data?.risk_level ?? cnic.body, death: death.body?.data?.risk_level ?? death.body }).slice(0, 500) })
    await page.waitForTimeout(500) // let React render the result rows before the screenshot
    await shot(page, 'j1-03-photo-step', true)
    await page.getByRole('button', { name: /Continue/ }).click()

    // Result: approved, reasons in Urdu and English
    await expect(page.getByText('Your claim is approved', { exact: true })).toBeVisible()
    await expect(page.locator('.reason-ur').first()).toHaveAttribute('dir', 'rtl')
    await expect(page.locator('.reason-en').first()).not.toBeEmpty()
    await shot(page, 'j1-04-approved')

    // Listen: either a pre-recorded clip, the server voice (TTS 200) or the phone voice; no crash.
    const tts = page.waitForResponse((r) => r.url().includes('/api/v1/speech/tts'), { timeout: 30_000 }).catch(() => null)
    await page.locator('.verdict').getByRole('button', { name: /Listen/ }).click()
    const ttsRes = await tts
    test.info().annotations.push({ type: 'tts', description: ttsRes ? `TTS HTTP ${ttsRes.status()}` : 'no TTS request (clip or phone voice)' })
    if (ttsRes) expect.soft([200, 503]).toContain(ttsRes.status())

    // Decision checked through the API as well
    const z = await apiLogin(request, 'zainab')
    const cases = await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')
    expect(cases.body.data[0].latest_decision.route).toBe('AUTO_APPROVE')

    // My data -> consent take-back
    await page.getByRole('button', { name: /Back/ }).last().click()
    await page.getByRole('button', { name: /My data/ }).click()
    await expect(page.getByRole('heading', { name: /My data/ })).toBeVisible()
    await shot(page, 'j1-05-my-data')
    const ayeshaCard = page.locator('.grant').filter({ hasText: 'Ayesha' })
    await ayeshaCard.getByRole('button', { name: /Take back all access/ }).click()
    await ayeshaCard.getByRole('button', { name: /Yes, take back/ }).click()
    await expect(page.getByText('Access you took back')).toBeVisible()

    // Server enforces it: the helper can no longer read Zainab's case data
    const ayesha = await apiLogin(request, 'ayesha')
    const fams = await apiCall<any[]>(request, ayesha, 'GET', '/api/v1/helper/families')
    const zf = fams.body.data.find((f: any) => /Zainab/.test(f.name))
    expect(zf, 'Zainab still listed for helper').toBeTruthy()
    expect(zf.consent_active === false || !zf.cnic).toBeTruthy()
    // Demo script: "Ayesha's next request returns 403, logged as CONSENT_DENIED"
    const caseId = cases.body.data[0].id
    const blocked = await apiCall(request, ayesha, 'GET', `/api/v1/cases/${caseId}`)
    expect(blocked.status, 'helper reads withdrawn case').toBe(403)
    const log = await apiCall<any[]>(request, z, 'GET', '/api/v1/me/access-log')
    expect(JSON.stringify(log.body.data)).toContain('CONSENT_DENIED')
  })
})
