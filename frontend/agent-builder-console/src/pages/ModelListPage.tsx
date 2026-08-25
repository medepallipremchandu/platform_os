import { useEffect, useMemo, useState } from "react";
import { createModel, deactivateModel, listModels, updateModel } from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { EditIcon, LockIcon, PlusIcon, SparkleIcon, TrashIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import type { Model, ModelProvider } from "../types";

type ProviderFilter = "" | ModelProvider;

export default function ModelListPage() {
  const canRead = hasPermission(PERMISSIONS.AGENTS_READ);
  const canManage = hasPermission(PERMISSIONS.MODELS_MANAGE);

  const [models, setModels] = useState<Model[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [provider, setProvider] = useState<ModelProvider>("claude");
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [apiVersion, setApiVersion] = useState("");

  // --- Search / filter / sort ---
  const [search, setSearch] = useState("");
  const [providerFilter, setProviderFilter] = useState<ProviderFilter>("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  // --- Edit modal ---
  const [editing, setEditing] = useState<Model | null>(null);
  const [editName, setEditName] = useState("");
  const [editApiKey, setEditApiKey] = useState("");
  const [editEndpoint, setEditEndpoint] = useState("");
  const [editApiVersion, setEditApiVersion] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // --- Deactivate confirm ---
  const [deactivating, setDeactivating] = useState<Model | null>(null);
  const [deactivateLoading, setDeactivateLoading] = useState(false);

  function refresh() {
    if (!canRead) return;
    listModels()
      .then(setModels)
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

  const visibleModels = useMemo(() => {
    if (!models) return models;
    const q = search.trim().toLowerCase();
    const filtered = models.filter((m) => {
      if (
        q &&
        !(
          m.name.toLowerCase().includes(q) ||
          m.model_code.toLowerCase().includes(q) ||
          m.model_id.toLowerCase().includes(q)
        )
      )
        return false;
      if (providerFilter && m.provider !== providerFilter) return false;
      return true;
    });
    return sortRows(filtered, sortKey, sortDirection, {
      name: (m) => m.name.toLowerCase(),
      created_at: (m) => m.created_at,
    });
  }, [models, search, providerFilter, sortKey, sortDirection]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createModel({
        name,
        provider,
        model_id: modelId,
        api_key: apiKey,
        endpoint: provider === "azure_openai" ? endpoint : undefined,
        api_version: provider === "azure_openai" ? apiVersion : undefined,
      });
      setName("");
      setModelId("");
      setApiKey("");
      setEndpoint("");
      setApiVersion("");
      setShowForm(false);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  function openEdit(m: Model) {
    setEditing(m);
    setEditName(m.name);
    setEditApiKey("");
    setEditEndpoint(m.endpoint || "");
    setEditApiVersion(m.api_version || "");
    setEditError(null);
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await updateModel(editing.id, {
        name: editName !== editing.name ? editName : undefined,
        api_key: editApiKey || undefined,
        endpoint: editing.provider === "azure_openai" ? editEndpoint : undefined,
        api_version: editing.provider === "azure_openai" ? editApiVersion : undefined,
      });
      setEditing(null);
      refresh();
    } catch (err) {
      setEditError(extractErrorMessage(err));
    } finally {
      setEditSaving(false);
    }
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setDeactivateLoading(true);
    try {
      await deactivateModel(deactivating.id);
      setDeactivating(null);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDeactivateLoading(false);
    }
  }

  const columns: Column<Model>[] = [
    { key: "code", header: "Code", render: (m) => <Badge tone="neutral">{m.model_code}</Badge> },
    { key: "name", header: "Name", sortable: true, render: (m) => m.name },
    { key: "provider", header: "Provider", render: (m) => <Badge tone="brand">{m.provider}</Badge> },
    { key: "model_id", header: "Model / deployment", render: (m) => <code>{m.model_id}</code> },
    { key: "created_by", header: "Registered by", render: (m) => m.created_by || "-" },
    { key: "created_at", header: "Registered on", sortable: true, render: (m) => formatDateTime(m.created_at) },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (m: Model) => (
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<EditIcon width={14} height={14} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(m);
                  }}
                >
                  Edit
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon={<TrashIcon width={14} height={14} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeactivating(m);
                  }}
                >
                  Deactivate
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader title="Models" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view models (talentos.agentbuilder.agents.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Models"
        subtitle="The catalog of ready-to-use model deployments agents pick from. Credentials are encrypted at rest."
        actions={
          canManage && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={() => setShowForm((v) => !v)}>
              {showForm ? "Cancel" : "Register model"}
            </Button>
          )
        }
      />

      {showForm && canManage && (
        <Card title="Register a model">
          <form onSubmit={handleSubmit} className="jd-form">
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude Sonnet 5" required />
            </label>
            <label>
              Provider
              <select value={provider} onChange={(e) => setProvider(e.target.value as ModelProvider)}>
                <option value="claude">Claude (Anthropic)</option>
                <option value="azure_openai">Azure OpenAI</option>
              </select>
            </label>
            <label>
              {provider === "claude" ? "Model name" : "Deployment name"}
              <input value={modelId} onChange={(e) => setModelId(e.target.value)} required />
            </label>
            <label>
              API key
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
            </label>
            {provider === "azure_openai" && (
              <>
                <label>
                  Endpoint
                  <input
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    placeholder="https://your-resource.openai.azure.com"
                    required
                  />
                </label>
                <label>
                  API version
                  <input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} placeholder="2025-04-01-preview" required />
                </label>
              </>
            )}
            <Button type="submit" icon={<SparkleIcon width={16} height={16} />} loading={saving}>
              Register model
            </Button>
          </form>
          {error && <p className="error-text">{error}</p>}
        </Card>
      )}

      <Card>
        <div className="filter-bar">
          <div className="filter-bar__field" style={{ minWidth: 240 }}>
            <label htmlFor="model-search">Search</label>
            <SearchInput id="model-search" value={search} onChange={setSearch} placeholder="Search by name, code, or model id" />
          </div>
          <div className="filter-bar__field">
            <label htmlFor="model-provider-filter">Provider</label>
            <select
              id="model-provider-filter"
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value as ProviderFilter)}
            >
              <option value="">All</option>
              <option value="claude">Claude</option>
              <option value="azure_openai">Azure OpenAI</option>
            </select>
          </div>
        </div>
      </Card>

      <Card>
        {!showForm && error && <p className="error-text">{error}</p>}
        {visibleModels === null ? (
          <SkeletonRows rows={3} columns={6} />
        ) : models && models.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No models registered yet"
            description="Register a Claude or Azure OpenAI deployment so agents have something to run on."
          />
        ) : visibleModels.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No models match your filters"
            description="Try clearing the search text or resetting the provider filter."
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleModels}
            getRowKey={(m) => m.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
        )}
      </Card>

      {editing && (
        <Modal
          title={`Edit ${editing.name}`}
          onClose={() => setEditing(null)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setEditing(null)} disabled={editSaving}>
                Cancel
              </Button>
              <Button type="submit" form="edit-model-form" loading={editSaving}>
                Save changes
              </Button>
            </>
          }
        >
          <form id="edit-model-form" onSubmit={handleEditSubmit} className="jd-form">
            <label>
              Name
              <input value={editName} onChange={(e) => setEditName(e.target.value)} required />
            </label>
            <p className="hint-text">
              Provider (<Badge tone="brand">{editing.provider}</Badge>) and model/deployment ID (
              <code>{editing.model_id}</code>) can't be changed here - register a new model instead if you need a
              different one.
            </p>
            <label>
              New API key <span className="hint-text">(leave blank to keep the current one)</span>
              <input type="password" value={editApiKey} onChange={(e) => setEditApiKey(e.target.value)} />
            </label>
            {editing.provider === "azure_openai" && (
              <>
                <label>
                  Endpoint
                  <input value={editEndpoint} onChange={(e) => setEditEndpoint(e.target.value)} />
                </label>
                <label>
                  API version
                  <input value={editApiVersion} onChange={(e) => setEditApiVersion(e.target.value)} />
                </label>
              </>
            )}
          </form>
          {editError && <p className="error-text">{editError}</p>}
        </Modal>
      )}

      {deactivating && (
        <ConfirmDialog
          title="Deactivate model"
          message={`Deactivate "${deactivating.name}"? It will no longer be offered when creating or editing agents, but agents already using it keep working.`}
          confirmLabel="Deactivate"
          loading={deactivateLoading}
          onConfirm={confirmDeactivate}
          onCancel={() => setDeactivating(null)}
        />
      )}
    </div>
  );
}
