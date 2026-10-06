// capture-showcase.mjs — refait les captures de la vitrine (docs/screenshots/*.png)
// à partir du jeu de données SYNTHÉTIQUE examples/demo-data (examples/make_demo_data.py).
//
// Même prérequis que capture-tutorial.mjs : une instance de DEV, jamais la prod.
//   1. backend  : UPLOAD_DIR=<dossier temp> uvicorn main:app --host 127.0.0.1 --port 9299
//   2. frontend : $env:VITE_API_URL='http://127.0.0.1:9299/api'; npx vite --port 5174
//   3. node scripts/capture-showcase.mjs            (TUTO_URL pour une autre adresse)

import { chromium } from 'playwright-core';
import { mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = join(here, '..', '..', '..');
const OUT = join(ROOT, 'docs', 'screenshots');
const SAMPLES = join(ROOT, 'examples', 'demo-data');
const URL = process.env.TUTO_URL || 'http://127.0.0.1:5174/';

const files = readdirSync(SAMPLES).filter(f => f.endsWith('.csv')).map(f => join(SAMPLES, f));
if (files.length === 0) throw new Error(`❌ Aucun CSV dans ${SAMPLES} — lancer examples/make_demo_data.py`);
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
page.on('requestfailed', r => console.log(`❌ ${r.method()} ${r.url()} — ${r.failure()?.errorText}`));
page.on('console', m => m.type() === 'error' && console.log(`❌ console: ${m.text()}`));
const pause = ms => page.waitForTimeout(ms);
const shot = async name => { await page.screenshot({ path: join(OUT, `${name}.png`) }); console.log(`✅ ${name}.png`); };
const tab = label => page.locator('.page-nav button', { hasText: new RegExp(`^${label}$`) }).click();

async function selectByText(select, re) {
  const value = await select.evaluate(
    (el, src) => [...el.options].find(o => new RegExp(src, 'i').test(o.textContent.trim()))?.value,
    re.source,
  );
  if (value == null) throw new Error(`❌ option ${re} introuvable`);
  await select.selectOption(value);
}

try {
  await page.goto(URL, { waitUntil: 'networkidle' });
  if ((await page.locator('html').getAttribute('data-theme')) !== 'light') {
    await page.locator('.theme-toggle').click();
  }

  // 1. Data — 9 fichiers hétérogènes (deux formats d'export), X = Time, Y = Stress, Group by = pH.
  await page.locator('input[type="file"][accept*=".csv"]').setInputFiles(files);
  await page.locator('.file-table tbody tr').nth(files.length - 1).waitFor();
  const headCheck = page.locator('.file-table thead input[type="checkbox"]').first();
  if (!(await headCheck.isChecked())) await headCheck.check();
  const selector = page.locator('.column-selector');
  await selector.locator('.tab-bar button', { hasText: /^X$/ }).click();
  await selector.locator('.column-item', { hasText: 'Time' }).click();
  await selector.locator('.tab-bar button', { hasText: /^Y \(/ }).click();
  for (const item of await selector.locator('.column-item').all()) {
    const want = (await item.textContent()).includes('Stress');
    if ((await item.locator('input').isChecked()) !== want) await item.click();
  }
  await page.locator('.page.active .series-picker .token-chip', { hasText: /^pH/ }).first().click();
  await page.locator('.page.active button', { hasText: /^From series$/ }).first().click();
  await pause(1200);
  await shot('01-data');

  // 2-3. Mise en forme centralisée — titres et unités saisis UNE fois dans le panneau de réglages,
  //      appliqués à toutes les courbes, sauvegardés dans le pool et exportables en preset .json.
  await tab('Plot');
  await page.locator('.page.active .js-plotly-plot').waitFor();
  await page.locator('.page.active .settings-toggle').click();
  await pause(500);
  const field = (section, label) => page.locator(`[data-section="${section}"] .field`, { hasText: new RegExp(`^${label}`) }).locator('input').first();
  await field('title', 'Title Text').fill('Internal stress of electroless Ni-P (synthetic demo data)');
  // Unité dans le titre d'axe (convention de publication) plutôt que dans le champ Unit.
  await field('xaxis', 'Title').fill('Deposition time (min)');
  await field('yaxis', 'Title').fill('Internal stress (MPa)');
  // Plusieurs changements de style rapprochés laissent les graduations Plotly sur la plage par
  // défaut (−1…6) alors que les courbes restent justes (bug connu, cf. TODO.md) :
  // on force un recalcul des traces en décochant/recochant un fichier.
  await page.locator('.page.active .settings-toggle').click();
  await tab('Data');
  const first = page.locator('.file-table tbody tr input[type="checkbox"]').first();
  await first.uncheck(); await pause(800); await first.check(); await pause(800);
  await tab('Plot');
  await pause(1500);
  await page.locator('.page.active .settings-toggle').click();
  await page.locator('[data-section="xaxis"]').scrollIntoViewIfNeeded();
  await pause(700);
  await shot('03-plot-settings');
  await page.locator('.page.active .settings-toggle').click();
  await pause(1200);
  await shot('02-plot');

  // 4. Process — débruitage Savitzky-Golay.
  await tab('Process');
  const denoise = page.locator('.proc-enable', { hasText: 'Advanced Denoising' }).locator('input');
  if (!(await denoise.isChecked())) await denoise.check();
  await pause(1500);
  await shot('04-process');
  await denoise.uncheck();

  // 5. Extract — contrainte finale (Y at max(X)) par fichier + statistiques par population.
  await tab('Extract');
  const selects = page.locator('.extract-fields select');
  await selectByText(selects.nth(0), /^Stress/);
  await selectByText(selects.nth(1), /^Y at max\(X\)$/);
  await selectByText(selects.nth(2), /^Time/);
  await page.locator('.page.active input[placeholder*="("]').fill('Final stress (MPa)');
  await page.locator('.apply-button').click();
  await page.locator('.col-extracted').first().waitFor();
  await pause(1200);
  await shot('05-extract');

  // 6. Pilotage par une IA — la commande MCP affichée dans l'aide.
  await page.locator('.help-button', { hasText: /^\?$/ }).click();
  await page.locator('.mcp-install').waitFor();
  await page.locator('.mcp-install').scrollIntoViewIfNeeded();
  await pause(500);
  await shot('06-mcp-help');
} finally {
  await browser.close();
}
