/** Shared formatting so every page renders dates/names identically. */

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const trimmed = name.trim();
  if (!trimmed) return "?";
  // Emails ("jane@acme.com") don't split on whitespace - fall back to the local part's first
  // two letters so the sidebar/topbar avatar still shows something sensible.
  if (trimmed.includes("@") && !trimmed.includes(" ")) {
    return trimmed.slice(0, 2).toUpperCase();
  }
  const parts = trimmed.split(/\s+/);
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("");
}
