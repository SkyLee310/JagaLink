import { defineConfig } from '@playwright/test'

/**
 * Browser checks against a running app (TS §8). Locally, PW_CHANNEL=msedge or chrome uses an
 * installed browser, so nothing is downloaded; E2E_BASE_URL and E2E_API_URL point the same
 * checks at the deployed app.
 */
export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    channel: process.env.PW_CHANNEL || undefined,
    // The guardhouse PC (D-67).
    viewport: { width: 1366, height: 768 },
    trace: 'retain-on-failure',
  },
})
