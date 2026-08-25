import { type FormEvent, useEffect, useMemo, useState } from "react";
import { extractErrorMessage } from "../api/client";
import {
  createOrganization,
  deactivateOrganization,
  listOrganizations,
  listPermissions,
  reactivateOrganization,
  updateOrganizationEntitlements,
} from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import PermissionPicker from "../components/PermissionPicker";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import Table, { type Column, type SortDirection } from "../components/ui/Table";
import { BuildingIcon, EditIcon, PlusIcon } from "../components/ui/icons";
import { formatDate } from "../lib/format";
import { isSuperAdmin } from "../lib/permissions";
import type { Organization, OrganizationWithAdmin, Permission } from "../types";

type Editor = { mode: "create" } | { mode: "entitlements"; org: Organization } | null;

/** Superadmin-only: the platform tier's view of every tenant.
 *
 * Two things happen here that happen nowhere else in the console. Creating an organization also
 * creates its first admin and sets its permission ceiling - one call, because a tenant with no
 * admin is unusable and one with no ceiling can grant nothing. And the ceiling itself is
 * editable afterwards, which is the lever a superadmin has over what an organization is allowed
 * to do at all, independent of how that organization chooses to arrange its own roles.
 */
export default function OrganizationsPage() {
  const { refreshOrganizations } = useAuth();
  const superAdmin = isSuperAdmin();

  const [organizations, setOrganizations] = useState<Organization[] | null>(null);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const [editor, setEditor] = useState<Editor>(null);
  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminDisplayName, setAdminDisplayName] = useState("");
  const [permissionCodes, setPermissionCodes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [created, setCreated] = useState<OrganizationWithAdmin | null>(null);

  const [lifecycleTarget, setLifecycleTarget] = useState<Organization | null>(null);
  const [lifecycleLoading, setLifecycleLoading] = useState(false);

  function load() {
    listOrganizations()
      .then(setOrganizations)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(() => {
    if (!superAdmin) return;
    load();
    listPermissions()
      .then(setCatalog)
      .catch((err) => setError(extractErrorMessage(err)));
  }, [superAdmin]);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = (organizations || []).filter((org) => org.name.toLowerCase().includes(needle));
    const direction = sortDirection === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sortKey === "created_at") return direction * a.created_at.localeCompare(b.created_at);
      if (sortKey === "status") return direction * (Number(a.is_active) - Number(b.is_active));
      if (sortKey === "entitlements") {
        // "Unrestricted" (null) sorts as the largest possible ceiling, because that is what it is.
        const size = (org: Organization) => (org.allowed_permissions ? org.allowed_permissions.length : Infinity);
        return direction * (size(a) - size(b));
      }
      return direction * a.name.localeCompare(b.name);
    });
  }, [organizations, query, sortKey, sortDirection]);

  function onSort(key: string) {
    if (key === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }

  function openCreate() {
    setName("");
    setAdminEmail("");
    setAdminDisplayName("");
    setPermissionCodes([]);
    setSaveError(null);
    setEditor({ mode: "create" });
  }

  function openEntitlements(org: Organization) {
    setPermissionCodes(org.allowed_permissions ?? []);
    setSaveError(null);
    setEditor({ mode: "entitlements", org });
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!editor) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editor.mode === "create") {
        const result = await createOrganization({
          name,
          admin_email: adminEmail,
          admin_display_name: adminDisplayName || undefined,
          allowed_permission_codes: permissionCodes,
        });
        setEditor(null);
        setCreated(result);
      } else {
        await updateOrganizationEntitlements(editor.org.id, { allowed_permission_codes: permissionCodes });
        setEditor(null);
      }
      load();
      refreshOrganizations();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function toggleLifecycle() {
    if (!lifecycleTarget) return;
    setLifecycleLoading(true);
    try {
      if (lifecycleTarget.is_active) {
        await deactivateOrganization(lifecycleTarget.id);
      } else {
        await reactivateOrganization(lifecycleTarget.id);
      }
      setLifecycleTarget(null);
      load();
      refreshOrganizations();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLifecycleLoading(false);
    }
  }

  if (!superAdmin) {
    return (
      <div className="page">
        <PageHeader eyebrow="Platform" title="Organizations" />
        <EmptyState
          icon={<BuildingIcon width={26} height={26} />}
          title="Platform superadmins only"
          description="Creating organizations and setting their permission ceilings sits above every organization, so no organization-scoped permission grants access to this page."
        />
      </div>
    );
  }

  const columns: Column<Organization>[] = [
    { key: "name", header: "Organization", sortable: true, render: (org) => <strong>{org.name}</strong> },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (org) => <Badge tone={org.is_active ? "success" : "neutral"}>{org.is_active ? "Active" : "Deactivated"}</Badge>,
    },
    {
      key: "entitlements",
      header: "Entitlements",
      sortable: true,
      render: (org) =>
        org.allowed_permissions && org.allowed_permissions.length > 0 ? (
          <span title={org.allowed_permissions.join("\n")}>{org.allowed_permissions.length} permissions</span>
        ) : (
          <span className="hint-text" title="No ceiling set - this organization may grant any permission in the catalog.">
            Unrestricted
          </span>
        ),
    },
    { key: "created_at", header: "Created", sortable: true, render: (org) => formatDate(org.created_at) },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (org) => (
        <div className="data-table__actions">
          <Button
            variant="secondary"
            size="sm"
            icon={<EditIcon width={14} height={14} />}
            onClick={() => openEntitlements(org)}
          >
            Entitlements
          </Button>
          <Button variant={org.is_active ? "danger" : "secondary"} size="sm" onClick={() => setLifecycleTarget(org)}>
            {org.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Platform"
        title="Organizations"
        subtitle="Every tenant on the platform. Creating one also creates its first admin and sets the ceiling of what it is allowed to grant."
        actions={
          <Button icon={<PlusIcon width={16} height={16} />} onClick={openCreate}>
            New organization
          </Button>
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card
        title="All organizations"
        actions={<SearchInput value={query} onChange={setQuery} placeholder="Search organizations..." />}
      >
        {organizations === null ? null : rows.length === 0 ? (
          <EmptyState
            icon={<BuildingIcon width={26} height={26} />}
            title={query ? "No organizations match your search" : "No organizations yet"}
            action={!query ? <Button onClick={openCreate}>New organization</Button> : undefined}
          />
        ) : (
          <Table
            columns={columns}
            rows={rows}
            getRowKey={(org) => org.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={onSort}
          />
        )}
      </Card>

      {editor && (
        <Modal
          title={editor.mode === "create" ? "New organization" : `Entitlements - ${editor.org.name}`}
          onClose={() => setEditor(null)}
        >
          <form className="form" onSubmit={handleSave}>
            {saveError && <p className="error-text">{saveError}</p>}

            {editor.mode === "create" && (
              <>
                <label>
                  Organization name
                  <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
                </label>
                <label>
                  Organization admin email
                  <input type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required />
                </label>
                <p className="hint-text">
                  This person is created as an invited user with no password and emailed a link to set one. They get
                  the built-in Organization Admin role at organization scope.
                </p>
                <label>
                  Organization admin name
                  <input type="text" value={adminDisplayName} onChange={(e) => setAdminDisplayName(e.target.value)} />
                </label>
              </>
            )}

            <label>
              {editor.mode === "create" ? "Permissions this organization may grant" : "Permission ceiling"}
              <PermissionPicker catalog={catalog.map((p) => p.code)} selected={permissionCodes} onChange={setPermissionCodes} />
            </label>
            <p className="hint-text">
              {editor.mode === "create"
                ? "At least one is required. Roles inside the organization can only ever grant permissions from this set - anything outside it is stripped from every token, however the role was authored."
                : "Applies on the next token issued to any member. Clearing everything removes the ceiling entirely, letting the organization grant anything in the catalog."}
            </p>

            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setEditor(null)} disabled={saving}>
                Cancel
              </Button>
              <Button
                type="submit"
                loading={saving}
                disabled={editor.mode === "create" && permissionCodes.length === 0}
              >
                {editor.mode === "create" ? "Create organization" : "Save entitlements"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {created && (
        <Modal title="Organization created" onClose={() => setCreated(null)}>
          <p>
            <strong>{created.organization.name}</strong> is ready, and{" "}
            <strong>{created.admin.display_name || created.admin.email}</strong> has been invited as its admin.
          </p>
          <p className="hint-text">
            An email with a set-password link has been queued to {created.admin.email}. Their account stays in the
            "invited" state until they follow it - they cannot sign in before then.
          </p>
          <div className="form__actions">
            <Button onClick={() => setCreated(null)}>Done</Button>
          </div>
        </Modal>
      )}

      {lifecycleTarget && (
        <ConfirmDialog
          title={lifecycleTarget.is_active ? "Deactivate organization" : "Reactivate organization"}
          message={
            lifecycleTarget.is_active
              ? `Deactivate "${lifecycleTarget.name}"? Nothing is deleted, but its members can no longer log into it. Reactivating restores access exactly as it was.`
              : `Reactivate "${lifecycleTarget.name}"? Its members will be able to log in again.`
          }
          confirmLabel={lifecycleTarget.is_active ? "Deactivate" : "Reactivate"}
          loading={lifecycleLoading}
          onConfirm={toggleLifecycle}
          onCancel={() => setLifecycleTarget(null)}
        />
      )}
    </div>
  );
}
