import { useEffect, useRef, useState } from "react";
import { SearchIcon } from "./icons";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Debounce delay in ms before `onChange` fires. Defaults to 250ms. */
  debounceMs?: number;
  className?: string;
}

/** A debounced search box used at the top of every list page (users, roles, role assignments,
 * service principals, ...) - typing updates an internal draft immediately for a responsive feel,
 * but `onChange` (which drives the actual client-side filter) only fires ~250ms after the user
 * stops typing. Kept in sync with `value` if it's changed from outside (e.g. a "clear filters"
 * button elsewhere on the page). */
export default function SearchInput({ value, onChange, placeholder = "Search...", debounceMs = 250, className = "" }: Props) {
  const [draft, setDraft] = useState(value);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  function handleInput(next: string) {
    setDraft(next);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    // Captures this render's `onChange` - fine for a debounced text input (the parent's handler
    // for a controlled search box is effectively stable in identity-of-behavior even if the
    // function reference itself isn't memoized).
    timeoutRef.current = setTimeout(() => onChange(next), debounceMs);
  }

  return (
    <div className={`search-input ${className}`.trim()}>
      <SearchIcon width={16} height={16} className="search-input__icon" />
      <input
        type="search"
        value={draft}
        onChange={(e) => handleInput(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
    </div>
  );
}
