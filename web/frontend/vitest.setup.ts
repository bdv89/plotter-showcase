/* eslint-disable @typescript-eslint/no-explicit-any */
// The Zustand store reads localStorage at module-init (theme). Provide a minimal
// in-memory stub so pure state tests can run in the node environment (no jsdom).
class MemStorage {
  private m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
  key(i: number) { return [...this.m.keys()][i] ?? null; }
  get length() { return this.m.size; }
}
if (!(globalThis as any).localStorage) {
  (globalThis as any).localStorage = new MemStorage();
}
