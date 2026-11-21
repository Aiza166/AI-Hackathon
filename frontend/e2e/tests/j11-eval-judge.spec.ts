import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test } from './helpers'

// Journey 11: the staff Evaluation page and the admin Judge console.
// Admin: evaluation charts (keyboard readout, table view), then breaks NADRA and Jev from the console
// and sees both in the live status and the activity feed. Officer: Evaluation tab, no Judge console.

test.use({ viewport: { width: 1280, height: 900 }, hasTouch: false })

test.describe('J11 Evaluation page and Judge console', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('admin reads the evaluation and breaks things from the console', async ({ page, request, consoleErrors }) => {
    const admin = await apiLogin(request, 'admin')
    await openAs(page, admin)

    await page.getByRole('tab', { name: 'Evaluation' }).click()
    await expect(page.getByRole('heading', { name: 'Evaluation' })).toBeVisible()
    await expect(page.getByText('Why 0.95:')).toBeVisible()
    await expect(page.getByText('Synthetic test set').first()).toBeVisible()
    const chart = page.getByRole('slider', { name: /Total cost = 20 x wrong approvals/ })
    await chart.focus()
    const readout = page.locator('.viz-readout').first()
    await expect(readout).toContainText('0.95')
    await page.keyboard.press('Home')
    await expect(readout).toContainText('0.50')
    await expect(page.getByRole('cell', { name: /gpt-5-mini/ }).first()).toBeVisible()
    await page.getByText('Show as table').first().click()
    await expect(page.getByRole('columnheader', { name: 'Wrong approvals' })).toBeVisible()
    await shot(page, 'j11-01-evaluation', true)

    await page.getByRole('tab', { name: 'Judge console' }).click()
    await expect(page.getByText('PROTOTYPE / DEMO CONTROLS')).toBeVisible()
    await expect(page.getByText('Intact')).toBeVisible()

    const identity = page.getByRole('group', { name: 'NADRA identity mode' })
    await identity.getByRole('button', { name: 'timeout' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'NADRA identity: timeout' })).toBeVisible()
    await expect(identity.getByRole('button', { name: 'timeout' })).toHaveAttribute('aria-pressed', 'true')

    await page.getByRole('button', { name: 'Simulate outage of Jev (jev-1.14.0)' }).click()
    await expect(page.getByRole('button', { name: 'Restore Jev (jev-1.14.0)' })).toBeVisible()
    await expect(page.getByText('simulated outage')).toBeVisible()

    await expect(page.getByRole('cell', { name: 'MOCK_FAULT_SET' }).first()).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('cell', { name: 'identity: timeout' }).first()).toBeVisible()
    await shot(page, 'j11-02-judge-console', true)

    // A claim filed now goes to an officer (identity down), visible in the feed.
    const zainab = await apiLogin(request, 'zainab')
    const claim = await apiCall<any>(request, zainab, 'POST', '/api/v1/cases', {
      claimant_cnic: '9000000000022', claimant_name: 'Zainab Bibi', claimant_dob: '1962-06-01', relation_claimed: 'widow',
      deceased_cnic: '9000000000011', deceased_name: 'Muhammad Aslam', payout_iban: 'PK00MOCK0000000000000001',
      documents: ['death_certificate', 'claimant_cnic', 'frc', 'nikah_nama'],
    })
    expect(claim.body.data.latest_decision.reason_codes).toContain('SERVICE_UNAVAILABLE')
    await expect(page.getByRole('cell', { name: /SERVICE_UNAVAILABLE/ }).first()).toBeVisible({ timeout: 15_000 })

    await page.getByRole('button', { name: 'Restore Jev (jev-1.14.0)' }).click()
    await identity.getByRole('button', { name: 'ok' }).click()
    await expect(identity.getByRole('button', { name: 'ok' })).toHaveAttribute('aria-pressed', 'true')
    expect(consoleErrors).toEqual([])
  })

  test('officer sees Evaluation but not the Judge console; console API refuses', async ({ page, request }) => {
    const officer = await apiLogin(request, 'kamran')
    await openAs(page, officer)
    await expect(page.getByRole('tab', { name: 'Evaluation' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Judge console' })).toHaveCount(0)
    const denied = await apiCall(request, officer, 'GET', '/api/v1/admin/judge/status')
    expect(denied.status).toBe(403)
  })

  test('evaluation and console fit a 390 px phone without sideways scroll', async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const admin = await apiLogin(request, 'admin')
    await openAs(page, admin)
    for (const tab of ['Evaluation', 'Judge console']) {
      await page.getByRole('tab', { name: tab }).click()
      await page.waitForLoadState('networkidle')
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      expect(overflow, `${tab} horizontal overflow`).toBeLessThanOrEqual(1)
    }
  })
})
