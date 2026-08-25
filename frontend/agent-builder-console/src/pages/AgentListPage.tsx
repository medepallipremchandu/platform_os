import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { archiveAgent, listAgents } from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { ArchiveIcon, LockIcon, PlusIcon, SparkleIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import { toneForAgentStatus } from "../lib/tone";
import type { AgentStatus, AgentSummary } from "../types";

type StatusFilter = "" | AgentStatus;

export default function AgentListPage() {
  const canRead = hasPermission(PERMISSIONS.AGENTS_READ);
  const canWrite = hasPermission(PERMISSIONS.AGENTS_WRITE);
  const canArchive = hasPermission(PERMISSIONS.AGENTS_PUBLISH);

  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState<AgentSummary | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  // --- Search / filter / sort ---
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function refresh() {
    if (!canRead) return;
    // Fetch archived agents too (include_archived=true) so the "Archived" status filter below
    // has something to show - the default listing hides them.
    listAgents({ includeArchived: true })
      .then(setAgents)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(refresh, [canRead]);

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }

  const visibleAgents = useMemo(() => {
    if (!agents) return agents;
    const q = search.trim().toLowerCase();
    const filtered = agents.filter((a) => {
      if (q && !(a.name.toLowerCase().includes(q) || a.agent_code.toLowerCase().includes(q))) return false;
      if (statusFilter && a.status !== statusFilter) return false;
      return true;
    });
    return sortRows(filtered, sortKey, sortDirection, {
      name: (a) => a.name.toLowerCase(),
      created_at: (a) => a.created_at,
    });
  }, [agents, search, statusFilter, sortKey, sortDirection]);

  async function confirmArchive() {
    if (!archiving) return;
    setArchiveLoading(true);
    try {
      await archiveAgent(archiving.id);
      setArchiving(null);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setArchiveLoading(false);
    }
  }

  const columns: Column<AgentSummary>[] = [
    { key: "code", header: "Code", render: (a) => <Badge tone="neutral">{a.agent_code}</Badge> },
    { key: "name", header: "Name", sortable: true, render: (a) => a.name },
    { key: "model", header: "Primary model", render: (a) => a.primary_model.name },
    {
      key: "status",
      header: "Status",
      render: (a) => <Badge tone={toneForAgentStatus(a.status)}>{a.status}</Badge>,
    },
    { key: "created_by", header: "Created by", render: (a) => a.created_by || "-" },
    { key: "created_at", header: "Created on", sortable: true, render: (a) => formatDateTime(a.created_at) },
    ...(canArchive
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (a: AgentSummary) =>
              a.status !== "archived" ? (
                <Button
                  variant="danger"
                  size="sm"
                  icon={<ArchiveIcon width={14} height={14} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setArchiving(a);
                  }}
                >
                  Archive
                </Button>
              ) : null,
          },
        ]
      : []),
  ];

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader title="Agents" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view agents (talentos.agentbuilder.agents.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Agents"
        subtitle="Reusable AI tasks: a prompt template bound to a model, with limits - the AI layer every other service calls through."
        actions={
          canWrite && (
            <Link to="/agents/new">
              <Button icon={<PlusIcon width={16} height={16} />}>New agent</Button>
            </Link>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <div className="filter-bar">
          <div className="filter-bar__field" style={{ minWidth: 240 }}>
            <label htmlFor="agent-search">Search</label>
            <SearchInput id="agent-search" value={search} onChange={setSearch} placeholder="Search by name or code" />
          </div>
          <div className="filter-bar__field">
            <label htmlFor="agent-status-filter">Status</label>
            <select id="agent-status-filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="published">Published</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>
      </Card>

      <Card>
        {visibleAgents === null ? (
          <SkeletonRows rows={4} columns={6} />
        ) : agents && agents.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No agents yet"
            description="Create an agent: pick a model, write a prompt template, and publish it to get an invoke credential."
            action={
              canWrite ? (
                <Link to="/agents/new">
                  <Button>New agent</Button>
                </Link>
              ) : undefined
            }
          />
        ) : visibleAgents.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No agents match your filters"
            description="Try clearing the search text or resetting the status filter."
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleAgents}
            getRowKey={(a) => a.id}
            getRowHref={(a) => `/agents/${a.id}`}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
        )}
      </Card>

      {archiving && (
        <ConfirmDialog
          title="Archive agent"
          message={`Archive "${archiving.name}"? Archived agents can no longer be invoked or edited - their invoke credential is revoked immediately. This can't be undone; create a new agent if you need to bring it back.`}
          confirmLabel="Archive"
          loading={archiveLoading}
          onConfirm={confirmArchive}
          onCancel={() => setArchiving(null)}
        />
      )}
    </div>
  );
}
