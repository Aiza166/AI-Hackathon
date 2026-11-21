import { apiCall, apiLogin, expect, fillWizard, openAs, resetDemo, sendClaim, shot, test, zainabClaim } from './helpers'

// Journey 8: fault injection (judge console, API only: there is no console page yet).
// Raast timeout -> claim to officer + payout change flagged; identity service error -> UNSURE.
// Jev down: run with E2E_JEV_DOWN=1 against a backend started with an unreachable TYPESAFE_BASE_URL.

async function setFault(request: any, service: string, mode: string) {
  const admin = await apiLogin(request, 'admin')
  const res = await apiCall(request, admin, 'POST', '/api/v1/admin/faults', { service, mode })
  expect(res.status, `fault ${service}=${mode}`).toBe(200)
}

test.describe('J8 Fault injection', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })
  test.afterEach(async ({ request }) => {
    await setFault(request, 'raast', 'ok')
    await setFault(request, 'identity', 'ok')
  })

  test('raast timeout: new claim goes to an officer; payout change flagged PAYEE_CHECK_TIMEOUT', async ({ page, request }) => {
    await setFault(request, 'raast', 'timeout')
    const z = await apiLogin(request, 'zainab')
    await openAs(page, z)
    await fillWizard(page, { dob: '1962-06-01', useDemoButton: true })
    await sendClaim(page)
    await page.getByRole('button', { name: /Continue/ }).click({ timeout: 60_000 })
    await expect(page.locator('.verdict')).toBeVisible()
    await shot(page, 'j8-01-raast-timeout-citizen')
    const c = (await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')).body.data[0]
    test.info().annotations.push({ type: 'raast-timeout-claim', description: `${c.status} ${c.latest_decision.route} ${c.latest_decision.reason_codes}` })
    expect(c.latest_decision.route).toBe('UNSURE')
    expect(c.latest_decision.reason_codes).toContain('SERVICE_UNAVAILABLE')

    const change = await apiCall<any>(request, z, 'POST', `/api/v1/cases/${c.id}/payout-change`, { new_iban: 'PK00MOCK0000000000000013' })
    test.info().annotations.push({ type: 'raast-timeout-payout', description: `${change.status} ${JSON.stringify(change.body.data ?? change.body.error).slice(0, 300)}` })
    expect(change.body.data.status).toBe('flagged')
    expect(change.body.data.flags).toContain('PAYEE_CHECK_TIMEOUT')
    // Her PIN alone must not release it
    const conf = await apiCall<any>(request, z, 'POST', `/api/v1/payout-changes/${change.body.data.id}/confirm`, { pin: '1234' })
    test.info().annotations.push({ type: 'raast-timeout-pin', description: `${conf.status} ${conf.body.data?.status ?? conf.body.error?.message}` })
    expect(conf.body.data?.status ?? 'refused').not.toBe('applied')
  })

  test('identity service error: claim routes UNSURE with SERVICE_UNAVAILABLE, no crash', async ({ request }) => {
    await setFault(request, 'identity', 'error')
    const z = await apiLogin(request, 'zainab')
    const res = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    test.info().annotations.push({ type: 'identity-error', description: `${res.status} ${JSON.stringify(res.body.data?.latest_decision ?? res.body.error).slice(0, 300)}` })
    expect(res.status).toBe(201)
    expect(res.body.data.latest_decision.route).toBe('UNSURE')
    expect(res.body.data.latest_decision.reason_codes).toContain('SERVICE_UNAVAILABLE')
  })

  test('Jev unreachable: scam check and claim still answer safely', async ({ request }) => {
    test.skip(process.env.E2E_JEV_DOWN !== '1', 'needs a backend started with an unreachable TYPESAFE_BASE_URL')
    const z = await apiLogin(request, 'zainab')
    const scam = await apiCall<any>(request, z, 'POST', '/api/v1/scam/check', { text: 'Your pension is released. Pay Rs 5000 fee today.', sender: '03001234567' })
    test.info().annotations.push({ type: 'jev-down-scam', description: `${scam.status} ${scam.body.data?.verdict}` })
    expect(scam.status).toBe(200)
    expect(scam.body.data.verdict).not.toBe('LOOKS_GENUINE')
    const claim = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    test.info().annotations.push({ type: 'jev-down-claim', description: `${claim.status} ${JSON.stringify(claim.body.data?.latest_decision ?? claim.body.error).slice(0, 200)}` })
    expect(claim.status).toBe(201)
  })
})
