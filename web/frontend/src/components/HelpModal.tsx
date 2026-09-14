import { useState } from 'react';

import { copyToClipboard } from '../utils/clipboard';

// L'URL suit la base du build (/plotter/, /plotter-exp/ ou / en dev) : une seule
// commande valable quel que soit le déploiement, sans rien coder en dur.
const MCP_URL = `${window.location.origin}${import.meta.env.BASE_URL}mcp`;
const MCP_COMMAND = `claude mcp add --transport http plotter ${MCP_URL}`;

interface Props {
  open: boolean;
  onClose: () => void;
}

const SECTIONS: { title: string; rows: { keys: string[]; action: string }[] }[] = [
  {
    title: 'Onglets',
    rows: [{ keys: ['Alt', '1…5'], action: 'Data / Plot / Process / Extract / Metrics' }],
  },
  {
    title: 'Recherche',
    rows: [
      { keys: ['/'], action: 'Focus la recherche' },
      { keys: ['Échap'], action: 'Sortir de la recherche' },
    ],
  },
  {
    title: 'Lignes',
    rows: [
      { keys: ['↑', '↓'], action: 'Déplacer la ligne active' },
      { keys: ['Espace'], action: 'Cocher / décocher la ligne active' },
      { keys: ['Shift', '↑', '↓'], action: 'Étendre la sélection' },
      { keys: ['Ctrl', 'A'], action: 'Tout (dé)sélectionner' },
    ],
  },
  {
    title: 'Couleur',
    rows: [{ keys: ['1…9'], action: 'Couleur N de la palette sur les lignes cochées' }],
  },
  {
    title: 'Group by',
    rows: [
      { keys: ['Alt', 'Shift', '1…9'], action: 'Activer / désactiver le token N' },
      { keys: ['Alt', 'Shift', '0'], action: 'Auto (aucun token)' },
    ],
  },
  {
    title: 'Aide',
    rows: [{ keys: ['?'], action: 'Ouvrir ce panneau' }],
  },
];

export function HelpModal({ open, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (await copyToClipboard(MCP_COMMAND)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Aide · raccourcis</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          {SECTIONS.map(section => (
            <div key={section.title} className="shortcut-section">
              <div className="shortcut-title">{section.title}</div>
              {section.rows.map((row, i) => (
                <div key={i} className="shortcut-row">
                  <span className="shortcut-keys">
                    {row.keys.map((k, j) => (
                      <kbd key={j}>{k}</kbd>
                    ))}
                  </span>
                  <span className="shortcut-action">{row.action}</span>
                </div>
              ))}
            </div>
          ))}

          <div className="shortcut-section">
            <div className="shortcut-title">Piloter depuis Claude</div>
            <p className="mcp-hint">
              Une LLM peut charger, tracer, extraire et calculer les statistiques par
              population à votre place. Une seule commande à coller dans un terminal —
              rien à installer :
            </p>
            <div className="mcp-install">
              <code>{MCP_COMMAND}</code>
              <button onClick={handleCopy}>{copied ? 'Copié ✓' : 'Copier'}</button>
            </div>
            <p className="mcp-hint">
              Le serveur ne voit pas votre disque : déposez vos fichiers dans le dossier
              partagé, la LLM y écrit en retour un pool <code>.db</code> que vous
              rouvrez avec <strong>Load</strong>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
