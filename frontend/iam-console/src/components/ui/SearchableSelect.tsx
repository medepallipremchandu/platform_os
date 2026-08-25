import { useEffect, useRef, useState } from "react";

export interface SearchableOption {
  value: string;
  label: string;
  description?: string;
}

interface Props {
  options: SearchableOption[];
  value: string | null;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

/** A minimal type-to-filter select with no external dependency, used to pick a principal (a user
 * or service principal, potentially dozens of each) out of a flat list. */
export default function SearchableSelect({ options, value, onChange, placeholder = "Search...", disabled }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onClickAway = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, [open]);

  const filtered = options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="searchable-select" ref={containerRef}>
      <input
        type="text"
        placeholder={placeholder}
        disabled={disabled}
        value={open ? query : selected?.label || ""}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onChange={(e) => setQuery(e.target.value)}
      />
      {open && (
        <div className="searchable-select__menu">
          {filtered.length === 0 ? (
            <div className="searchable-select__empty">No matches</div>
          ) : (
            filtered.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`searchable-select__option ${option.value === value ? "searchable-select__option--active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                  setQuery("");
                }}
              >
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
