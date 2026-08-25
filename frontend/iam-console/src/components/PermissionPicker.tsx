import { groupPermissionsByNamespace } from "../lib/permissions";

interface Props {
  catalog: string[];
  selected: string[];
  onChange: (codes: string[]) => void;
  disabled?: boolean;
}

/** Grouped-by-service-namespace checkbox picker used when authoring a custom role. Grouping
 * labels come from lib/permissions.ts (namespaceLabel), never hardcoded here, so a new namespace
 * only needs to be taught to that one file. */
export default function PermissionPicker({ catalog, selected, onChange, disabled = false }: Props) {
  const groups = groupPermissionsByNamespace(catalog);
  const selectedSet = new Set(selected);

  function toggle(code: string) {
    if (disabled) return;
    const next = selectedSet.has(code) ? selected.filter((c) => c !== code) : [...selected, code];
    onChange(next);
  }

  function toggleGroup(codes: string[]) {
    if (disabled) return;
    const allSelected = codes.every((c) => selectedSet.has(c));
    const next = allSelected ? selected.filter((c) => !codes.includes(c)) : [...new Set([...selected, ...codes])];
    onChange(next);
  }

  if (catalog.length === 0) {
    return <p className="hint-text">No permissions available yet.</p>;
  }

  return (
    <div className="permission-picker">
      {groups.map((group) => {
        const allSelected = group.codes.every((c) => selectedSet.has(c));
        return (
          <div className="permission-picker__group" key={group.namespace}>
            <div className="permission-picker__group-header">
              <span>{group.label}</span>
              {!disabled && (
                <button type="button" onClick={() => toggleGroup(group.codes)}>
                  {allSelected ? "Clear all" : "Select all"}
                </button>
              )}
            </div>
            {group.codes.map((code) => (
              <label key={code} className="permission-picker__item">
                <input type="checkbox" checked={selectedSet.has(code)} disabled={disabled} onChange={() => toggle(code)} />
                <code>{code}</code>
              </label>
            ))}
          </div>
        );
      })}
    </div>
  );
}
