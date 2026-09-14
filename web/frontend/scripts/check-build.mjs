// Contrôle du dist/ après chaque `npm run build` (branché en npm `postbuild`,
// donc actif AUSSI sur un build lancé à la main). Rejette les deux pannes qui
// ne se voient pas en dev et qui ont chacune cassé la prod une fois :
//
//   1. base (--base) et URL d'API (VITE_API_URL) incohérentes -> la page
//      s'affiche mais TOUS les appels partent en 404. Panne silencieuse.
//   2. un import nu en tête de bundle -> le module ne charge pas, page blanche.
//
// Et AVERTIT sur la troisieme, qui ne se repare pas toute seule :
//
//   3. un build de dev (base /) ecrase le dist/ que le service prod sert en
//      direct -> la prod passe en page blanche + API 404 jusqu'au prochain
//      build aux flags prod. dist/ n'etant pas versionne, l'ancien est perdu.
//
// Voir PITFALLS.md. Sortie en code 1 = build rejeté.

import { readFileSync, readdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const DIST = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const fail = msg => { console.error(`\n❌ BUILD REJETE\n${msg}\n`); process.exit(1); };

const html = readFileSync(join(DIST, 'index.html'), 'utf8');

// La base telle que vite l'a écrite dans index.html : "/plotter/assets/…" -> "/plotter/"
const m = html.match(/src="(.*)assets\/index-[^"]+\.js"/);
if (!m) fail(`Aucun <script src=".../assets/index-*.js"> dans dist/index.html.`);
const base = m[1] || '/';

const entry = readdirSync(join(DIST, 'assets')).find(f => /^index-.*\.js$/.test(f));
if (!entry) fail('Aucun bundle dist/assets/index-*.js.');
const js = readFileSync(join(DIST, 'assets', entry), 'utf8');

// --- 1. cohérence base <-> API -------------------------------------------
// Cohérence INTERNE : rien n'est codé en dur, la règle vaut pour /plotter/,
// /plotter-exp/ et la racine. client.ts retombe sur '/api' sans VITE_API_URL.
const expectedApi = `${base}api`.replace('//', '/');
if (base !== '/' && !js.includes(expectedApi)) {
  fail(
    `  base (index.html) : ${base}\n` +
    `  api  (bundle)     : /api          <-- attendu ${expectedApi}\n\n` +
    `  VITE_API_URL manquant : la page s'affichera, mais tous les appels\n` +
    `  API partiront en 404. Relancer :\n\n` +
    `      $env:VITE_API_URL='${expectedApi}'; npm run build -- --base=${base}`,
  );
}

// --- 2. import nu (page blanche) -----------------------------------------
if (/^\s*import\s/.test(js)) {
  const bare = js.match(/^\s*import\s[^;]*/)?.[0] ?? '';
  fail(
    `  ${entry} commence par un import nu :\n` +
    `      ${bare}\n\n` +
    `  Le navigateur ne sait pas resoudre un specifier nu : le module entier\n` +
    `  echoue -> page blanche. Chercher un import qui tire un graphe Node\n` +
    `  (typiquement 'plotly.js' au lieu de 'plotly.js/dist/plotly').`,
  );
}

// --- 3. dist ecrase sous le nez d'un service qui le sert ------------------
// Le backend sert FRONTEND_DIST (= ce dossier) en direct : un build base '/'
// laisse la prod avec des assets introuvables. On ne peut plus l'annuler ici
// (le dist est deja ecrit) — on le DIT, avec la commande de reparation.
if (base === '/' && process.platform === 'win32') {
  const running = ['CSVPlotter', 'CSVPlotter_Exp'].filter(name => {
    try {
      return /STATE\s+:\s+4\s+RUNNING/.test(execFileSync('sc', ['query', name], { encoding: 'utf8' }));
    } catch {
      return false;   // service absent = rien a signaler
    }
  });
  if (running.length > 0) {
    const sub = running.includes('CSVPlotter') ? '/plotter/' : '/plotter-exp/';
    console.warn(
      `
⚠️  DIST ECRASE — service(s) ${running.join(', ')} en cours d'execution

` +
      `  Ce build est en base '/', mais le backend sert CE dossier dist/ derriere
` +
      `  nginx en sous-chemin. Les assets sont maintenant introuvables : page
` +
      `  blanche + API en 404, et l'ancien dist n'est pas versionne.

` +
      `  Rebuild aux flags de deploiement pour reparer :

` +
      `      $env:VITE_API_URL='${sub}api'; npm run build -- --base=${sub}
`,
    );
  }
}

console.log(`✓ build coherent — base ${base}, api ${base === '/' ? '/api' : expectedApi}, pas d'import nu`);
