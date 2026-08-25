import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { deactivateCallAgentConfig, listCallAgentConfigs, listProviders } from "../api/voiceAgent";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { LockIcon, PlusIcon, SlidersIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import { toneForActiveState, toneForVisibility } from "../lib/tone";
import type { CallAgentConfig, TelephonyProviderConfig, Visibility } from "../types";

type StatusFilter = "" | "active" | "inactive";
type VisibilityFilter = "" | Visibility;

export default function CallAgentsPage() {
  const canRead = hasPermission(PERMISSIONS.CALLAGENTS_READ);
  const canWrite = hasPermission(PERMISSIONS.CALLAGENTS_WRITE);

  const [configs, setConfigs] = useState<CallAgentConfig[] | null>(null);
  const [providers, setProviders] = useState<Record<string, TelephonyProviderConfig>>({});
  const [error, setError] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState<CallAgentConfig | null>(null);
  const [deactivateLoading, setDeactivateLoading] = useState(false);

  // --- Search / filter / sort ---
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [visibilityFilter, setVisibilityFilter] = useState<VisibilityFilter>("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function refresh() {
    if (!canRead) return;
    // Fetch deactivated configs too (include_inactive=true) so the "Inactive" status filter below
    // has something to show - the default listing hides them.
    listCallAgentConfigs(true)
      .then(setConfigs)
      .catch((err) => setError(extractErrorMessage(err)));
    // Providers are used only to show a friendly name next to the raw id - a read failure here
    // (e.g. this principal lacks providers.read) shouldn't block the call agent list itself.
    listProviders(true)
      .then((list) => setProviders(Object.fromEntries(list.map((p) => [p.id, p]))))
      .catch(() => setProviders({}));
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

  const visibleConfigs = useMemo(() => {
    if (!configs) return configs;
    const q = search.trim().toLowerCase();
    const filtered = configs.filter((c) => {
      if (q && !(c.name.toLowerCase().includes(q) || (c.description || "").toLowerCase().includes(q))) return false;
      if (statusFilter === "active" && c.deactivated_at) return false;
      if (statusFilter === "inactive" && !c.deactivated_at) return false;
      if (visibilityFilter && c.visibility !== visibilityFilter) return false;
      return true;
    });
    return sortRows(filtered, sortKey, sortDirection, {
      name: (c) => c.name.toLowerCase(),
      created_at: (c) => c.created_at,
    });
  }, [configs, search, statusFilter, visibilityFilter, sortKey, sortDirection]);

  async function confirmDeactivate() {
    if (!deactivating) return;
    setDeactivateLoading(true);
    try {
      await deactivateCallAgentConfig(deactivating.id);
      setDeactivating(null);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDeactivateLoading(false);
    }
  }

  const columns: Column<CallAgentConfig>[] = [
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (c) => (
        <div>
          <div>{c.name}</div>
          {c.description && <span className="hint-text">{c.description}</span>}
        </div>
      ),
    },
    { key: "provider", header: "Provider", render: (c) => providers[c.telephony_provider_config_id]?.name || <code>{c.telephony_provider_config_id}</code> },
    {
      key: "retry",
      header: "Retry policy",
      render: (c) => `${c.retry_max_attempts} attempts / ${c.retry_interval_minutes}m apart`,
    },
    {
      key: "visibility",
      header: "Visibility",
      render: (c) => <Badge tone={toneForVisibility(c.visibility)}>{c.visibility === "organization" ? "Organization" : "Restricted"}</Badge>,
    },
    {
      key: "status",
      header: "Status",
      render: (c) => <Badge tone={toneForActiveState(c.deactivated_at)}>{c.deactivated_at ? "Deactivated" : "Active"}</Badge>,
    },
    { key: "created_at", header: "Created on", sortable: true, render: (c) => formatDateTime(c.created_at) },
    ...(canWrite
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (c: CallAgentConfig) => (
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <Link to={`/call-agents/${c.id}/edit`} onClick={(e) => e.stopPropagation()}>
                  <Button variant="secondary" size="sm">
                    Edit
                  </Button>
                </Link>
                {!c.deactivated_at && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeactivating(c);
                    }}
                  >
                    Deactivate
                  </Button>
                )}
              </div>
            ),
          },
        ]
      : []),
  ];

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader title="Call Agents" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view call agent configs (talentos.voiceagent.callagents.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Call Agents"
        subtitle="Reusable script + retry policy + provider bundles - pick one when placing a call, or build one inline for a one-off."
        actions={
          canWrite && (
            <Link to="/call-agents/new">
              <Button icon={<PlusIcon width={16} height={16} />}>New call agent</Button>
            </Link>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <div className="filter-bar">
          <div className="filter-bar__field" style={{ minWidth: 240 }}>
            <label htmlFor="call-agent-search">Search</label>
            <SearchInput id="call-agent-search" value={search} onChange={setSearch} placeholder="Search by name or description" />
          </div>
          <div className="filter-bar__field">
            <label htmlFor="call-agent-visibility-filter">Visibility</label>
            <select
              id="call-agent-visibility-filter"
              value={visibilityFilter}
              onChange={(e) => setVisibilityFilter(e.target.value as VisibilityFilter)}
            >
              <option value="">All</option>
              <option value="organization">Organization</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          <div className="filter-bar__field">
            <label htmlFor="call-agent-status-filter">Status</label>
            <select id="call-agent-status-filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>
      </Card>

      <Card>
        {visibleConfigs === null ? (
          <SkeletonRows rows={3} columns={6} />
        ) : configs && configs.length === 0 ? (
          <EmptyState
            icon={<SlidersIcon width={26} height={26} />}
            title="No call agents yet"
            description="Create a call agent: a persona, objective, consent/closing lines, fields to extract, retry policy, and a provider to place calls through."
            action={
              canWrite ? (
                <Link to="/call-agents/new">
                  <Button>New call agent</Button>
                </Link>
              ) : undefined
            }
          />
        ) : visibleConfigs.length === 0 ? (
          <EmptyState
            icon={<SlidersIcon width={26} height={26} />}
            title="No call agents match your filters"
            description="Try clearing the search text or resetting the visibility/status filters."
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleConfigs}
            getRowKey={(c) => c.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
        )}
      </Card>

      {deactivating && (
        <ConfirmDialog
          title="Deactivate call agent"
          message={`Deactivate "${deactivating.name}"? It stays on record but can no longer be used to place new calls.`}
          confirmLabel="Deactivate"
          loading={deactivateLoading}
          onConfirm={confirmDeactivate}
          onCancel={() => setDeactivating(null)}
        />
      )}
    </div>
  );
}
