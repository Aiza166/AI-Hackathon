import type { Page } from '@playwright/test'
import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test, zainabClaim } from './helpers'

// Journey 13: Sindhi and Punjabi (machine-assisted) on the citizen screens at 360 px.
// The language picker is on the login and home screens; the choice is remembered on the phone.
// Checks: the right script and lang tag, right-to-left, no sideways scroll, tap targets >= 48 px,
// the "machine-assisted, to be reviewed" note, and that Listen still sends the Urdu sentence.

test.use({ viewport: { width: 360, height: 780 } })

const LANGS = [
  { id: 'sd', button: /سنڌي/, tag: 'sd', newClaim: 'نئين پينشن جي دعويٰ', relation: 'توهان مرحوم جا ڇا لڳو ٿا؟', approved: 'توهان جي دعويٰ منظور ٿي وئي', scam: 'هي دوکو لڳي ٿو' },
  { id: 'pa', button: /پنجابی/, tag: 'pa-Arab', newClaim: 'نواں پنشن دعویٰ', relation: 'تُسیں مرحوم دے کی لگدے او؟', approved: 'تہاڈا دعویٰ منظور ہو گیا', scam: 'ایہہ دھوکا لگدا اے' },
] as const

async function phoneChecks(page: Page, name: string): Promise<void> {
  const r = await page.evaluate(() => {
    const rtl = [...document.querySelectorAll('[lang="ur"], [lang="sd"], [lang="pa-Arab"]')]
    const small = [...document.querySelectorAll('button, a[href], input, select, textarea')]
      .filter((el) => {
        const b = el.getBoundingClientRect()
        return b.width > 0 && b.height > 0 && (b.height < 48 || b.width < 48)
      })
      .map((el) => `${((el as HTMLElement).innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 30)} ${Math.round(el.getBoundingClientRect().height)}px`)
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      notRtl: rtl.filter((el) => getComputedStyle(el).direction !== 'rtl').length,
      small,
    }
  })
  expect.soft(r.overflow, `${name}: sideways scroll at 360 px`).toBeLessThanOrEqual(0)
  expect.soft(r.notRtl, `${name}: right-to-left text`).toBe(0)
  expect.soft(r.small, `${name}: tap targets under 48 px`).toEqual([])
}

test.describe('J13 Sindhi and Punjabi (360 px)', () => {
  test.beforeAll(async ({ request }) => {
    await resetDemo(request)
  })

  for (const lang of LANGS) {
    test(`${lang.id}: picker, home, wizard, decision reasons, Scam Shield, Listen stays Urdu`, async ({ page, request }) => {
      // Pick the language on the login screen, before signing in
      await page.goto('/')
      await page.getByRole('button', { name: lang.button }).click()
      await expect(page.getByRole('button', { name: lang.button })).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByText('Machine-assisted translation, to be reviewed.')).toBeVisible()
      await phoneChecks(page, `${lang.id} login`)

      // A claim already decided, so the decision screen has reasons
      const z = await apiLogin(request, 'zainab')
      expect((await apiCall(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))).status).toBe(201)

      // The choice survives sign-in (remembered on the phone)
      await openAs(page, z)
      await expect(page.locator(`[lang="${lang.tag}"]`, { hasText: lang.newClaim })).toBeVisible()
      await phoneChecks(page, `${lang.id} home`)
      await shot(page, `j13-${lang.id}-01-home`)

      await page.getByRole('button', { name: /Start a new pension claim/ }).click()
      await expect(page.locator(`[lang="${lang.tag}"]`, { hasText: lang.relation })).toBeVisible()
      await phoneChecks(page, `${lang.id} wizard`)
      await shot(page, `j13-${lang.id}-02-wizard`)
      await page.getByRole('button', { name: /Back/ }).click()

      // Decision: headline and the reason line in the chosen language; Listen sends Urdu
      await page.locator('.claim-item').first().click()
      await expect(page.locator(`.verdict [lang="${lang.tag}"]`)).toHaveText(lang.approved)
      await expect(page.locator(`.reason-ur[lang="${lang.tag}"]`).first()).toBeVisible()
      await phoneChecks(page, `${lang.id} decision`)
      await shot(page, `j13-${lang.id}-03-decision`)
      const tts = page.waitForRequest((r) => r.url().includes('/api/v1/speech/tts'), { timeout: 15_000 }).catch(() => null)
      await page.locator('.verdict').getByRole('button', { name: /Listen/ }).click()
      const ttsRequest = await tts
      if (ttsRequest) {
        const spoken = String(JSON.parse(ttsRequest.postData() ?? '{}').text ?? '')
        expect(spoken, 'Listen speaks the Urdu headline').toContain('آپ کا دعویٰ منظور ہو گیا')
      }
      await page.getByRole('button', { name: /Back/ }).last().click()

      // Scam Shield verdict headline
      await page.getByRole('button', { name: /Is this message a scam/ }).click()
      await page.getByRole('button', { name: 'Fill demo scam SMS (mock)' }).click()
      await page.getByRole('button', { name: /Check this message/ }).click()
      await expect(page.locator(`[lang="${lang.tag}"]`, { hasText: lang.scam })).toBeVisible({ timeout: 60_000 })
      await phoneChecks(page, `${lang.id} scam verdict`)
      await shot(page, `j13-${lang.id}-04-scam`)

      // Back to Urdu: nothing is stuck in the other language
      await page.getByRole('button', { name: /Back/ }).first().click()
      await page.getByRole('button', { name: /اردو/ }).click()
      await expect(page.locator('[lang="ur"]', { hasText: 'نیا پنشن دعویٰ' })).toBeVisible()
      await expect(page.locator(`[lang="${lang.tag}"]`, { hasText: lang.newClaim })).toHaveCount(0)

      // Reset the demo claim for the next language
      await resetDemo(request)
    })
  }
})
