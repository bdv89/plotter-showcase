// capture-tutorial.mjs — refait les captures du tutoriel (public/tutorial/*.png).
//
// Prérequis : une instance de DEV, jamais la prod (dist/ est servi par nginx, cf. PITFALLS).
//   1. backend  : UPLOAD_DIR=<dossier temp> uvicorn main:app --host 127.0.0.1 --port 9299
//   2. frontend : $env:VITE_API_URL='http://127.0.0.1:9299/api'; npx vite --port 5174
//   3. node scripts/capture-tutorial.mjs            (TUTO_URL pour une autre adresse)
//
// Utilise le Chrome installé (playwright-core, channel 'chrome') : aucun navigateur à télécharger.
// Nouveau contexte = localStorage vide = session neuve, donc aucune donnée existante n'est touchée.

import { chromium } from 'playwright-core';
import { mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const OUT = join(here, '..', 'public', 'tutorial');
const SAMPLES = join(here, '..', '..', '..', 'samples', 'samples');
const URL = process.env.TUTO_URL || 'http://127.0.0.1:5174/';

const files = readdirSync(SAMPLES)
  .filter(f => /^Essai_\d+_c\d+\.csv$/.test(f))
  .map(f => join(SAMPLES, f));
if (files.length === 0) throw new Error(`❌ Aucun fichier Essai_*.csv dans ${SAMPLES}`);
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const pause = ms => page.waitForTimeout(ms);

// Capture d'un élément, élargie d'une marge, bornée à la fenêtre et
// éventuellement tronquée en hauteur (maxHeight) quand le bas n'est que du vide.
async function snap(name, selector, { margin = 8, maxHeight = Infinity } = {}) {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`❌ ${name} : ${selector} introuvable`);
  const vp = page.viewportSize();
  const x = Math.max(0, box.x - margin);
  const y = Math.max(0, box.y - margin);
  const clip = {
    x, y,
    width: Math.min(vp.width - x, box.width + 2 * margin),
    height: Math.min(vp.height - y, box.height + 2 * margin, maxHeight),
  };
  await page.screenshot({ path: join(OUT, `${name}.png`), clip });
  console.log(`✅ ${name}.png`);
}

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

  // Thème clair : c'est celui des figures de publication.
  if ((await page.locator('html').getAttribute('data-theme')) !== 'light') {
    await page.locator('.theme-toggle').click();
  }

  // 1. Charger — via l'<input type="file"> caché de Load (pas de sélecteur de fichiers).
  await page.locator('input[type="file"][accept*=".csv"]').setInputFiles(files);
  await page.locator('.file-table tbody tr').nth(files.length - 1).waitFor();
  const headCheck = page.locator('.file-table thead input[type="checkbox"]').first();
  if (!(await headCheck.isChecked())) await headCheck.check();
  await pause(400);
  await snap('01-load', '.page.active', { margin: 0 });

  // 2. Colonnes — X = Position, Y = F. Seul le haut du panneau porte l'information.
  const selector = page.locator('.column-selector');
  await selector.locator('.tab-bar button', { hasText: /^X$/ }).click();
  await selector.locator('.column-item', { hasText: 'Position' }).click();
  await selector.locator('.tab-bar button', { hasText: /^Y \(/ }).click();
  const yItem = selector.locator('.column-item', { hasText: 'F (N)' });
  if (!(await yItem.locator('input').isChecked())) await yItem.click();
  await pause(1200);
  await snap('02-columns', '.column-selector', { margin: 12, maxHeight: 130 });

  // 3. Group by — le morceau « cNNN » (la charge), légende « From series »
  //    (une entrée par groupe), puis la figure colorée.
  await page.locator('.page.active .series-picker .token-chip', { hasText: /^c\d+$/ }).first().click();
  await page.locator('.page.active button', { hasText: /^From series$/ }).first().click();
  await tab('Plot');
  await page.locator('.page.active .js-plotly-plot').waitFor();
  await pause(1500);
  await snap('03-groupby', '.page.active', { margin: 0 });

  // 4. Figure — réglages ouverts.
  await page.locator('.page.active .settings-toggle').click();
  await pause(700);
  await snap('04-figure', '.page.active', { margin: 0 });
  await page.locator('.page.active .settings-toggle').click();

  // 5. Process — débruitage Savitzky-Golay.
  await tab('Process');
  const denoise = page.locator('.proc-enable', { hasText: 'Advanced Denoising' }).locator('input');
  if (!(await denoise.isChecked())) await denoise.check();
  await pause(1500);
  await snap('05-process', '.page.active', { margin: 0 });
  await denoise.uncheck();

  // 6. Extract — Max de F (N), puis statistiques par population.
  await tab('Extract');
  const selects = page.locator('.extract-fields select');
  await selectByText(selects.nth(0), /^F \(N\)$/);
  await selectByText(selects.nth(1), /^max$/);
  await page.locator('.apply-button').click();
  await page.locator('.col-extracted').first().waitFor();
  await pause(1200);
  await snap('06-extract', '.page.active', { margin: 0 });

  // 7. Enregistrer — la zone des boutons de l'en-tête (Tuto, Save, Save As, Load).
  await snap('07-save', '.header-actions', { margin: 10 });
} finally {
  await browser.close();
}
