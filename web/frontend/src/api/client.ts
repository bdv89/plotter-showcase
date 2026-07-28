import type {
  FileInfo, FileStyle, PlotTrace, ProcessingSettings, StyleSettings,
  MetricsSummary, MetricsDailyRow, MetricsEndpointRow,
} from '../types';

// Same-origin by default (frontend served by the backend). Override with
// VITE_API_URL when running the Vite dev server on a separate port.
const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Stable per-browser session id → isolates this user's state on the central server.
const SESSION_ID: string = (() => {
  let id = localStorage.getItem('plotter-session-id');
  if (!id) {
    id = (crypto.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    localStorage.setItem('plotter-session-id', id);
  }
  return id;
})();

function sidHeaders(): Record<string, string> {
  return { 'X-Session-Id': SESSION_ID };
}

// Operation name mapping: frontend value → backend label
const OPERATION_MAP: Record<string, string> = {
  'max': 'Max', 'min': 'Min', 'mean': 'Mean', 'median': 'Median',
  'std': 'Std Dev', 'integral': 'Integral', 'slope': 'Slope',
  'y_at_max_x': 'Y at max(X)', 'value_at_x': 'Value at X',
  'y_when_x_gt': 'Y when X > threshold', 'y_when_x_lt': 'Y when X < threshold',
};

export async function uploadFiles(files: File[]): Promise<FileInfo[]> {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData, headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getFiles(): Promise<FileInfo[]> {
  const res = await fetch(`${API_BASE}/files`, { headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPlotData(request: {
  file_ids: string[];
  x_column: string;
  y_columns: string[];
  y2_columns?: string[];
  styles?: Record<string, FileStyle>;
  processing?: ProcessingSettings;
}): Promise<{ traces: PlotTrace[] }> {
  const res = await fetch(`${API_BASE}/plot-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...sidHeaders() },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function processFile(file_id: string, settings: ProcessingSettings): Promise<void> {
  const res = await fetch(`${API_BASE}/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...sidHeaders() },
    body: JSON.stringify({ file_id, settings }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function extractData(request: {
  file_ids: string[];
  column: string;
  operation: string;
  x_column?: string;
  x_value?: number;
  x_min?: number;
  x_max?: number;
  threshold?: number;
  condition_column?: string;
  operator?: string;
  processing?: ProcessingSettings;
}): Promise<{ results: Record<string, number | null> }> {
  const backendOp = OPERATION_MAP[request.operation] || request.operation;
  const results: Record<string, number | null> = {};

  // Call backend individually per file (backend expects singular file_id)
  for (const file_id of request.file_ids) {
    try {
      const res = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...sidHeaders() },
        body: JSON.stringify({
          file_id,
          column: request.column,
          operation: backendOp,
          x_column: request.x_column,
          x_value: request.x_value,
          x_min: request.x_min,
          x_max: request.x_max,
          threshold: request.threshold,
          condition_column: request.condition_column,
          operator: request.operator,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        results[file_id] = data.value;
      } else {
        results[file_id] = null;
      }
    } catch {
      results[file_id] = null;
    }
  }

  return { results };
}

// Supprime une colonne extraite (de tous les fichiers), ou toutes si name absent.
// Persisté côté serveur → ne réapparaît pas au rechargement.
export async function removeExtractedColumn(name?: string): Promise<void> {
  const res = await fetch(`${API_BASE}/extract/remove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...sidHeaders() },
    body: JSON.stringify({ column_name: name ?? null }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function deleteFile(fileId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/files/${fileId}`, { method: 'DELETE', headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
}

// Vide toute la session serveur (fichiers + copies disque + .db) en un seul appel.
// Bien plus rapide que N suppressions unitaires (chacune réécrit tout le .db).
export async function resetSession(): Promise<void> {
  const res = await fetch(`${API_BASE}/reset`, { method: 'DELETE', headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
}

export async function savePool(data: {
  files: FileInfo[];
  styles: Record<string, FileStyle>;
  extracted: Record<string, Record<string, { value: number; precision: number }>>;
  plot_style: StyleSettings;
  processing: ProcessingSettings;
  path?: string;
  x_column?: string;
  y_columns?: string[];
  y2_columns?: string[];
}): Promise<{ path: string }> {
  const res = await fetch(`${API_BASE}/pool/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...sidHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function exportPool(data: {
  files: FileInfo[];
  styles: Record<string, FileStyle>;
  extracted: Record<string, Record<string, { value: number; precision: number }>>;
  plot_style: StyleSettings;
  processing: ProcessingSettings;
  x_column?: string;
  y_columns?: string[];
  y2_columns?: string[];
}): Promise<Blob> {
  const res = await fetch(`${API_BASE}/pool/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...sidHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function loadPool(file: File): Promise<{
  files: FileInfo[];
  styles: Record<string, FileStyle>;
  extracted: Record<string, Record<string, { value: number; precision: number }>>;
  plot_style: StyleSettings;
  processing: ProcessingSettings;
  plot_settings?: { x_column: string; y_columns: string[]; y2_columns: string[] };
}> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/pool/load`, { method: 'POST', body: formData, headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Fetch this session's full server-side state (for rehydration on startup).
export async function getSessionState(): Promise<{
  files: FileInfo[];
  styles: Record<string, FileStyle>;
  extracted: Record<string, Record<string, { value: number; precision: number }>>;
  plot_style: StyleSettings;
  processing: ProcessingSettings;
  plot_settings?: { x_column: string; y_columns: string[]; y2_columns: string[] };
}> {
  const res = await fetch(`${API_BASE}/session`, { headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Connection-tracking metrics (onglet Metrics).
export async function getMetricsSummary(): Promise<MetricsSummary> {
  const res = await fetch(`${API_BASE}/metrics/summary`, { headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMetricsDaily(days = 30): Promise<{ rows: MetricsDailyRow[] }> {
  const res = await fetch(`${API_BASE}/metrics/daily?days=${days}`, { headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getMetricsEndpoints(): Promise<{ rows: MetricsEndpointRow[] }> {
  const res = await fetch(`${API_BASE}/metrics/endpoints`, { headers: sidHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
