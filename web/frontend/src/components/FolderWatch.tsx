import { useEffect, useRef, useState } from 'react';
import { getWatchFolders, pollWatch } from '../api/client';
import { useAppStore } from '../store/appStore';
import { replayRecipes } from '../utils/recipes';

const POLL_MS = 2000;
const FOLDER_KEY = 'plotter-watch-folder'; // last folder, per browser (convenience only)

function readFolder(): string {
  try { return localStorage.getItem(FOLDER_KEY) ?? ''; } catch { return ''; }
}

// Header control: follow a sub-folder of the server's shared folder. Every POLL_MS the
// backend loads new files and reloads growing ones (api/watch.py); here we add them to
// the table (checked → auto-plot redraws), bump dataVersion for reloaded ones, and replay
// the extraction recipes on both — population statistics update as files arrive.
// Lives in the header, not the Data tab: watching goes on whatever tab is shown.
export function FolderWatch() {
  const [open, setOpen] = useState(false);
  const [folders, setFolders] = useState<string[] | null>(null);
  const [folder, setFolder] = useState(readFolder);
  const [active, setActive] = useState(false);
  const [status, setStatus] = useState('');
  const timer = useRef<number | undefined>(undefined);

  const openPanel = async () => {
    setOpen(o => !o);
    if (folders) return;
    try {
      const res = await getWatchFolders();
      setFolders(res.folders);
      if (!res.folders.includes(folder)) setFolder(res.folders[0] ?? '');
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Shared folder unavailable');
    }
  };

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    const cycle = async () => {
      try {
        const res = await pollWatch(folder);
        const store = useAppStore.getState();
        if (res.added.length) store.addFiles(res.added);
        if (res.updated.length) store.bumpDataVersion();
        if (res.rejected.length) {
          store.setError(`Watch: ${res.rejected[0].filename} — ${res.rejected[0].error}`);
        }
        const changed = [...res.added, ...res.updated].map(f => f.file_id);
        if (changed.length) {
          console.log('🔵 watch', { added: res.added.length, updated: res.updated.length });
          await replayRecipes(changed);
        }
        setStatus(`${res.files_in_folder} file(s) · ${new Date().toLocaleTimeString()}`);
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Watch failed');
      }
      // Next cycle only after this one has fully finished: never two polls at once.
      if (!stopped) timer.current = window.setTimeout(cycle, POLL_MS);
    };
    cycle();
    return () => { stopped = true; window.clearTimeout(timer.current); };
  }, [active, folder]);

  const toggle = () => {
    if (!active) {
      try { localStorage.setItem(FOLDER_KEY, folder); } catch { /* private mode */ }
      setOpen(false);
    }
    setActive(a => !a);
  };

  const label = folder || 'shared folder';
  return (
    <div className="folder-watch">
      <button
        className={`pool-button${active ? ' watching' : ''}`}
        onClick={active ? toggle : openPanel}
        title={active
          ? `Watching ${label} — click to stop`
          : 'Watch a folder of the shared drive: new and growing files are loaded and plotted automatically'}
      >
        {active ? `● ${label}` : 'Watch'}
      </button>
      {active && status && <span className="pool-status">{status}</span>}
      {open && !active && (
        <div className="watch-panel">
          {folders === null ? (
            <span className="watch-hint">{status || 'Loading folders…'}</span>
          ) : (
            <>
              <select value={folder} onChange={e => setFolder(e.target.value)}>
                {folders.map(f => <option key={f} value={f}>{f || '(shared folder root)'}</option>)}
              </select>
              <button className="apply-button" onClick={toggle}>Start</button>
              <span className="watch-hint">
                New files are loaded and checked; files still being written are reloaded live;
                saved extractions are replayed.
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
