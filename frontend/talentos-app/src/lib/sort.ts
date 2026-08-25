/** Small client-side sort helper shared by list pages that sort an already-fetched array
 * (requirements/applicants/submissions - small per-org lists today, so sorting the full
 * in-memory array is fine; see each list page for a note on what server-side pagination would
 * look like if these grow large in practice). */

export type SortDirection = "asc" | "desc";

function compareValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return -1;
  if (b == null) return 1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { sensitivity: "base" });
}

/** Returns a new sorted array (or `rows` itself, unchanged, when `sortKey` is null/unknown).
 * `accessors` maps each sortable key to a function pulling the comparable value off a row. */
export function sortRows<T>(
  rows: T[],
  sortKey: string | null,
  direction: SortDirection,
  accessors: Record<string, (row: T) => unknown>,
): T[] {
  const accessor = sortKey ? accessors[sortKey] : undefined;
  if (!accessor) return rows;
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => sign * compareValues(accessor(a), accessor(b)));
}
