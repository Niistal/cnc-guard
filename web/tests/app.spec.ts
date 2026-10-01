import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('recorrido completo de la demo local', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Resumen de planta', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva sesión', exact: true }).click();
  await expect(page.getByText('50 con lectura disponible', { exact: true })).toBeVisible({ timeout: 30000 });
  await page.getByRole('button', { name: 'Reproducir demo', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pausar demo', exact: true })).toBeVisible();
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: 'Pausar demo', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reproducir demo', exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/overview-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Máquinas', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Buscar máquina' }).count();
  await page.getByRole('textbox', { name: 'Buscar máquina' }).fill('CNC-001');
  await expect(page.getByRole('button', { name: /CNC-001 Fresado/ })).toBeVisible();
  await page.getByRole('button', { name: 'Analizar y guardar', exact: true }).click();
  await expect(page.locator('.manual-result')).toBeVisible();
  await page.getByRole('link', { name: 'Alertas', exact: true }).click();
  await expect(page.locator('.alert-card').first()).toBeVisible();
  const first = page.locator('.alert-card').first();
  const alertText = await first.locator('.tiny-label').innerText();
  await first.getByRole('textbox').fill('Prueba de demo: inspección visual registrada.');
  await first.getByRole('button', { name: 'Guardar nota' }).click();
  await expect(page.getByText('Prueba de demo: inspección visual registrada.', { exact: true }).first()).toBeVisible();
  await page.locator('.alert-card').filter({ hasText: alertText }).getByRole('button', { name: 'Reconocer alerta' }).click();
  await page.getByLabel('Filtrar alertas').selectOption('acknowledged');
  await expect(page.locator('.alert-card').filter({ hasText: alertText })).toBeVisible();
  await page.getByRole('link', { name: 'Laboratorio de desgaste', exact: true }).click();
  await expect(page.getByText('167', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Estimar desgaste' }).click();
  await expect(page.locator('.wear-result')).toBeVisible();
  await page.screenshot({ path: 'test-results/milling-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Evaluación', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Matriz de confusión' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Descargar informe completo' }).click();
  expect((await download).suggestedFilename()).toContain('ai4i');
  await page.getByRole('button', { name: 'NASA · Desgaste' }).click();
  await expect(page.getByRole('heading', { name: 'Errores por ensayo de test' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('accesibilidad, teclado y adaptación de tamaños', async ({ page }) => {
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    await page.goto('/#overview');
    await expect(page.getByRole('heading', { name: 'Mapa de planta' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    if (width === 320) await page.screenshot({ path: 'test-results/overview-mobile.png', fullPage: true });
  }
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY');
});
