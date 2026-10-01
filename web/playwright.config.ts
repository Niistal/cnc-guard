import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:8000', headless: true,
    viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: '..\\.venv\\Scripts\\python.exe -m cnc_guard.cli serve',
    url: 'http://127.0.0.1:8000/api/v1/health', reuseExistingServer: true, timeout: 60000 },
});
