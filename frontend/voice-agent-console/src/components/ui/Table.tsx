import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDownIcon } from "./icons";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** Marks this column's header as clickable-to-sort. Only rendered as such when the parent also
   * passes `sortKey`/`onSort` to <Table> - a page with no sorting can leave these off entirely. */
  sortable?: boolean;
  /** The value passed to `onSort`/compared against `sortKey` for this column. Defaults to `key`
   * when omitted (set it explicitly if `key` isn't itself a valid sort field, e.g. a computed
   * column). */
  sortKey?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  /** If given, the whole row navigates here on click - keeps every list page's row-click
   * behavior consistent instead of each page re-implementing its own <Link>-in-<td>. */
  getRowHref?: (row: T) => string;
  /** The `sortKey` of the currently active sort column, or null/undefined when unsorted. */
  sortKey?: string | null;
  sortDirection?: "asc" | "desc";
  /** Called with a column's `sortKey` when its header is clicked. The caller owns the actual
   * sort state (including toggling direction on repeat clicks) - this component only renders
   * the active-column indicator. */
  onSort?: (key: string) => void;
}

export default function Table<T>({ columns, rows, getRowKey, getRowHref, sortKey, sortDirection, onSort }: Props<T>) {
  const navigate = useNavigate();

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => {
              const key = col.sortKey || col.key;
              const isActive = Boolean(col.sortable && sortKey === key);
              return (
                <th key={col.key} style={{ textAlign: col.align || "left" }}>
                  {col.sortable && onSort ? (
                    <button
                      type="button"
                      className={`data-table__sort-btn ${isActive ? "data-table__sort-btn--active" : ""}`}
                      onClick={() => onSort(key)}
                      aria-sort={isActive ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                    >
                      {col.header}
                      <ChevronDownIcon
                        width={13}
                        height={13}
                        className={`data-table__sort-icon ${isActive ? "data-table__sort-icon--active" : ""} ${
                          isActive && sortDirection === "asc" ? "data-table__sort-icon--asc" : ""
                        }`}
                      />
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const href = getRowHref?.(row);
            return (
              <tr
                key={getRowKey(row)}
                className={href ? "data-table__row--clickable" : ""}
                onClick={href ? () => navigate(href) : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} style={{ textAlign: col.align || "left" }}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
