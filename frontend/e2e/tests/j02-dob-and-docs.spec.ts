import { apiCall, apiLogin, expect, fillWizard, openAs, resetDemo, sendClaim, shot, test, uploadDoc, zainabClaim } from './helpers'

// Journey 2: blank DOB -> ASK_PROOF (never a rejection); wrong DOB -> DOB_MISMATCH;
// edited death certificate -> officer UNSURE with DOC_EDIT_RISK and an ELA heatmap.

test.describe('J2 DOB and document checks', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('blank DOB typed by hand -> ASK_PROOF with "confirm your date of birth"', async ({ page, request }) => {
    await openAs(page, await apiLogin(request, 'zainab'))
    await fillWizard(page, { dob: '', useDemoButton: false })
    await expect(page.getByText('Not given (we will ask)')).toBeVisible()
    await sendClaim(page)
    await expect(page.getByText('Take a photo of each paper')).toBeVisible()
    await page.getByRole('button', { name: /Continue/ }).click()
    await expect(page.getByText('One more paper is needed', { exact: true })).toBeVisible()
    await expect(page.getByText(/confirm your date of birth/i).first()).toBeVisible()
    await shot(page, 'j2-01-blank-dob-ask-proof')
    const z = await apiLogin(request, 'zainab')
    const cases = await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')
    expect(cases.body.data[0].latest_decision.route).toBe('ASK_PROOF')
    expect(cases.body.data[0].status).not.toBe('rejected')
  })

  test('blank DOB and "Fill demo data" pressed -> DOB stays blank (B3)', async ({ page, request }) => {
    // Demo script says "File Zainab's claim with the DOB step empty". The demo-data button on a later
    // step must not fill her DOB behind her back (fixed: it never touches the DOB).
    await openAs(page, await apiLogin(request, 'zainab'))
    await fillWizard(page, { dob: '', useDemoButton: true })
    const dobRow = page.locator('.review-row').filter({ hasText: 'Your date of birth' })
    const shown = (await dobRow.locator('dd').textContent()) ?? ''
    test.info().annotations.push({ type: 'dob-after-demo-button', description: shown })
    expect(shown, 'DOB left blank should stay blank after "Fill demo data"').toContain('Not given')
  })

  test('wrong DOB -> DOB_MISMATCH, routed for proof/officer, not rejected', async ({ page, request }) => {
    await openAs(page, await apiLogin(request, 'zainab'))
    await fillWizard(page, { dob: '1970-01-01', useDemoButton: true })
    await expect(page.locator('.review-row').filter({ hasText: 'Your date of birth' })).toContainText('1970-01-01')
    await sendClaim(page)
    await page.getByRole('button', { name: /Continue/ }).click()
    await expect(page.locator('.verdict')).toBeVisible()
    await shot(page, 'j2-02-wrong-dob')
    const z = await apiLogin(request, 'zainab')
    const c = (await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')).body.data[0]
    test.info().annotations.push({ type: 'wrong-dob', description: `${c.latest_decision.route} ${c.latest_decision.reason_codes.join(',')}` })
    expect(c.latest_decision.reason_codes).toContain('DOB_MISMATCH')
    expect(c.latest_decision.route).not.toBe('AUTO_APPROVE')
    expect(c.status).not.toBe('rejected')
  })

  test('edited death certificate -> UNSURE with DOC_EDIT_RISK; officer sees heatmap', async ({ page, request }) => {
    const z = await apiLogin(request, 'zainab')
    await openAs(page, z)
    await fillWizard(page, { dob: '1962-06-01', useDemoButton: true })
    await sendClaim(page)
    const up = await uploadDoc(page, 'death_certificate', 'death_certificate_aslam_edited.png')
    test.info().annotations.push({ type: 'edited-upload', description: JSON.stringify({ status: up.status, risk: up.body?.data?.risk_level, case_status: up.body?.data?.case_status, reasons: up.body?.data?.reasons?.map((r: any) => r.code) }) })
    const citizenText = (await page.locator('.doc-capture').innerText()).toLowerCase()
    expect.soft(citizenText, 'never "fake"/"forged" on the citizen screen').not.toMatch(/\bfake\b|forged/)
    await shot(page, 'j2-03-edited-cert-citizen', true)
    await page.getByRole('button', { name: /Continue/ }).click()
    await expect(page.locator('.verdict')).toBeVisible()

    const cases = (await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')).body.data
    const caseRow = cases[0]
    const decisions = await apiCall<any[]>(request, z, 'GET', `/api/v1/cases/${caseRow.id}/decisions`)
    test.info().annotations.push({ type: 'edited-decisions', description: JSON.stringify(decisions.body.data?.map?.((d: any) => [d.route, d.reason_codes]) ?? decisions.body).slice(0, 600) })
    const latest = caseRow.latest_decision
    expect.soft(latest.route, 'route after edited certificate').toBe('UNSURE')
    expect.soft(latest.reason_codes, 'reason codes after edited certificate').toContain('DOC_EDIT_RISK')

    // Officer view at desktop width
    await page.setViewportSize({ width: 1280, height: 900 })
    await openAs(page, await apiLogin(request, 'kamran'))
    await page.getByRole('button', { name: new RegExp(`Open case ${caseRow.reference}`) }).click()
    await expect(page.getByRole('img', { name: 'Error level analysis heatmap' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/DOC_EDIT_RISK|second look/i).first()).toBeVisible()
    await shot(page, 'j2-04-officer-heatmap', false)
  })
})
