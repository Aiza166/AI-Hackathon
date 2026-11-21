import { defineConfig } from '@playwright/test'

// E2E journeys for the Sahara prototype. LOCALHOST ONLY: never point this at the live site.
// Start the stack first (see README.md in this folder), then: npm test
const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5180'

if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(BASE_URL)) {
  throw new Error(`E2E_BASE_URL must be a localhost URL, got ${BASE_URL}`)
}

export default defineConfig({
  testDir: './tests',
  outputDir: './results/artifacts',
  fullyParallel: false,
  workers: 1, // journeys share one demo database and reset it
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['json', { outputFile: './results/report.json' }], ['html', { outputFolder: './results/html', open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    hasTouch: true,
    locale: 'en-GB',
    timezoneId: 'Asia/Karachi',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 20_000,
  },
})
