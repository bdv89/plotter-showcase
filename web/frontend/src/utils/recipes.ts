import { extractData } from '../api/client';
import { useAppStore } from '../store/appStore';
import type { ExtractRecipe } from '../types';

// The only code path that turns an extraction recipe into stored values: "Extract",
// "Re-extract" (ExtractPanel) and the folder watch all go through it, so a value
// recomputed later is identical to the original. Uses the session's CURRENT processing,
// like /plot-data. Returns how many files got a value.
export async function runRecipe(colName: string, recipe: ExtractRecipe, fileIds: string[]): Promise<number> {
  const { processing, setExtractedColumn } = useAppStore.getState();
  const result = await extractData({ file_ids: fileIds, ...recipe, processing });
  let ok = 0;
  Object.entries(result.results).forEach(([fileId, value]) => {
    // 6 = what api/extract.py actually rounded to (its Pydantic default);
    // how many of those digits are SHOWN is extractedDecimals.
    if (value != null) { setExtractedColumn(fileId, colName, value, 6); ok++; }
  });
  console.log('🟢 extract', { colName, files: fileIds.length, ok });
  return ok;
}

// Replays every saved recipe on the given files (new or reloaded by the folder watch).
export async function replayRecipes(fileIds: string[]): Promise<void> {
  const recipes = useAppStore.getState().extractRecipes;
  for (const [name, recipe] of Object.entries(recipes)) {
    await runRecipe(name, recipe, fileIds);
  }
}
