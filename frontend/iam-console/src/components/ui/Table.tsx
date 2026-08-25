import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDownIcon } from "./icons";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  /** Marks this column's header as clickable when the table itself is given `onSort`. */
  sortable?: boolean;
}

export type SortDirection = "asc" | "desc";

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  /** If given, the whole row navigates here on click - keeps every list page's row-click
   * behavior consistent instead of each page re-implementing its own <Link>-in-<td>. */
  getRowHref?: (row: T) => string;
  /** Key of the column currently sorted on (must match a `sortable` column's `key`). */
  sortKey?: string;
  sortDirection?: SortDirection;
  /** Called with a sortable column's `key` when its header is clicked - toggling direction (or
   * picking a sensible default for a newly-selected column) is the caller's responsibility, same
   * as every other page-owns-its-state pattern in this app. */
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
              const isSortable = col.sortable && onSort;
              const isActive = isSortable && sortKey === col.key;
              return (
                <th
                  key={col.key}
                  style={{ textAlign: col.align || "left" }}
                  className={isSortable ? "data-table__sortable-header" : undefined}
                  onClick={isSortable ? () => onSort!(col.key) : undefined}
                  aria-sort={isActive ? (sortDirection === "asc" ? "ascending" : "descending") : undefined}
                >
                  <span className="data-table__header-inner">
                    {col.header}
                    {isSortable && (
                      <ChevronDownIcon
                        width={13}
                        height={13}
                        className={`data-table__sort-icon ${isActive ? "data-table__sort-icon--active" : ""}`}
                        style={{
                          transform: isActive && sortDirection === "asc" ? "rotate(180deg)" : undefined,
                        }}
                      />
                    )}
                  </span>
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
