import type { ReactNode } from "react";

interface FieldProps {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}

/** One labeled control inside a FilterBar (a search box, a <select>, a date input, ...). */
export function FilterBarField({ label, htmlFor, children }: FieldProps) {
  return (
    <div className="filter-bar__field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
    </div>
  );
}

interface Props {
  children: ReactNode;
  /** Trailing content that isn't a labeled field - e.g. AuditLogPage's sort-direction toggle. */
  trailing?: ReactNode;
}

/** Shared layout for every list page's search/filter controls - originally AuditLogPage's
 * bespoke `.filter-bar` markup, extracted here so every page (users, roles, role assignments,
 * service principals, audit log) renders the same row-of-fields look instead of copy-pasting
 * the wrapper divs. */
export default function FilterBar({ children, trailing }: Props) {
  return (
    <div className="filter-bar">
      {children}
      {trailing}
    </div>
  );
}
