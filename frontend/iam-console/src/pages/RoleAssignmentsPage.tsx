import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import {
  createRoleAssignment,
  listOrgUsers,
  listRoleAssignments,
  listRoleDefinitions,
  listServicePrincipals,
  revokeRoleAssignment,
} from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import FilterBar, { FilterBarField } from "../components/ui/FilterBar";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import SearchableSelect from "../components/ui/SearchableSelect";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column, type SortDirection } from "../components/ui/Table";
import { LinkIcon, PlusIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission, principalLabelFor } from "../lib/permissions";
import { toneForRevocation, toneForScopeType } from "../lib/tone";
import {
  KNOWN_SERVICES,
  type OrgUser,
  type PrincipalType,
  type RoleAssignment,
  type RoleDefinition,
  type ScopeType,
  type ServiceName,
  type ServicePrincipal,
} from "../types";

type SortKey = "principal" | "created_at";

export default function RoleAssignmentsPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canManage = hasPermission(PERMISSIONS.ROLE_ASSIGNMENTS_MANAGE);
  const [searchParams] = useSearchParams();

  const [assignments, setAssignments] = useState<RoleAssignment[] | null>(null);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [servicePrincipals, setServicePrincipals] = useState<ServicePrincipal[]>([]);
  const [roles, setRoles] = useState<RoleDefinition[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [principalTypeFilter, setPrincipalTypeFilter] = useState<PrincipalType | "">("");
  const [scopeTypeFilter, setScopeTypeFilter] = useState<ScopeType | "">("");
  const [showRevoked, setShowRevoked] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const [showForm, setShowForm] = useState(false);
  const [principalType, setPrincipalType] = useState<PrincipalType>("user");
  const [principalId, setPrincipalId] = useState<string | null>(searchParams.get("principal_id"));
  const [roleDefinitionId, setRoleDefinitionId] = useState<string | null>(null);
  const [scopeType, setScopeType] = useState<ScopeType>("organization");
  const [serviceName, setServiceName] = useState<ServiceName>(KNOWN_SERVICES[0]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<RoleAssignment | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);

  function load() {
    if (!orgId) return;
    Promise.all([
      listRoleAssignments(orgId, showRevoked),
      listOrgUsers(orgId),
      listServicePrincipals(orgId),
      listRoleDefinitions(orgId),
    ])
      .then(([assignmentList, userList, spList, roleList]) => {
        setAssignments(assignmentList);
        setUsers(userList);
        setServicePrincipals(spList);
        setRoles(roleList);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(load, [orgId, showRevoked]);

  useEffect(() => {
    if (searchParams.get("principal_id")) setShowForm(true);
  }, [searchParams]);

  const principalOptions = useMemo(() => {
    if (principalType === "user") {
      return users.map((u) => ({ value: u.user_id, label: u.display_name || u.email, description: u.email }));
    }
    return servicePrincipals.map((sp) => ({ value: sp.id, label: sp.name, description: sp.client_id }));
  }, [principalType, users, servicePrincipals]);

  function openCreate() {
    setPrincipalType("user");
    setPrincipalId(null);
    setRoleDefinitionId(null);
    setScopeType("organization");
    setServiceName(KNOWN_SERVICES[0]);
    setSaveError(null);
    setShowForm(true);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!orgId || !principalId || !roleDefinitionId) {
      setSaveError("Choose a principal and a role.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await createRoleAssignment({
        principal_type: principalType,
        principal_id: principalId,
        role_definition_id: roleDefinitionId,
        organization_id: orgId,
        scope_type: scopeType,
        service_name: scopeType === "service" ? serviceName : undefined,
      });
      setShowForm(false);
      load();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function confirmRevoke() {
    if (!revoking) return;
    setRevokeLoading(true);
    try {
      await revokeRoleAssignment(revoking.id);
      setRevoking(null);
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRevokeLoading(false);
    }
  }

  function toggleSort(key: string) {
    if (key !== "principal" && key !== "created_at") return;
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection(key === "created_at" ? "desc" : "asc");
    }
  }

  // Client-side search/filter/sort over the already-fetched list - this is admin-configured
  // access control data (dozens to low hundreds of rows per org), not application-scale data, so
  // it doesn't need server-side pagination. Revisit if an org's assignment count ever grows large
  // enough that this stops feeling instant.
  const visibleAssignments = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = (assignments || []).filter((a) => {
      if (principalTypeFilter && a.principal_type !== principalTypeFilter) return false;
      if (scopeTypeFilter && a.scope_type !== scopeTypeFilter) return false;
      if (q) {
        const label = principalLabelFor(a.principal_type, a.principal_id, users, servicePrincipals).toLowerCase();
        if (!label.includes(q)) return false;
      }
      return true;
    });
    list = [...list].sort((a, b) => {
      let diff: number;
      if (sortKey === "principal") {
        const labelA = principalLabelFor(a.principal_type, a.principal_id, users, servicePrincipals);
        const labelB = principalLabelFor(b.principal_type, b.principal_id, users, servicePrincipals);
        diff = labelA.localeCompare(labelB);
      } else {
        diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDirection === "asc" ? diff : -diff;
    });
    return list;
  }, [assignments, query, principalTypeFilter, scopeTypeFilter, sortKey, sortDirection, users, servicePrincipals]);

  const columns: Column<RoleAssignment>[] = [
    {
      key: "principal",
      header: "Principal",
      sortable: true,
      render: (a) => (
        <div>
          <div>{principalLabelFor(a.principal_type, a.principal_id, users, servicePrincipals)}</div>
          <span className="hint-text">{a.principal_type === "user" ? "User" : "Service principal"}</span>
        </div>
      ),
    },
    { key: "role", header: "Role", render: (a) => a.role_definition_name || "-" },
    {
      key: "scope",
      header: "Scope",
      render: (a) => (
        <Badge tone={toneForScopeType(a.scope_type)}>
          {a.scope_type === "organization" ? "Organization" : `Service: ${a.scope_id.split(":").pop()}`}
        </Badge>
      ),
    },
    ...(showRevoked
      ? [
          {
            key: "status",
            header: "Status",
            render: (a: RoleAssignment) => <Badge tone={toneForRevocation(a.revoked_at)}>{a.revoked_at ? "Revoked" : "Active"}</Badge>,
          },
        ]
      : []),
    {
      key: "created_at",
      header: "Created",
      sortable: true,
      render: (a) => new Date(a.created_at).toLocaleDateString(),
    },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (a: RoleAssignment) =>
              a.revoked_at ? (
                <span className="hint-text">Revoked</span>
              ) : (
                <Button variant="danger" size="sm" onClick={() => setRevoking(a)}>
                  Revoke
                </Button>
              ),
          },
        ]
      : []),
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Access control"
        title="Role assignments"
        subtitle="Bind a user or service principal to a role at organization or service scope."
        actions={
          canManage && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={openCreate}>
              New assignment
            </Button>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        <FilterBar
          trailing={
            <FilterBarField label="Revoked">
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 400 }}>
                <input type="checkbox" checked={showRevoked} onChange={(e) => setShowRevoked(e.target.checked)} />
                Show revoked
              </label>
            </FilterBarField>
          }
        >
          <FilterBarField label="Search" htmlFor="ra-search">
            <SearchInput value={query} onChange={setQuery} placeholder="Search by principal name..." />
          </FilterBarField>
          <FilterBarField label="Principal type" htmlFor="ra-principal-type">
            <select
              id="ra-principal-type"
              value={principalTypeFilter}
              onChange={(e) => setPrincipalTypeFilter(e.target.value as PrincipalType | "")}
            >
              <option value="">All</option>
              <option value="user">User</option>
              <option value="service_principal">Service principal</option>
            </select>
          </FilterBarField>
          <FilterBarField label="Scope type" htmlFor="ra-scope-type">
            <select id="ra-scope-type" value={scopeTypeFilter} onChange={(e) => setScopeTypeFilter(e.target.value as ScopeType | "")}>
              <option value="">All</option>
              <option value="organization">Organization</option>
              <option value="service">Service</option>
            </select>
          </FilterBarField>
        </FilterBar>
      </Card>

      <Card>
        {assignments === null ? (
          <SkeletonRows rows={5} columns={4} />
        ) : visibleAssignments.length === 0 ? (
          <EmptyState
            icon={<LinkIcon width={26} height={26} />}
            title={assignments.length === 0 ? "No role assignments yet" : "No role assignments match your filters"}
            description={assignments.length === 0 ? "Assign a role to a user or service principal to grant access." : undefined}
            action={assignments.length === 0 && canManage ? <Button onClick={openCreate}>New assignment</Button> : undefined}
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleAssignments}
            getRowKey={(a) => a.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
        )}
      </Card>

      {showForm && (
        <Modal title="New role assignment" onClose={() => setShowForm(false)}>
          <form className="form" onSubmit={handleSubmit}>
            {saveError && <p className="error-text">{saveError}</p>}
            <label>
              Principal type
              <select
                value={principalType}
                onChange={(e) => {
                  setPrincipalType(e.target.value as PrincipalType);
                  setPrincipalId(null);
                }}
              >
                <option value="user">User</option>
                <option value="service_principal">Service principal</option>
              </select>
            </label>
            <label>
              Principal
              <SearchableSelect
                options={principalOptions}
                value={principalId}
                onChange={setPrincipalId}
                placeholder={principalType === "user" ? "Search users..." : "Search service principals..."}
              />
            </label>
            <label>
              Role
              <select value={roleDefinitionId ?? ""} onChange={(e) => setRoleDefinitionId(e.target.value || null)} required>
                <option value="" disabled>
                  Choose a role
                </option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                    {role.is_builtin ? " (built-in)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Scope
              <select value={scopeType} onChange={(e) => setScopeType(e.target.value as ScopeType)}>
                <option value="organization">Organization (everywhere in this org)</option>
                <option value="service">Service (one service only)</option>
              </select>
            </label>
            {scopeType === "service" && (
              <label>
                Service
                <select value={serviceName} onChange={(e) => setServiceName(e.target.value as ServiceName)}>
                  {KNOWN_SERVICES.map((service) => (
                    <option key={service} value={service}>
                      {service}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                Create assignment
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke role assignment"
          message={`Remove "${revoking.role_definition_name}" from ${principalLabelFor(revoking.principal_type, revoking.principal_id, users, servicePrincipals)}? This can't be undone from here, but the assignment's history is kept for audit purposes.`}
          confirmLabel="Revoke"
          loading={revokeLoading}
          onConfirm={confirmRevoke}
          onCancel={() => setRevoking(null)}
        />
      )}
    </div>
  );
}
