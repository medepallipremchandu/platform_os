import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { listCalls } from "../api/voiceAgent";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { LockIcon, PhoneOutgoingIcon, PlusIcon } from "../components/ui/icons";
import { formatDateTime, humanizeStatus } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { toneForCallStatus } from "../lib/tone";
import { CALL_STATUSES } from "../types";
import type { CallSortKey, CallStatus, CallSummaryRow } from "../types";

const PAGE_SIZE = 25;

export default function CallsPage() {
  const canRead = hasPermission(PERMISSIONS.CALLS_READ);
  const canWrite = hasPermission(PERMISSIONS.CALLS_WRITE);

  const [calls, setCalls] = useState<CallSummaryRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<CallStatus | "">("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<CallSortKey>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canRead) return;
    setCalls(null);
    listCalls({
      status: statusFilter || undefined,
      search: search || undefined,
      sortBy,
      sortDir,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((res) => {
        setCalls(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }, [canRead, statusFilter, search, sortBy, sortDir, page]);

  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function toggleSort(key: string) {
    const sortable = key as CallSortKey;
    if (sortBy === sortable) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(sortable);
      setSortDir("asc");
    }
    setPage(1);
  }

  const columns: Column<CallSummaryRow>[] = [
    { key: "to_number", header: "To", render: (c) => <code>{c.to_number}</code> },
    { key: "from_number", header: "From", render: (c) => (c.from_number ? <code>{c.from_number}</code> : "-") },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (c) => <Badge tone={toneForCallStatus(c.status)}>{humanizeStatus(c.status)}</Badge>,
    },
    {
      key: "attempt_number",
      header: "Attempt",
      sortable: true,
      render: (c) => (c.root_call_id ? `#${c.attempt_number} (retry)` : `#${c.attempt_number}`),
    },
    { key: "created_at", header: "Placed", sortable: true, render: (c) => formatDateTime(c.created_at) },
    { key: "ended_at", header: "Ended", render: (c) => (c.ended_at ? formatDateTime(c.ended_at) : "-") },
    { key: "end_reason", header: "End reason", render: (c) => c.end_reason || "-" },
  ];

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader title="Calls" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view calls (talentos.voiceagent.calls.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Calls"
        subtitle="Every outbound AI-driven call placed through this org - status, transcript, and summary."
        actions={
          canWrite && (
            <Link to="/calls/new">
              <Button icon={<PlusIcon width={16} height={16} />}>Place a call</Button>
            </Link>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <div className="filter-bar">
          <div className="filter-bar__field" style={{ minWidth: 240 }}>
            <label htmlFor="call-search">Search</label>
            <SearchInput
              id="call-search"
              value={search}
              onChange={(v) => {
                setPage(1);
                setSearch(v);
              }}
              placeholder="Search by destination number"
            />
          </div>
          <div className="filter-bar__field">
            <label htmlFor="call-status">Status</label>
            <select
              id="call-status"
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value as CallStatus | "");
              }}
            >
              <option value="">All</option>
              {CALL_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {humanizeStatus(s)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      <Card>
        {calls === null ? (
          <SkeletonRows rows={5} columns={7} />
        ) : calls.length === 0 ? (
          <EmptyState
            icon={<PhoneOutgoingIcon width={26} height={26} />}
            title="No calls yet"
            description="Place a call from a saved call agent, or build one inline for a one-off."
            action={
              canWrite ? (
                <Link to="/calls/new">
                  <Button>Place a call</Button>
                </Link>
              ) : undefined
            }
          />
        ) : (
          <>
            <Table
              columns={columns}
              rows={calls}
              getRowKey={(c) => c.id}
              getRowHref={(c) => `/calls/${c.id}`}
              sortKey={sortBy}
              sortDirection={sortDir}
              onSort={toggleSort}
            />
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
    </div>
  );
}
