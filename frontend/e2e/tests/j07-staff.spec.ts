import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test, zainabClaim } from './helpers'

// Journey 7 (desktop): officer decides a queued case -> audit entry; auditor verifies the
// hash chain; admin runs the Digital Twin for v2 and publishes it: the pending Haider heir claims are
// re-decided under v2 (capped 2034-11-01), the decided Rakha claims keep v1.

test.use({ viewport: { width: 1280, height: 900 }, hasTouch: false })

test.describe('J7 Staff: officer, auditor, admin rules', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('officer decides queued case, audit entry, auditor chain OK', async ({ page, request }) => {
    // A wrong-DOB claim goes to a person
    const z = await apiLogin(request, 'zainab')
    const created = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1970-01-01'))
    const ref = created.body.data.reference
    test.info().annotations.push({ type: 'queued', description: `${ref} ${created.body.data.latest_decision.route} ${created.body.data.latest_decision.reason_codes}` })

    const kamran = await apiLogin(request, 'kamran')
    await openAs(page, kamran)
    await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()
    const row = page.getByRole('button', { name: `Open case ${ref}` })
    const inQueue = await row.count()
    test.info().annotations.push({ type: 'wrong-dob-in-officer-queue', description: String(inQueue > 0) })
    // ASK_PROOF cases wait for the citizen, not an officer; use a red-flag case for the decision if needed
    let decideRef = ref
    if (inQueue === 0) {
      const r = await apiLogin(request, 'rukhsana')
      const competing = await apiCall<any>(request, r, 'POST', '/api/v1/cases', {
        ...zainabClaim(null), claimant_cnic: '9000000000033', claimant_name: 'Rukhsana', payout_iban: 'PK00MOCK0000000000000003',
      })
      test.info().annotations.push({ type: 'competing', description: `${competing.status} ${JSON.stringify(competing.body.data?.latest_decision ?? competing.body.error)}` })
      decideRef = competing.body.data.reference
      await page.getByRole('button', { name: /Refresh/ }).click()
    }
    await page.getByRole('button', { name: `Open case ${decideRef}` }).click()
    await expect(page.locator('.detail-title')).toHaveText(decideRef)
    await shot(page, 'j7-01-officer-case')
    await page.locator('.detail textarea').fill('Checked papers in person (mock).')
    await page.getByRole('button', { name: /Approve/ }).click()
    await expect(page.getByRole('button', { name: `Open case ${decideRef}` })).toHaveCount(0)

    // Audit: decision recorded, chain intact
    const auditor = await apiLogin(request, 'auditor')
    const events = await apiCall<any>(request, auditor, 'GET', '/api/v1/audit')
    const list = Array.isArray(events.body.data) ? events.body.data : events.body.data.events ?? []
    expect(JSON.stringify(list)).toContain('CASE_APPROVED')
    await openAs(page, auditor)
    await page.getByPlaceholder(/Filter by action/).fill('CASE_APPROVED')
    await expect(page.locator('tbody tr').first()).toContainText('CASE_APPROVED')
    await page.getByRole('button', { name: /Verify hash chain/ }).click()
    await expect(page.getByText(/Chain intact: \d+ events checked\./)).toBeVisible()
    await shot(page, 'j7-02-auditor-verify')

    // Auditor is read-only
    const blocked = await apiCall(request, auditor, 'POST', `/api/v1/cases/${created.body.data.id}/approve`, { reason: 'auditor tries' })
    expect(blocked.status).toBe(403)
  })

  test('admin Digital Twin v2, publish re-decides pending Haider heirs, Rakha keeps v1', async ({ page, request }) => {
    const admin = await apiLogin(request, 'admin')
    await openAs(page, admin)
    await expect(page.getByRole('heading', { name: 'Rule versions' })).toBeVisible()
    await page.locator('button.version').filter({ hasText: /v2|2/ }).filter({ hasText: /draft/i }).first().click()
    const sim = page.waitForResponse((r) => r.url().includes('/simulate'))
    await page.getByRole('button', { name: /Run Digital Twin/ }).click()
    const simBody = (await (await sim).json()).data
    test.info().annotations.push({ type: 'twin', description: `checked=${simBody.checked} changed=${simBody.changed} ${JSON.stringify(simBody.cases.filter((c: any) => c.changed?.length).map((c: any) => [c.case, c.after.entitlement_end]))}` })
    expect(simBody.changed).toBeGreaterThan(0)
    await expect(page.getByText('2034-11-01').first()).toBeVisible()
    expect(simBody.will_redecide).toBe(2)
    await expect(page.getByText('Re-decided').first()).toBeVisible()
    await shot(page, 'j7-03-digital-twin')
    await page.getByRole('button', { name: /Publish v2/ }).click()
    await page.getByRole('button', { name: /Yes, publish v2/ }).click()
    await expect(page.locator('button.version').filter({ hasText: /live/i }).filter({ hasText: /2/ })).toHaveCount(1)

    // Publish re-decides the pending Haider claims under v2 (B2); the decided Rakha claims keep v1.
    const officerRows = (await apiCall<any[]>(request, await apiLogin(request, 'kamran'), 'GET', '/api/v1/cases')).body.data
    const byRef = Object.fromEntries(officerRows.filter((c: any) => c.reference.startsWith('SP-0')).map((c: any) => [c.reference, [c.status, c.latest_decision.rule_version]]))
    test.info().annotations.push({ type: 'after-publish', description: JSON.stringify(byRef) })
    expect(byRef['SP-0001']).toEqual(['in_review', 2])
    expect(byRef['SP-0002']).toEqual(['in_review', 2])
    expect(byRef['SP-0003']).toEqual(['approved', 1])
    expect(byRef['SP-0004']).toEqual(['approved', 1])
    const bilal = await apiLogin(request, 'bilal')
    const bcases = (await apiCall<any[]>(request, bilal, 'GET', '/api/v1/cases')).body.data
    const bexpl = await apiCall<any>(request, bilal, 'GET', `/api/v1/cases/${bcases[0].id}/explanation`)
    expect(bexpl.body.data.entitlement_end, 'Haider heir capped after v2 publish').toBe('2034-11-01')

    // Zainab (widow) files a new claim under v2: unaffected by the heir cap
    const z = await apiLogin(request, 'zainab')
    const zc = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    expect(zc.body.data.latest_decision.rule_version).toBe(2)
    expect(zc.body.data.latest_decision.route).toBe('AUTO_APPROVE')
  })
})
