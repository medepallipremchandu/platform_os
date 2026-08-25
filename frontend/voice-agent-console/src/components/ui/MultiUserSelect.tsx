import { useEffect, useRef, useState } from "react";
import { CloseIcon } from "./icons";
import type { SearchableOption } from "./SearchableSelect";

interface Props {
  options: SearchableOption[];
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  emptyLabel?: string;
}

/** A type-to-filter multi-select with removable chips for the already-picked items - used to
 * grant restricted-visibility access to a set of specific people. Modeled after iam-console's
 * `SearchableSelect` (single-value) but keeps a running list instead of replacing the value. */
export default function MultiUserSelect({
  options,
  values,
  onChange,
  placeholder = "Search people...",
  disabled,
  emptyLabel = "No matches",
}: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClickAway = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, [open]);

  const selectedOptions = values.map((v) => options.find((o) => o.value === v)).filter((o): o is SearchableOption => !!o);
  const filtered = options.filter((o) => !values.includes(o.value) && o.label.toLowerCase().includes(query.toLowerCase()));

  function add(value: string) {
    onChange([...values, value]);
    setQuery("");
  }

  function remove(value: string) {
    onChange(values.filter((v) => v !== value));
  }

  return (
    <div className="multi-select" ref={containerRef}>
      {selectedOptions.length > 0 && (
        <div className="multi-select__chips">
          {selectedOptions.map((o) => (
            <span className="multi-select__chip" key={o.value}>
              {o.label}
              <button type="button" onClick={() => remove(o.value)} aria-label={`Remove ${o.label}`}>
                <CloseIcon width={12} height={12} />
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        type="text"
        placeholder={placeholder}
        disabled={disabled}
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
      />
      {open && !disabled && (
        <div className="searchable-select__menu">
          {filtered.length === 0 ? (
            <div className="searchable-select__empty">{options.length === 0 ? "No users to choose from" : emptyLabel}</div>
          ) : (
            filtered.map((option) => (
              <button key={option.value} type="button" className="searchable-select__option" onClick={() => add(option.value)}>
                <div>{option.label}</div>
                {option.description && <div className="hint-text">{option.description}</div>}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
