// Native "Save As" via the File System Access API (Chrome/Edge), with a
// download fallback for browsers that don't support it (Firefox/Safari).

interface SaveFilePickerOptions {
  suggestedName?: string;
  startIn?: FileSystemHandle;
  types?: { description?: string; accept: Record<string, string[]> }[];
}
type ShowSaveFilePicker = (opts?: SaveFilePickerOptions) => Promise<FileSystemFileHandle>;
type ShowOpenFilePicker = (opts?: { multiple?: boolean }) => Promise<FileSystemFileHandle[]>;

function getPicker(): ShowSaveFilePicker | undefined {
  return (window as unknown as { showSaveFilePicker?: ShowSaveFilePicker }).showSaveFilePicker;
}

/**
 * Open data/session files via the File System Access API so we keep a handle
 * (used later as the default folder for "Save As"). Returns null when the API
 * is unavailable, so the caller can fall back to a plain <input>.
 * Throws AbortError if the user cancels.
 */
export async function openDataFiles(): Promise<{ files: File[]; handle: FileSystemFileHandle | null } | null> {
  const picker = (window as unknown as { showOpenFilePicker?: ShowOpenFilePicker }).showOpenFilePicker;
  if (!picker) return null;
  const handles = await picker({ multiple: true });
  const files = await Promise.all(handles.map(h => h.getFile()));
  return { files, handle: handles[0] ?? null };
}

/** Write a Blob to an existing file handle (silent re-save). */
export async function writeBlob(handle: FileSystemFileHandle, blob: Blob): Promise<void> {
  const writable = await handle.createWritable();
  await writable.write(blob);
  await writable.close();
}

/**
 * Prompt the user for a save location and write the blob there.
 * Returns the file handle (for later silent Save), or null when the
 * download fallback was used. Throws AbortError if the user cancels.
 */
export async function pickAndSave(
  blob: Blob,
  suggestedName: string,
  startIn?: FileSystemHandle,
): Promise<FileSystemFileHandle | null> {
  const picker = getPicker();
  if (picker) {
    const handle = await picker({
      suggestedName,
      ...(startIn ? { startIn } : {}),
      types: [{ description: 'Pool SQLite', accept: { 'application/octet-stream': ['.db'] } }],
    });
    await writeBlob(handle, blob);
    return handle;
  }
  // Fallback: trigger a normal download (goes to the Downloads folder).
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = suggestedName;
  a.click();
  URL.revokeObjectURL(url);
  return null;
}
