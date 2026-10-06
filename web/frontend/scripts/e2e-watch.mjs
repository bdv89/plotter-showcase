// e2e-watch.mjs — test de bout en bout du suivi de dossier (api/watch.py + FolderWatch.tsx).
//
// Simule un banc qui écrit dans le partage : fichiers déjà présents au démarrage, nouveau
// fichier pendant le suivi (la recette d'extraction doit être rejouée), fichier qui grossit
// avec une dernière ligne incomplète (rechargé en direct, ligne coupée ignorée).
//
// Prérequis : une instance de DEV dont le SHARE_PATH contient un dossier vide PEO_bench/.
//   1. backend  : $env:SHARE_PATH='<partage>'; $env:UPLOAD_DIR='<temp>'; uvicorn main:app --port 9299
//   2. frontend : $env:VITE_API_URL='http://127.0.0.1:9299/api'; npx vite --port 5174
//   3. node scripts/e2e-watch.mjs <partage> [../../docs/screenshots]   (le 2e argument refait 07-folder-watch.png)
import { chromium } from 'playwright-core';
import { readFileSync, writeFileSync, appendFileSync, copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const DEMO = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'examples', 'demo-data');
const SHARE = process.argv[2], OUT = process.argv[3];
if (!SHARE) throw new Error('usage: node scripts/e2e-watch.mjs <SHARE_PATH> [screenshot dir]');
const BENCH = join(SHARE, 'PEO_bench');
const b = await chromium.launch({ channel: 'chrome', headless: true });
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on('console', m => m.type() === 'error' && console.log('❌ console', m.text()));
const pause = ms => p.waitForTimeout(ms);
const rows = () => p.locator('.page-data .file-table tbody tr').count();
const points = () => p.evaluate(() => { const g = document.querySelector('.js-plotly-plot'); return g?.data?.map(t => t.x.length) ?? []; });
const check = (cond, msg) => { console.log(cond ? '✅' : '❌', msg); if (!cond) process.exitCode = 1; };
try {
  await p.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' });
  if ((await p.locator('html').getAttribute('data-theme')) !== 'light') await p.locator('.theme-toggle').click();
  copyFileSync(join(DEMO, 'NiP_pH4.5_r1.csv'), join(BENCH, 'NiP_pH4.5_r1.csv'));
  copyFileSync(join(DEMO, 'NiP_pH5.0_r1.csv'), join(BENCH, 'NiP_pH5.0_r1.csv'));
  await p.locator('.folder-watch button', { hasText: /^Watch$/ }).click();
  await p.locator('.watch-panel select').waitFor();
  const opts = await p.locator('.watch-panel option').allTextContents();
  check(opts.includes('PEO_bench') && opts.includes('other'), `folders listed: ${opts.join(', ')}`);
  await p.locator('.watch-panel select').selectOption('PEO_bench');
  await p.locator('.watch-panel button', { hasText: 'Start' }).click();
  await p.locator('.page-data .file-table tbody tr').nth(1).waitFor({ timeout: 8000 });
  const n = await rows();
  check(n === 2, `existing files loaded on start: ${n} row(s)`);

  const sel = p.locator('.column-selector');
  await sel.locator('.tab-bar button', { hasText: /^X$/ }).click();
  await sel.locator('.column-item', { hasText: 'Time' }).click();
  await sel.locator('.tab-bar button', { hasText: /^Y \(/ }).click();
  for (const it of await sel.locator('.column-item').all()) { const w = (await it.textContent()).includes('Stress'); if ((await it.locator('input').isChecked()) !== w) await it.click(); }
  await p.locator('.page-nav button', { hasText: /^Extract$/ }).click();
  const s = p.locator('.extract-fields select');
  await s.nth(0).selectOption({ label: 'Stress (MPa)' });
  await s.nth(1).selectOption({ label: 'Y at max(X)' });
  await s.nth(2).selectOption({ label: 'Time (min)' });
  await p.locator('.page.active input[placeholder*="("]').fill('Final stress (MPa)');
  await p.locator('.apply-button').click();
  await pause(1500);

  // New file arrives while watching
  copyFileSync(join(DEMO, 'NiP_pH5.5_r1.csv'), join(BENCH, 'NiP_pH5.5_r1.csv'));
  await p.locator('.page-data .file-table tbody tr').nth(2).waitFor({ state: 'attached', timeout: 8000 });
  await pause(2500);
  const vals = await p.locator('.page-extract tbody tr').filter({ hasText: 'NiP_pH5.5_r1' }).first().textContent();
  check(/\d/.test(vals.replace('NiP_pH5.5_r1.csv', '')), `recipe replayed on new file: "${vals.trim()}"`);

  // Growing file: written in chunks, last line incomplete
  await p.locator('.page-nav button', { hasText: /^Plot$/ }).click();
  const lines = readFileSync(join(DEMO, 'NiP_pH5.5_r2.csv'), 'utf8').split('\n');
  const live = join(BENCH, 'live_run.csv');
  writeFileSync(live, lines.slice(0, 40).join('\n') + '\n' + lines[40].slice(0, 4));
  await pause(5000);
  const before = await points();
  check(before.length === 4 && before.includes(39), `growing file plotted with complete lines only: ${before}`);
  appendFileSync(live, lines[40].slice(4) + '\n' + lines.slice(41, 120).join('\n') + '\n');
  await pause(5000);
  const after = await points();
  check(after.includes(119), `growing file reloaded live: ${after}`);
  if (OUT) { mkdirSync(OUT, { recursive: true }); await p.screenshot({ path: join(OUT, '07-folder-watch.png') }); }
  await p.locator('.page-nav button', { hasText: /^Extract$/ }).click();
  await pause(500);
  // Stop
  await p.locator('.folder-watch button.watching').click();
  check(await p.locator('.folder-watch button', { hasText: /^Watch$/ }).count() === 1, 'watch stopped');
} finally { await b.close(); }
