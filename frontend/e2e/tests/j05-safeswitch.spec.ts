import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test, zainabClaim } from './helpers'

// Journey 5: SafeSwitch payout change. Joint account ...0012 flagged; own wallet ...0013
// confirmed with PIN; cancel; officer approves / rejects flagged changes.

test.describe('J5 SafeSwitch', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('joint flagged + cancel, wallet confirmed with PIN, officer approve/reject', async ({ page, request }) => {
    const z = await apiLogin(request, 'zainab')
    const created = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    expect(created.status).toBe(201)
    const caseId = created.body.data.id

    await openAs(page, z)
    await page.getByRole('button', { name: /^.*Change payout account$/ }).click()
    await expect(page.getByRole('heading', { name: /Change payout account/ })).toBeVisible()

    // Joint account: close match, flagged, proof needed
    await page.getByRole('button', { name: 'Demo: Joint account' }).click()
    await page.getByRole('button', { name: /Check account and request change/ }).click()
    await expect(page.getByText('Held longer: an officer must check')).toBeVisible()
    await expect(page.getByText(/Joint \(two names\)/)).toBeVisible()
    await expect(page.locator('.reason-list')).toBeVisible()
    await shot(page, 'j5-01-joint-flagged', true)
    let changes = (await apiCall<any[]>(request, z, 'GET', `/api/v1/cases/${caseId}/payout-changes`)).body.data
    const joint = changes[0]
    test.info().annotations.push({ type: 'joint', description: `${joint.status} ${joint.payee_result} ${joint.flags.join(',')}` })
    expect(joint.status).toBe('flagged')
    expect(joint.payee_result).toBe('close_match')

    // Cancel it
    await page.getByRole('button', { name: /Cancel this change/ }).click()
    await page.getByRole('button', { name: /Yes, cancel/ }).click()
    await expect(page.getByRole('button', { name: /Check account and request change/ })).toBeVisible()
    changes = (await apiCall<any[]>(request, z, 'GET', `/api/v1/cases/${caseId}/payout-changes`)).body.data
    expect(changes.find((c) => c.id === joint.id).status).toBe('cancelled')

    // Own wallet: match, held 48 h, confirm with PIN
    await page.getByRole('button', { name: 'Demo: Own wallet' }).click()
    await page.getByRole('button', { name: /Check account and request change/ }).click()
    await expect(page.getByText('On hold: waiting for your PIN')).toBeVisible()
    await expect(page.getByText('ZA**** BI**')).toBeVisible()
    // Wrong PIN first: refused, not confirmed
    await page.getByLabel(/Enter your own PIN to confirm/).fill('9999')
    await page.getByRole('button', { name: /Confirm with my PIN/ }).click()
    await expect(page.locator('.note-risk')).toBeVisible()
    await page.getByLabel(/Enter your own PIN to confirm/).fill('1234')
    await page.getByRole('button', { name: /Confirm with my PIN/ }).click()
    await expect(page.getByText('Confirmed: switches when the hold ends')).toBeVisible()
    await shot(page, 'j5-02-wallet-confirmed')

    // Someone else's account: two flagged changes for the officer (one approve, one reject)
    await page.getByRole('button', { name: /Cancel this change/ }).click()
    await page.getByRole('button', { name: /Yes, cancel/ }).click()
    await page.getByRole('button', { name: "Demo: Someone else's" }).click()
    await page.getByRole('button', { name: /Check account and request change/ }).click()
    await expect(page.getByText('Held longer: an officer must check')).toBeVisible()

    const officer = await apiLogin(request, 'kamran')
    await page.setViewportSize({ width: 1280, height: 900 })
    await openAs(page, officer)
    await page.getByRole('tab', { name: /Payout changes/ }).click()
    const card = page.locator('article.detail').first()
    await expect(card).toBeVisible()
    await shot(page, 'j5-03-officer-payouts')
    await card.locator('textarea').fill('Account holder name does not match the claimant.')
    await card.getByRole('button', { name: /Reject/ }).click()
    await expect(page.getByText(/rejected\./)).toBeVisible()

    // Approve path through a fresh flagged joint change (API, then UI approve)
    const z2 = await apiLogin(request, 'zainab')
    const j2 = await apiCall<any>(request, z2, 'POST', `/api/v1/cases/${caseId}/payout-change`, { new_iban: 'PK00MOCK0000000000000012' })
    expect(j2.body.data.status).toBe('flagged')
    await page.getByRole('tab', { name: /Review queue/ }).click()
    await page.getByRole('tab', { name: /Payout changes/ }).click()
    const card2 = page.locator('article.detail').first()
    await card2.locator('textarea').fill('Joint account proof seen (mock).')
    await card2.getByRole('button', { name: /Approve/ }).click()
    await expect(page.getByText(/approved\./)).toBeVisible()
    const after = (await apiCall<any[]>(request, z2, 'GET', `/api/v1/cases/${caseId}/payout-changes`)).body.data
    const approved = after.find((c) => c.id === j2.body.data.id)
    expect(approved.status).toBe('approved')
    expect(approved.confirmed, 'officer approval does not skip her PIN').toBeFalsy()
  })
})
