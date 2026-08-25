import type { InputHTMLAttributes } from "react";
import { useEffect, useRef, useState } from "react";
import { SearchIcon } from "./icons";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> {
  value: string;
  onChange: (value: string) => void;
  /** Debounce delay before `onChange` fires after the user stops typing. */
  debounceMs?: number;
}

/**
 * Debounced text search box with a leading search icon, shared by every list page (Requirements,
 * Applicants, Submissions) instead of each one wiring up its own input + timer. The parent owns
 * the actual filter/query state - this component only debounces keystrokes before calling
 * `onChange`.
 */
export default function SearchInput({ value, onChange, placeholder = "Search...", debounceMs = 250, ...rest }: Props) {
  const [draft, setDraft] = useState(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // Keep the visible text in sync if the parent resets/changes `value` externally (e.g. a
  // "Clear filters" action), without fighting the user mid-keystroke.
  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (draft === value) return;
    const handle = setTimeout(() => onChangeRef.current(draft), debounceMs);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, debounceMs]);

  return (
    <div className="search-input">
      <SearchIcon className="search-input__icon" width={16} height={16} />
      <input
        type="search"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={placeholder}
        {...rest}
      />
    </div>
  );
}
