import { type FormEvent, useEffect, useMemo, useState } from "react";
import { extractErrorMessage } from "../api/client";
import { listOrgUsers } from "../api/iam";
import { createProvider, listProviders, revokeProvider, updateProvider } from "../api/voiceAgent";
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
import VisibilityPicker from "../components/ui/VisibilityPicker";
import { EditIcon, LockIcon, PlusIcon, TargetIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import { toneForRevocation, toneForVisibility } from "../lib/tone";
import type { OrgUser, ProviderType, TelephonyProviderConfig, Visibility } from "../types";

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [{ value: "twilio", label: "Twilio" }];

type StatusFilter = "" | "active" | "revoked";
type VisibilityFilter = "" | Visibility;

export default function ProvidersPage() {
  const canRead = hasPermission(PERMISSIONS.PROVIDERS_READ);
  const canManage = hasPermission(PERMISSIONS.PROVIDERS_MANAGE);

  const [providers, setProviders] = useState<TelephonyProviderConfig[] | null>(null);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<TelephonyProviderConfig | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);

  // --- Search / filter / sort ---
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [visibilityFilter, setVisibilityFilter] = useState<VisibilityFilter>("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  // --- Create form state ---
  const [name, setName] = useState("");
  const [providerType, setProviderType] = useState<ProviderType>("twilio");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [accountSid, setAccountSid] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [fromNumber, setFromNumber] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("organization");
  const [grantUserIds, setGrantUserIds] = useState<string[]>([]);

  // --- Edit form state ---
  const [editing, setEditing] = useState<TelephonyProviderConfig | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editPhoneNumber, setEditPhoneNumber] = useState("");
  const [editAccountSid, setEditAccountSid] = useState("");
  const [editAuthToken, setEditAuthToken] = useState("");
  const [editFromNumber, setEditFromNumber] = useState("");

  function refresh() {
    if (!canRead) return;
    // Fetch revoked providers too (include_revoked=true) so the "Revoked" status filter below has
    // something to show - the default listing hides them, same as CallAgentsPage/is_active.
    listProviders(true)
      .then(setProviders)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(refresh, [canRead]);

  useEffect(() => {
    if (!showForm || visibility !== "restricted") return;
    listOrgUsers()
      .then(setUsers)
      .catch((err) => setUsersError(extractErrorMessage(err)));
  }, [showForm, visibility]);

  function resetForm() {
    setName("");
    setProviderType("twilio");
    setPhoneNumber("");
    setAccountSid("");
    setAuthToken("");
    setFromNumber("");
    setVisibility("organization");
    setGrantUserIds([]);
    setSaveError(null);
  }

  function openCreate() {
    resetForm();
    setShowForm(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      const credentials: Record<string, string> = providerType === "twilio" ? { accountSid, authToken, fromNumber } : {};
      await createProvider({
        name,
        provider: providerType,
        phone_number: phoneNumber,
        credentials,
        visibility,
        grant_user_ids: visibility === "restricted" ? grantUserIds : undefined,
      });
      setShowForm(false);
      refresh();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  function openEdit(p: TelephonyProviderConfig) {
    setEditName(p.name);
    setEditPhoneNumber(p.phone_number);
    setEditAccountSid("");
    setEditAuthToken("");
    setEditFromNumber("");
    setEditError(null);
    setEditing(p);
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    const credentialFields = [editAccountSid, editAuthToken, editFromNumber];
    const filledCount = credentialFields.filter((v) => v.trim() !== "").length;
    if (filledCount > 0 && filledCount < credentialFields.length) {
      setEditError("Fill in all three credential fields to replace them, or leave all three blank to keep the existing ones.");
      return;
    }
    setEditSaving(true);
    setEditError(null);
    try {
      await updateProvider(editing.id, {
        name: editName,
        phone_number: editPhoneNumber,
        credentials: filledCount === credentialFields.length ? { accountSid: editAccountSid, authToken: editAuthToken, fromNumber: editFromNumber } : undefined,
      });
      setEditing(null);
      refresh();
    } catch (err) {
      setEditError(extractErrorMessage(err));
    } finally {
      setEditSaving(false);
    }
  }

  async function confirmRevoke() {
    if (!revoking) return;
    setRevokeLoading(true);
    try {
      await revokeProvider(revoking.id);
      setRevoking(null);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRevokeLoading(false);
    }
  }

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }

  const visibleProviders = useMemo(() => {
    if (!providers) return providers;
    const q = search.trim().toLowerCase();
    const filtered = providers.filter((p) => {
      if (q && !(p.name.toLowerCase().includes(q) || p.phone_number.toLowerCase().includes(q))) return false;
      if (statusFilter === "active" && p.revoked_at) return false;
      if (statusFilter === "revoked" && !p.revoked_at) return false;
      if (visibilityFilter && p.visibility !== visibilityFilter) return false;
      return true;
    });
    return sortRows(filtered, sortKey, sortDirection, {
      name: (p) => p.name.toLowerCase(),
      created_at: (p) => p.created_at,
    });
  }, [providers, search, statusFilter, visibilityFilter, sortKey, sortDirection]);

  const columns: Column<TelephonyProviderConfig>[] = [
    { key: "name", header: "Name", sortable: true, render: (p) => p.name },
    { key: "provider", header: "Provider", render: (p) => <Badge tone="brand">{p.provider}</Badge> },
    { key: "phone_number", header: "Phone number", render: (p) => <code>{p.phone_number}</code> },
    {
      key: "visibility",
      header: "Visibility",
      render: (p) => <Badge tone={toneForVisibility(p.visibility)}>{p.visibility === "organization" ? "Organization" : "Restricted"}</Badge>,
    },
    { key: "created_by", header: "Created by", render: (p) => p.created_by || "-" },
    { key: "created_at", header: "Created on", sortable: true, render: (p) => formatDateTime(p.created_at) },
    {
      key: "status",
      header: "Status",
      render: (p) => <Badge tone={toneForRevocation(p.revoked_at)}>{p.revoked_at ? "Revoked" : "Active"}</Badge>,
    },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (p: TelephonyProviderConfig) => (
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                {!p.revoked_at && (
                  <Button variant="secondary" size="sm" icon={<EditIcon width={14} height={14} />} onClick={() => openEdit(p)}>
                    Edit
                  </Button>
                )}
                {!p.revoked_at && (
                  <Button variant="danger" size="sm" onClick={() => setRevoking(p)}>
                    Revoke
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
        <PageHeader title="Providers" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view telephony providers (talentos.voiceagent.providers.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Providers"
        subtitle="Telephony provider credentials (e.g. Twilio) used to place outbound calls. Credentials are write-only - never returned once saved."
        actions={
          canManage && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={openCreate}>
              New provider
            </Button>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <div className="filter-bar">
          <div className="filter-bar__field" style={{ minWidth: 240 }}>
            <label htmlFor="provider-search">Search</label>
            <SearchInput id="provider-search" value={search} onChange={setSearch} placeholder="Search by name or phone number" />
          </div>
          <div className="filter-bar__field">
            <label htmlFor="provider-visibility-filter">Visibility</label>
            <select
              id="provider-visibility-filter"
              value={visibilityFilter}
              onChange={(e) => setVisibilityFilter(e.target.value as VisibilityFilter)}
            >
              <option value="">All</option>
              <option value="organization">Organization</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          <div className="filter-bar__field">
            <label htmlFor="provider-status-filter">Status</label>
            <select id="provider-status-filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="revoked">Revoked</option>
            </select>
          </div>
        </div>
      </Card>

      <Card>
        {visibleProviders === null ? (
          <SkeletonRows rows={3} columns={6} />
        ) : providers && providers.length === 0 ? (
          <EmptyState
            icon={<TargetIcon width={26} height={26} />}
            title="No providers registered yet"
            description="Register a telephony provider's credentials before creating a call agent or placing a call."
            action={canManage ? <Button onClick={openCreate}>New provider</Button> : undefined}
          />
        ) : visibleProviders.length === 0 ? (
          <EmptyState
            icon={<TargetIcon width={26} height={26} />}
            title="No providers match your filters"
            description="Try clearing the search text or resetting the visibility/status filters."
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleProviders}
            getRowKey={(p) => p.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
        )}
      </Card>

      {showForm && (
        <Modal title="Register a provider" onClose={() => setShowForm(false)} wide>
          <form className="form" onSubmit={handleSubmit}>
            {saveError && <p className="error-text">{saveError}</p>}
            <div className="form__row">
              <label>
                Name
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Primary Twilio line" required />
              </label>
              <label>
                Provider
                <select value={providerType} onChange={(e) => setProviderType(e.target.value as ProviderType)}>
                  {PROVIDER_TYPES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Phone number
              <input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+15551234567"
                required
              />
            </label>

            <div className="form__section-title">Credentials</div>
            {providerType === "twilio" && (
              <>
                <label>
                  Account SID
                  <input value={accountSid} onChange={(e) => setAccountSid(e.target.value)} placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" required />
                </label>
                <label>
                  Auth token
                  <input type="password" value={authToken} onChange={(e) => setAuthToken(e.target.value)} required />
                </label>
                <label>
                  From number
                  <input value={fromNumber} onChange={(e) => setFromNumber(e.target.value)} placeholder="+15551234567" required />
                </label>
              </>
            )}

            <hr className="form__divider" />

            <VisibilityPicker
              visibility={visibility}
              onVisibilityChange={setVisibility}
              grantUserIds={grantUserIds}
              onGrantUserIdsChange={setGrantUserIds}
              users={users}
              usersError={usersError}
            />

            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                Register provider
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {editing && (
        <Modal title={`Edit "${editing.name}"`} onClose={() => setEditing(null)} wide>
          <form className="form" onSubmit={handleEditSubmit}>
            {editError && <p className="error-text">{editError}</p>}
            <label>
              Name
              <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="e.g. Primary Twilio line" required />
            </label>
            <label>
              Phone number
              <input value={editPhoneNumber} onChange={(e) => setEditPhoneNumber(e.target.value)} placeholder="+15551234567" required />
            </label>

            <div className="form__section-title">Credentials</div>
            <p className="hint-text">Leave all three fields blank to keep the existing credentials - they're never shown here once saved.</p>
            <label>
              Account SID
              <input value={editAccountSid} onChange={(e) => setEditAccountSid(e.target.value)} placeholder="Leave blank to keep existing" autoComplete="off" />
            </label>
            <label>
              Auth token
              <input type="password" value={editAuthToken} onChange={(e) => setEditAuthToken(e.target.value)} placeholder="Leave blank to keep existing" autoComplete="new-password" />
            </label>
            <label>
              From number
              <input value={editFromNumber} onChange={(e) => setEditFromNumber(e.target.value)} placeholder="Leave blank to keep existing" autoComplete="off" />
            </label>

            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)} disabled={editSaving}>
                Cancel
              </Button>
              <Button type="submit" loading={editSaving}>
                Save changes
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke provider"
          message={`Revoke "${revoking.name}"? Any call agent configs still pointing at it will stop being able to place new calls.`}
          confirmLabel="Revoke"
          loading={revokeLoading}
          onConfirm={confirmRevoke}
          onCancel={() => setRevoking(null)}
        />
      )}
    </div>
  );
}
