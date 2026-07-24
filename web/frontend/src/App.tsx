import { useRef, useState, useEffect } from 'react';
import { FileTable } from './components/FileTable';
import { ColumnSelector } from './components/ColumnSelector';
import { PlotView } from './components/PlotView';
import { ProcessingPanel } from './components/ProcessingPanel';
import { ExtractionModal } from './components/ExtractionModal';
import { MetricsView } from './components/MetricsView';
import { useAppStore } from './store/appStore';
import { exportPool, loadPool, uploadFiles, getSessionState } from './api/client';
import { pickAndSave, writeBlob, openDataFiles } from './utils/saveFile';
import './App.css';

const SECTIONS = ['page-data', 'page-plot', 'page-processing', 'page-metrics'];

function App() {
  const [extractionOpen, setExtractionOpen] = useState(false);
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

  // Highlight the nav tab matching the most-visible section.
  useEffect(() => {
    const root = document.querySelector('.app-body');
    const els = SECTIONS.map(id => document.getElementById(id)).filter(Boolean) as HTMLElement[];
    if (!root || els.length === 0) return;
    const obs = new IntersectionObserver(
      entries => {
        const visible = entries.filter(e => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { root, threshold: [0.25, 0.5, 0.75] },
    );
    els.forEach(el => obs.observe(el));
    return () => obs.disconnect();
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
    const { files, fileStyles, extractedColumns, plotStyle, processing, xColumn, yColumns, y2Columns } = useAppStore.getState();
    return exportPool({
      files, styles: fileStyles, extracted: extractedColumns,
      plot_style: plotStyle, processing,
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

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  // navigator.clipboard n'existe qu'en contexte sécurisé (HTTPS/localhost) ;
  // en HTTP sur IP LAN (Firefox strict), il est undefined → fallback execCommand.
  const copyToClipboard = async (text: string): Promise<boolean> => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // tombe sur le fallback ci-dessous
    }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  };

  // Copy checked files as TSV (Filename, Legend, extracted columns) for spreadsheets.
  const handleCopyData = async () => {
    const { files, checkedFiles, fileStyles, extractedColumns } = useAppStore.getState();
    const rows = files.filter(f => checkedFiles.has(f.file_id));
    if (rows.length === 0) {
      setPoolStatus('Aucun fichier coché');
      setTimeout(() => setPoolStatus(''), 3000);
      return;
    }
    // Union of extracted column names across checked files (insertion order).
    const cols: string[] = [];
    rows.forEach(f => {
      Object.keys(extractedColumns[f.file_id] || {}).forEach(c => {
        if (!cols.includes(c)) cols.push(c);
      });
    });
    const header = ['Filename', 'Legend', ...cols];
    const body = rows.map(f => {
      const legend = fileStyles[f.file_id]?.legend_label || f.filename.replace(/\.[^.]+$/, '');
      const values = cols.map(c => {
        const e = extractedColumns[f.file_id]?.[c];
        return e ? e.value.toFixed(e.precision).replace('.', ',') : '';
      });
      return [f.filename, legend, ...values];
    });
    const tsv = [header, ...body].map(r => r.join('\t')).join('\n');
    if (await copyToClipboard(tsv)) {
      setPoolStatus(`Copié ${rows.length} ligne(s)`);
    } else {
      setError('Copie presse-papier échouée');
    }
    setTimeout(() => setPoolStatus(''), 3000);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Plotter</h1>
        <nav className="page-nav">
          <button className={activeSection === 'page-data' ? 'active' : ''} onClick={() => scrollTo('page-data')}>Data</button>
          <button className={activeSection === 'page-plot' ? 'active' : ''} onClick={() => scrollTo('page-plot')}>Plot</button>
          <button className={activeSection === 'page-processing' ? 'active' : ''} onClick={() => scrollTo('page-processing')}>Process</button>
          <button className={activeSection === 'page-metrics' ? 'active' : ''} onClick={() => scrollTo('page-metrics')}>Metrics</button>
        </nav>
        <div className="header-actions">
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
          <input
            ref={poolInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.tsv,.db"
            style={{ display: 'none' }}
            onChange={handleLoadInput}
          />
          {poolStatus && <span className="pool-status">{poolStatus}</span>}
          <button className="extract-button" onClick={() => setExtractionOpen(true)}>
            Extract Data
          </button>
          <button
            className="pool-button"
            onClick={handleCopyData}
            title="Copier (filename, legend, colonnes extraites) — collable dans un tableur"
          >
            Copy Data
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>&times;</button>
        </div>
      )}

      <div className="app-body">
        <section className="page page-data" id="page-data">
          <FileTable />
          <ColumnSelector />
        </section>

        <section className="page page-plot" id="page-plot">
          <PlotView />
        </section>

        <section className="page page-processing" id="page-processing">
          <ProcessingPanel />
        </section>

        <section className="page page-metrics" id="page-metrics">
          <MetricsView />
        </section>
      </div>

      <ExtractionModal open={extractionOpen} onClose={() => setExtractionOpen(false)} />
    </div>
  );
}

export default App;
