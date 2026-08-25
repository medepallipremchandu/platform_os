import { useEffect, useMemo, useState } from "react";
import { extractErrorMessage } from "../api/client";
import { listAuditEvents } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import FilterBar, { FilterBarField } from "../components/ui/FilterBar";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { ChevronDownIcon, HistoryIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { toneForAuditResult } from "../lib/tone";
import type { AuditLogEntry, AuditResult } from "../types";

type SortDirection = "desc" | "asc";

const PAGE_SIZE = 50;

export default function AuditLogPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;

  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [actorId, setActorId] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [resultFilter, setResultFilter] = useState<AuditResult | "">("");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [detail, setDetail] = useState<AuditLogEntry | null>(null);

  useEffect(() => {
    if (!orgId) return;
    setEntries(null);
    listAuditEvents({
      organization_id: orgId,
      actor_id: actorId || undefined,
      action: action || undefined,
      result: resultFilter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((res) => {
        setEntries(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(extractErrorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, actorId, action, resultFilter, dateFrom, dateTo, page]);

  function applyFilters(update: () => void) {
    setPage(1);
    update();
  }

  const visibleEntries = useMemo(() => {
    return [...(entries || [])].sort((a, b) => {
      const diff = new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime();
      return sortDirection === "asc" ? diff : -diff;
    });
  }, [entries, sortDirection]);

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const columns: Column<AuditLogEntry>[] = [
    {
      key: "occurred_at",
      header: "Time",
      render: (e) => formatDateTime(e.occurred_at),
    },
    {
      key: "actor",
      header: "Actor",
      render: (e) => (
        <div>
          <div>{e.actor_id}</div>
          <span className="hint-text">{e.actor_type}</span>
        </div>
      ),
    },
    { key: "action", header: "Action", render: (e) => <code>{e.action}</code> },
    {
      key: "target",
      header: "Target",
      render: (e) => (
        <div>
          <div>{e.target_id}</div>
          <span className="hint-text">{e.target_type}</span>
        </div>
      ),
    },
    { key: "result", header: "Result", render: (e) => <Badge tone={toneForAuditResult(e.result)}>{e.result}</Badge> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (e) => (
        <Button variant="ghost" size="sm" onClick={() => setDetail(e)}>
          Details
        </Button>
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Compliance"
        title="Audit log"
        subtitle="Every authentication, authorization, and business-data mutation across the platform, timestamped."
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <FilterBar
          trailing={
            <Button
              variant="secondary"
              size="sm"
              icon={<ChevronDownIcon width={14} height={14} style={{ transform: sortDirection === "asc" ? "rotate(180deg)" : undefined }} />}
              onClick={() => setSortDirection((d) => (d === "desc" ? "asc" : "desc"))}
            >
              {sortDirection === "desc" ? "Newest first" : "Oldest first"}
            </Button>
          }
        >
          <FilterBarField label="Actor ID" htmlFor="audit-actor">
            <input
              id="audit-actor"
              type="text"
              placeholder="user or service principal id"
              value={actorId}
              onChange={(e) => applyFilters(() => setActorId(e.target.value))}
            />
          </FilterBarField>
          <FilterBarField label="Action" htmlFor="audit-action">
            <input
              id="audit-action"
              type="text"
              placeholder="e.g. role_assignment.created"
              value={action}
              onChange={(e) => applyFilters(() => setAction(e.target.value))}
            />
          </FilterBarField>
          <FilterBarField label="Result" htmlFor="audit-result">
            <select
              id="audit-result"
              value={resultFilter}
              onChange={(e) => applyFilters(() => setResultFilter(e.target.value as AuditResult | ""))}
            >
              <option value="">All</option>
              <option value="success">Success</option>
              <option value="denied">Denied</option>
              <option value="error">Error</option>
            </select>
          </FilterBarField>
          <FilterBarField label="From" htmlFor="audit-from">
            <input id="audit-from" type="date" value={dateFrom} onChange={(e) => applyFilters(() => setDateFrom(e.target.value))} />
          </FilterBarField>
          <FilterBarField label="To" htmlFor="audit-to">
            <input id="audit-to" type="date" value={dateTo} onChange={(e) => applyFilters(() => setDateTo(e.target.value))} />
          </FilterBarField>
        </FilterBar>
      </Card>

      <Card>
        {entries === null ? (
          <SkeletonRows rows={6} columns={5} />
        ) : visibleEntries.length === 0 ? (
          <EmptyState
            icon={<HistoryIcon width={26} height={26} />}
            title="No matching audit events"
            description="Try widening the date range or clearing a filter."
          />
        ) : (
          <>
            <Table columns={columns} rows={visibleEntries} getRowKey={(e) => e.id} />
            <div className="pagination">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </Button>
              <span className="pagination__page">
                Page {page} of {lastPage} ({total} total)
              </span>
              <Button variant="secondary" size="sm" disabled={page >= lastPage} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </>
        )}
      </Card>

      {detail && (
        <Modal title="Audit event" onClose={() => setDetail(null)}>
          <dl className="audit-changes">
            <div>
              <strong>Occurred at:</strong> {formatDateTime(detail.occurred_at)}
            </div>
            <div>
              <strong>Actor:</strong> {detail.actor_type} <code>{detail.actor_id}</code>
            </div>
            <div>
              <strong>Action:</strong> <code>{detail.action}</code>
            </div>
            <div>
              <strong>Target:</strong> {detail.target_type} <code>{detail.target_id}</code>
            </div>
            <div>
              <strong>Result:</strong> <Badge tone={toneForAuditResult(detail.result)}>{detail.result}</Badge>
            </div>
            <div>
              <strong>Correlation ID:</strong> <code>{detail.correlation_id}</code>
            </div>
            {detail.source_ip && (
              <div>
                <strong>Source IP:</strong> <code>{detail.source_ip}</code>
              </div>
            )}
          </dl>
          {detail.changes && (
            <div>
              <strong>Changes</strong>
              <ul className="audit-changes">
                {Object.entries(detail.changes).map(([field, diff]) => (
                  <li key={field}>
                    <code>{field}</code>: {JSON.stringify(diff.old)} &rarr; {JSON.stringify(diff.new)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
