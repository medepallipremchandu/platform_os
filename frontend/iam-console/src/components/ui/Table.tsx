import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  /** If given, the whole row navigates here on click - keeps every list page's row-click
   * behavior consistent instead of each page re-implementing its own <Link>-in-<td>. */
  getRowHref?: (row: T) => string;
}

export default function Table<T>({ columns, rows, getRowKey, getRowHref }: Props<T>) {
  const navigate = useNavigate();

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ textAlign: col.align || "left" }}>
                {col.header}
              </th>
            ))}
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
