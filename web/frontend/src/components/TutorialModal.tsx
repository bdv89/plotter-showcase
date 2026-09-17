import { useEffect, useState, type ReactNode } from 'react';

// Captures réelles dans public/tutorial/, servies sous la base du build
// (/plotter/, /plotter-exp/ ou / en dev) — même principe que MCP_URL dans HelpModal.
// Après un changement d'interface, les refaire : node scripts/capture-tutorial.mjs
const shot = (name: string) => `${import.meta.env.BASE_URL}tutorial/${name}.png`;

interface Props {
  open: boolean;
  onClose: () => void;
}

interface Step {
  title: string;
  image: string;
  alt: string;
  body: ReactNode;
}

const STEPS: Step[] = [
  {
    title: 'Charger les fichiers',
    image: shot('01-load'),
    alt: "Onglet Data avec huit fichiers d'essai chargés et cochés",
    body: (
      <>
        <p>
          Cliquez sur <strong>Load</strong> en haut à droite, ou glissez vos fichiers directement
          sur ce bouton.
        </p>
        <ul>
          <li>Formats : <code>.csv</code>, <code>.tsv</code>, <code>.xlsx</code>, <code>.xls</code> — jusqu'à 500 Mo par fichier, 300 fichiers.</li>
          <li>Les décimales à la virgule (<code>0,93</code>) sont converties automatiquement.</li>
          <li>Cochez les fichiers à tracer : case d'en-tête pour tout cocher, ou <kbd>Ctrl</kbd>+<kbd>A</kbd>.</li>
        </ul>
        <p>Exemple utilisé ici : <code>Essai_70_c100.csv</code> … <code>Essai_71_c10000.csv</code>, colonnes <code>Position (mm)</code> et <code>F (N)</code>.</p>
      </>
    ),
  },
  {
    title: 'Choisir les colonnes',
    image: shot('02-columns'),
    alt: 'Panneau des colonnes avec Position (mm) en X et F (N) en Y',
    body: (
      <>
        <p>Le panneau de droite liste les colonnes communes aux fichiers cochés.</p>
        <ul>
          <li>Onglet <strong>X</strong> : l'axe horizontal, ici <code>Position (mm)</code>.</li>
          <li>Onglet <strong>Y</strong> : une ou plusieurs courbes, ici <code>F (N)</code>.</li>
          <li>Onglet <strong>Y2</strong> (facultatif) : un second axe vertical à droite.</li>
        </ul>
        <p>Avec <strong>Auto-plot</strong> coché, le graphe se trace dès qu'un X et un Y sont choisis.</p>
      </>
    ),
  },
  {
    title: 'Regrouper les échantillons',
    image: shot('03-groupby'),
    alt: 'Barre Group by avec le morceau c100 sélectionné et les courbes colorées par charge',
    body: (
      <>
        <p>
          <strong>Group by</strong> découpe un nom d'exemple en morceaux. Cliquez sur celui qui
          distingue vos conditions : ici <code>c100</code>, la charge.
        </p>
        <ul>
          <li><code>Essai_70_c100</code> et <code>Essai_71_c100</code> prennent la même couleur…</li>
          <li>… et forment la même <strong>population</strong> pour les statistiques de l'étape 6.</li>
          <li><strong>Legend → From series</strong> : une seule entrée de légende par groupe.</li>
          <li><strong>Auto</strong> revient à une couleur par fichier. Raccourci : <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>1…9</kbd>.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Soigner la figure',
    image: shot('04-figure'),
    alt: 'Onglet Plot avec la figure et le panneau de réglages ouvert',
    body: (
      <>
        <p>L'onglet <strong>Plot</strong> part d'un style de publication : fond blanc, cadre fermé, graduations extérieures.</p>
        <ul>
          <li>L'engrenage ouvre les réglages : titre, polices, unités, limites d'axes, légende, taille, preset <code>.json</code>.</li>
          <li>Cliquez sur un titre pour le modifier ; clic droit sur un axe ou la légende pour son réglage.</li>
          <li><strong>Zoom</strong>, <strong>Pan</strong>, <strong>Rect</strong>, <strong>Line</strong>, <strong>Arrow</strong>, <strong>Text</strong> pour annoter.</li>
          <li><strong>SVG</strong> (vectoriel, pour l'article) ou <strong>PNG</strong> haute résolution pour exporter.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Nettoyer le signal',
    image: shot('05-process'),
    alt: 'Onglet Process avec Advanced Denoising activé en Savitzky-Golay',
    body: (
      <>
        <p>Dans <strong>Process</strong>, cochez un traitement : le graphe se met à jour aussitôt.</p>
        <ul>
          <li><strong>Outlier Removal</strong> → <strong>Smoothing</strong> → <strong>Advanced Denoising</strong> (Savitzky-Golay, Median, Wavelet, FFT) → <strong>Baseline Correction</strong> (SNIP, AsLS, arPLS) → <strong>Normalize</strong> : ils s'appliquent toujours dans cet ordre.</li>
          <li>Vos fichiers ne sont jamais modifiés et l'axe X n'est jamais touché.</li>
          <li><strong>Reset</strong> désactive tout.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Extraire et comparer',
    image: shot('06-extract'),
    alt: 'Onglet Extract avec le maximum de F (N) par fichier et les statistiques par population',
    body: (
      <>
        <p>L'onglet <strong>Extract</strong> calcule une valeur par fichier, puis les statistiques par population.</p>
        <ul>
          <li><strong>Column to analyze</strong> : <code>F (N)</code> ; <strong>Operation</strong> : <code>Max</code>.</li>
          <li><strong>Restrict to X interval</strong> (facultatif) : ne mesurer que la zone d'intérêt.</li>
          <li><strong>Extract</strong> remplit le tableau <strong>Values</strong>, une ligne par fichier.</li>
          <li><strong>Populations</strong> regroupe selon le Group by de l'étape 3 ; les puces <strong>Stats</strong> choisissent n, mean, SD, CV%, min, max, med.</li>
          <li><strong>Re-extract</strong> rejoue les mêmes réglages sur des fichiers ajoutés ensuite ; <strong>Copy TSV</strong> colle le tableau dans Excel.</li>
        </ul>
      </>
    ),
  },
  {
    title: 'Enregistrer son travail',
    image: shot('07-save'),
    alt: 'En-tête avec les boutons Save, Save As et Load',
    body: (
      <>
        <p><strong>Save As</strong> enregistre un <strong>pool</strong> <code>.db</code> : fichiers, colonnes, couleurs, traitements, annotations et extractions.</p>
        <ul>
          <li><strong>Save</strong> réécrit ensuite au même emplacement.</li>
          <li>Rechargez le <code>.db</code> avec <strong>Load</strong> : la figure revient à l'identique, chez vous ou chez un collègue.</li>
          <li>Votre session est aussi conservée sur le serveur : fermer l'onglet ne perd rien.</li>
        </ul>
      </>
    ),
  },
];

export function TutorialModal({ open, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const step = STEPS[index];
  const isLast = index === STEPS.length - 1;

  // ←/→ changent d'étape. Écouté en capture et arrêté ici : sinon les flèches
  // déplaceraient aussi la ligne active de la table Data, cachée derrière le tuto.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') setIndex(i => Math.min(i + 1, STEPS.length - 1));
      else if (e.key === 'ArrowLeft') setIndex(i => Math.max(i - 1, 0));
      else return;
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-tutorial" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Tutoriel · pas à pas</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="tutorial-body">
          <ol className="tutorial-steps">
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <button className={i === index ? 'active' : ''} onClick={() => setIndex(i)}>
                  <span className="tutorial-step-num">{i + 1}</span>
                  {s.title}
                </button>
              </li>
            ))}
          </ol>

          <div className="tutorial-content">
            <h4>{step.title}</h4>
            {step.body}
            <a className="tutorial-shot" href={step.image} target="_blank" rel="noreferrer" title="Ouvrir en taille réelle">
              <img src={step.image} alt={step.alt} loading="lazy" />
            </a>
          </div>
        </div>

        <div className="tutorial-nav">
          <button onClick={() => setIndex(i => i - 1)} disabled={index === 0}>← Précédent</button>
          <span className="tutorial-progress">Étape {index + 1} / {STEPS.length}</span>
          {isLast
            ? <button onClick={onClose}>Terminer</button>
            : <button onClick={() => setIndex(i => i + 1)}>Suivant →</button>}
        </div>
      </div>
    </div>
  );
}
