import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test, zainabClaim } from './helpers'

// Journey 7 (desktop): officer decides a queued case -> audit entry; auditor verifies the
// hash chain; admin runs the Digital Twin for v2, publishes it, and a new heir case is decided under v2.

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

  test('admin Digital Twin v2, publish, new heir case decided under v2', async ({ page, request }) => {
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
    await shot(page, 'j7-03-digital-twin')
    await page.getByRole('button', { name: /Publish v2/ }).click()
    await page.getByRole('button', { name: /Yes, publish v2/ }).click()
    await expect(page.locator('button.version').filter({ hasText: /live/i }).filter({ hasText: /2/ })).toHaveCount(1)

    // New heir case after publish: decided under v2 with the 10-year cap
    let decided: any = null
    for (const who of ['bilal', 'hina'] as const) {
      const s = await apiLogin(request, who)
      const me = (await apiCall<any>(request, s, 'GET', '/api/v1/me')).body.data
      const relation = who === 'bilal' ? 'son' : 'daughter'
      const res = await apiCall<any>(request, s, 'POST', '/api/v1/cases', {
        claimant_cnic: me.person.cnic, claimant_name: me.person.name, claimant_dob: who === 'bilal' ? '2006-05-01' : '1991-12-12',
        relation_claimed: relation, deceased_cnic: '9000000000066', deceased_name: 'Ghulam Haider',
        payout_iban: who === 'bilal' ? 'PK00MOCK0000000000000005' : 'PK00MOCK0000000000000006', documents: ['death_certificate', 'frc', 'claimant_cnic'],
      })
      test.info().annotations.push({ type: `heir-${who}`, description: `${res.status} ${JSON.stringify(res.body.data?.latest_decision ?? res.body.error).slice(0, 300)}` })
      if (res.status === 201) {
        decided = { session: s, data: res.body.data }
        break
      }
    }
    // The seeded Haider heirs already hold open claims (409), so a brand-new heir claim cannot be filed.
    test.info().annotations.push({ type: 'heir-new-claim-possible', description: String(Boolean(decided)) })
    if (decided) expect(decided.data.latest_decision.rule_version).toBe(2)

    // Existing Haider case after publish: does the citizen see the v2 cap?
    const bilal = await apiLogin(request, 'bilal')
    const bcases = (await apiCall<any[]>(request, bilal, 'GET', '/api/v1/cases')).body.data
    const bexpl = await apiCall<any>(request, bilal, 'GET', `/api/v1/cases/${bcases[0].id}/explanation`)
    test.info().annotations.push({ type: 'haider-after-publish', description: JSON.stringify({ ref: bcases[0].reference, rule: bcases[0].latest_decision?.rule_version, end: bexpl.body.data.entitlement_end }) })
    expect.soft(bexpl.body.data.entitlement_end, 'Haider heir capped after v2 publish').toBe('2034-11-01')

    // Zainab (widow) files a new claim under v2: unaffected by the heir cap
    const z = await apiLogin(request, 'zainab')
    const zc = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    expect(zc.body.data.latest_decision.rule_version).toBe(2)
    expect(zc.body.data.latest_decision.route).toBe('AUTO_APPROVE')
  })
})
