interface Props {
  open: boolean;
  onClose: () => void;
}

const SECTIONS: { title: string; rows: { keys: string[]; action: string }[] }[] = [
  {
    title: 'Onglets',
    rows: [{ keys: ['Alt', '1…4'], action: 'Data / Plot / Process / Metrics' }],
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
        </div>
      </div>
    </div>
  );
}
