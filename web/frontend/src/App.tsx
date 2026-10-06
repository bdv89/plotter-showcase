import { useRef, useState, useEffect } from 'react';
import { FileTable } from './components/FileTable';
import { StyleBar } from './components/StyleBar';
import { PlotView } from './components/PlotView';
import { ProcessingPanel } from './components/ProcessingPanel';
import { ExtractPanel } from './components/ExtractPanel';
import { StatsBar } from './components/StatsBar';
import { HelpModal } from './components/HelpModal';
import { TutorialModal } from './components/TutorialModal';
import { MetricsView } from './components/MetricsView';
import { FolderWatch } from './components/FolderWatch';
import { useAppStore } from './store/appStore';
import { exportPool, loadPool, uploadFiles, getSessionState } from './api/client';
import { pickAndSave, writeBlob, openDataFiles } from './utils/saveFile';
import { displayTokens } from './utils/coloring';
import './App.css';

function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  const [tutorialOpen, setTutorialOpen] = useState(false);
  const [poolStatus, setPoolStatus] = useState('');
  const [activeSection, setActiveSection] = useState('page-data');
  const [dragOver, setDragOver] = useState(false);
  const poolInputRef = useRef<HTMLInputElement>(null);
  const poolHandleRef = useRef<FileSystemFileHandle | null>(null);
  // Handle of the last loaded data file → default folder for "Save As".
  const lastDataHandleRef = useRef<FileSystemFileHandle | null>(null);
  const theme = useAppStore(s => s.theme);
  const toggleTheme = useAppStore(s => s.toggleTheme);
  const error = useAppStore(s => s.error);
  const setError = useAppStore(s => s.setError);

  // Keyboard: Alt+1..5 switch tabs (Alt+digit avoids the browser's Ctrl+digit).
  // !shiftKey so it never overlaps Alt+Shift+digit (Group By) handled in FileTable.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      // "?" opens help, Escape closes it (not while typing in a field).
      if (!typing && e.key === '?') { e.preventDefault(); setHelpOpen(true); return; }
      if (e.key === 'Escape') { setHelpOpen(false); setTutorialOpen(false); }

      // Group by tokens — Alt+Shift+1..9 toggle / Alt+Shift+0 Auto, on DATA + Plot.
      if (e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && !typing) {
        const m = /^Digit([0-9])$/.exec(e.code);
        if (m && document.querySelector('.page-data.active, .page-plot.active, .page-extract.active')) {
          e.preventDefault();
          const n = Number(m[1]);
          const st = useAppStore.getState();
          if (n === 0) st.clearSeries();
          else {
            const tokens = st.files.length > 0 ? displayTokens(st.files[0].filename) : [];
            if (n - 1 < tokens.length) st.toggleSeriesToken(n - 1);
          }
        }
        return;
      }

      // Alt+1..5 switch tabs (no other modifier; Alt+Shift+digit is Group By).
      if (!e.altKey || e.shiftKey || e.ctrlKey || e.metaKey) return;
      const map: Record<string, string> = {
        Digit1: 'page-data', Digit2: 'page-plot', Digit3: 'page-processing',
        Digit4: 'page-extract', Digit5: 'page-metrics',
      };
      const target = map[e.code];
      if (target) {
        e.preventDefault();
        setActiveSection(target);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // On startup, rehydrate this browser's server-side session so a refresh (or a
  // server restart) restores the user's files/styles/columns from <sid>.db.
  useEffect(() => {
    getSessionState()
      .then(data => {
        if (data.files && data.files.length > 0) {
          useAppStore.getState().restorePool(data);
        }
      })
      .catch(() => { /* no session yet — fresh start */ });
  }, []);

  // Build the .db bytes from the current session (backend serializes to SQLite).
  const getPoolBlob = () => {
    const {
      files, fileStyles, extractedColumns, plotStyle, drawings, processing,
      xColumn, yColumns, y2Columns,
      statsVisible, statsCols, statsHiddenExtracted, extractedDecimals, hiddenLegend,
      extractRecipes,
    } = useAppStore.getState();
    return exportPool({
      files, styles: fileStyles, extracted: extractedColumns,
      // Drawings AND the stats box ride inside plot_style (backend keeps it as
      // an opaque dict) — no backend change needed to persist either.
      plot_style: {
        ...plotStyle,
        drawings,
        stats: { visible: statsVisible, cols: statsCols, hiddenExtracted: statsHiddenExtracted, decimals: extractedDecimals },
        hiddenLegend,
        // Les recettes d'extraction : sans elles, un pool rechargé garde ses
        // colonnes mais ne sait plus les rejouer sur de nouveaux fichiers.
        recipes: extractRecipes,
      } as typeof plotStyle,
      processing,
      x_column: xColumn, y_columns: yColumns, y2_columns: y2Columns,
    });
  };

  // Save As: native "Save As" dialog (Chrome/Edge) to pick folder + name.
  const handleSavePoolAs = async () => {
    try {
      setPoolStatus('Saving...');
      const blob = await getPoolBlob();
      const base = (useAppStore.getState().currentPoolName || 'pool')
        .replace(/^.*[\\/]/, '').replace(/\.db$/, '') || 'pool';
      const handle = await pickAndSave(blob, `${base}.db`, lastDataHandleRef.current ?? undefined);
      if (handle) {
        poolHandleRef.current = handle;
        useAppStore.getState().setCurrentPoolName(handle.name);
      }
      setPoolStatus('Pool saved!');
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') { setPoolStatus(''); return; }
      setPoolStatus('Save failed');
      setError(e instanceof Error ? e.message : 'Save pool failed');
    }
    setTimeout(() => setPoolStatus(''), 3000);
  };

  // Save: re-write to the last chosen location silently; else ask (Save As).
  const handleSavePool = async () => {
    if (!poolHandleRef.current) { handleSavePoolAs(); return; }
    try {
      setPoolStatus('Saving...');
      const blob = await getPoolBlob();
      await writeBlob(poolHandleRef.current, blob);
      setPoolStatus('Pool saved!');
    } catch (e) {
      setPoolStatus('Save failed');
      setError(e instanceof Error ? e.message : 'Save pool failed');
    }
    setTimeout(() => setPoolStatus(''), 3000);
  };

  // Unified load: .db restores a session pool, data files are uploaded. Used by
  // both the Load button (click → file picker) and drag&drop onto that button.
  const processFiles = async (picked: File[]) => {
    if (picked.length === 0) return;
    const dbFile = picked.find(f => /\.db$/i.test(f.name));
    const dataFiles = picked.filter(f => /\.(csv|xlsx|xls|tsv)$/i.test(f.name));
    if (!dbFile && dataFiles.length === 0) {
      setPoolStatus('Unsupported file');
      setTimeout(() => setPoolStatus(''), 3000);
      return;
    }
    try {
      if (dbFile) {
        setPoolStatus('Loading...');
        const data = await loadPool(dbFile);
        useAppStore.getState().restorePool(data);
        setPoolStatus(`Loaded ${data.files.length} files`);
      }
      if (dataFiles.length > 0) {
        setPoolStatus(`Uploading ${dataFiles.length} file(s)...`);
        const result = await uploadFiles(dataFiles);
        useAppStore.getState().addFiles(result);
        setPoolStatus(`Uploaded ${result.length} file(s)`);
      }
    } catch (err) {
      setPoolStatus('Load failed');
      useAppStore.getState().setError(err instanceof Error ? err.message : 'Load failed');
    }
    setTimeout(() => setPoolStatus(''), 3000);
  };

  const handleLoadInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files || []);
    e.target.value = '';
    processFiles(picked);
  };

  // Load via the File System Access API (keeps a handle → its folder becomes the
  // default for "Save As"). Falls back to the plain <input> when unavailable.
  const handleLoadClick = async () => {
    try {
      const picked = await openDataFiles();
      if (!picked) { poolInputRef.current?.click(); return; }
      if (picked.handle) lastDataHandleRef.current = picked.handle;
      processFiles(picked.files);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      poolInputRef.current?.click();
    }
  };

  // Drop: capture a file handle (Chromium) for the default Save-As folder.
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    const handlePromises = Array.from(e.dataTransfer.items)
      .filter(it => it.kind === 'file')
      .map(it => (it as unknown as { getAsFileSystemHandle?: () => Promise<FileSystemHandle> })
        .getAsFileSystemHandle?.());
    if (handlePromises.some(Boolean)) {
      Promise.all(handlePromises)
        .then(hs => {
          const h = hs.find(x => x && x.kind === 'file') as FileSystemFileHandle | undefined;
          if (h) lastDataHandleRef.current = h;
        })
        .catch(() => { /* ignore */ });
    }
    processFiles(dropped);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Plotter</h1>
        <nav className="page-nav">
          <button className={activeSection === 'page-data' ? 'active' : ''} onClick={() => setActiveSection('page-data')}>Data</button>
          <button className={activeSection === 'page-plot' ? 'active' : ''} onClick={() => setActiveSection('page-plot')}>Plot</button>
          <button className={activeSection === 'page-processing' ? 'active' : ''} onClick={() => setActiveSection('page-processing')}>Process</button>
          <button className={activeSection === 'page-extract' ? 'active' : ''} onClick={() => setActiveSection('page-extract')}>Extract</button>
          <button className={activeSection === 'page-metrics' ? 'active' : ''} onClick={() => setActiveSection('page-metrics')}>Metrics</button>
        </nav>
        <div className="header-actions">
          <button
            className="help-button"
            onClick={() => setHelpOpen(true)}
            title="Aide \u00B7 raccourcis (?)"
          >
            ?
          </button>
          <button
            className="help-button"
            onClick={() => setTutorialOpen(true)}
            title="Tutoriel pas à pas"
          >
            Tuto
          </button>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? '\u2600' : '\u263E'}
          </button>
          <button className="pool-button" onClick={handleSavePool} title="Enregistrer (au dernier emplacement choisi)">Save</button>
          <button className="pool-button" onClick={handleSavePoolAs} title="Enregistrer sous… (choisir le dossier et le nom)">Save As</button>
          <button
            className={`pool-button ${dragOver ? 'drag-over' : ''}`}
            onClick={handleLoadClick}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            title="Load or drop data (.csv, .xlsx, .xls) or session (.db)"
          >
            Load
          </button>
          <FolderWatch />
          <input
            ref={poolInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.tsv,.db"
            style={{ display: 'none' }}
            onChange={handleLoadInput}
          />
          {poolStatus && <span className="pool-status">{poolStatus}</span>}
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>&times;</button>
        </div>
      )}

      <div className="app-body">
        <section className={`page page-data${activeSection === 'page-data' ? ' active' : ''}`} id="page-data">
          <FileTable />
        </section>

        <section className={`page page-plot${activeSection === 'page-plot' ? ' active' : ''}`} id="page-plot">
          <div className="plot-stylebar"><StyleBar /><StatsBar /></div>
          <PlotView />
        </section>

        <section className={`page page-processing${activeSection === 'page-processing' ? ' active' : ''}`} id="page-processing">
          <ProcessingPanel />
        </section>

        <section className={`page page-extract${activeSection === 'page-extract' ? ' active' : ''}`} id="page-extract">
          <ExtractPanel />
        </section>

        <section className={`page page-metrics${activeSection === 'page-metrics' ? ' active' : ''}`} id="page-metrics">
          <MetricsView />
        </section>
      </div>

      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
      <TutorialModal open={tutorialOpen} onClose={() => setTutorialOpen(false)} />
    </div>
  );
}

export default App;
