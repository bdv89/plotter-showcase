import type { StyleSettings } from '../types';

// Standalone style preset (.json) — saves only the GLOBAL plot appearance.
// Per-file colors/labels are keyed by dataset UUIDs, so they are intentionally
// out of scope here (they wouldn't match another dataset).

const PRESET_VERSION = 'style-1';

export function exportStyle(plotStyle: StyleSettings): void {
  const payload = { version: PRESET_VERSION, plot_style: plotStyle };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'style-preset.json';
  a.click();
  URL.revokeObjectURL(url);
}

export async function importStyle(file: File): Promise<Partial<StyleSettings>> {
  const text = await file.text();
  const parsed = JSON.parse(text);
  // Tolerant: accept either { plot_style: {...} } or a bare StyleSettings object.
  const style = parsed?.plot_style ?? parsed;
  if (!style || typeof style !== 'object') {
    throw new Error('Invalid style preset file');
  }
  return style as Partial<StyleSettings>;
}
