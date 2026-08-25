import { useState } from "react";
import { formatDateTime } from "../lib/format";
import { toneForAuditAction } from "../lib/tone";
import type { AuditLogEntry } from "../types";
import Badge from "./ui/Badge";
import { ChevronRightIcon } from "./ui/icons";

interface Props {
  entries: AuditLogEntry[];
}

function formatChanges(changes: AuditLogEntry["changes"]): string[] {
  if (!changes) return [];
  return Object.entries(changes).map(([field, { old, new: next }]) => `${field}: "${old}" -> "${next}"`);
}

export default function AuditHistory({ entries }: Props) {
  const [open, setOpen] = useState(false);

  if (entries.length === 0) return null;

  return (
    <div className="audit-history">
      <button type="button" className="audit-history__toggle" onClick={() => setOpen((v) => !v)}>
        <ChevronRightIcon width={14} height={14} className={open ? "audit-history__chevron--open" : ""} />
        {open ? "Hide" : "Show"} history ({entries.length})
      </button>
      {open && (
        <ul className="audit-history__list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <Badge tone={toneForAuditAction(entry.action)}>{entry.action}</Badge>
              <span className="audit-history__meta">
                {entry.changed_by} - {formatDateTime(entry.changed_at)}
              </span>
              {entry.changes && (
                <ul className="audit-history__changes">
                  {formatChanges(entry.changes).map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
