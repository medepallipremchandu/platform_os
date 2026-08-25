import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { deactivateOrganization, listOrgUsers, listRoleDefinitions, listServicePrincipals, reactivateOrganization, renameOrganization } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import StatCard from "../components/ui/StatCard";
import { EditIcon, HistoryIcon, KeyIcon, ShieldIcon, UsersIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForOrgActive } from "../lib/tone";
import type { OrgUser, RoleDefinition, ServicePrincipal } from "../types";

export default function DashboardPage() {
  const { claims, organizations, refreshOrganizations } = useAuth();
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [roles, setRoles] = useState<RoleDefinition[] | null>(null);
  const [servicePrincipals, setServicePrincipals] = useState<ServicePrincipal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canManageOrg = hasPermission(PERMISSIONS.ORGANIZATIONS_MANAGE);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renameSaving, setRenameSaving] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [lifecycleAction, setLifecycleAction] = useState<"deactivate" | "reactivate" | null>(null);
  const [lifecycleLoading, setLifecycleLoading] = useState(false);

  const orgId = claims?.org_id;
  const currentOrg = organizations.find((org) => org.id === orgId);

  useEffect(() => {
    if (!orgId) return;
    Promise.all([listOrgUsers(orgId), listRoleDefinitions(orgId), listServicePrincipals(orgId)])
      .then(([userList, roleList, spList]) => {
        setUsers(userList);
        setRoles(roleList);
        setServicePrincipals(spList);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }, [orgId]);

  const customRoleCount = (roles || []).filter((r) => !r.is_builtin).length;
  const activeServicePrincipalCount = (servicePrincipals || []).filter((sp) => !sp.revoked_at).length;

  function openRename() {
    setRenameValue(currentOrg?.name || "");
    setRenameError(null);
    setRenaming(true);
  }

  async function handleRename(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setRenameSaving(true);
    setRenameError(null);
    try {
      await renameOrganization(orgId, { name: renameValue });
      setRenaming(false);
      await refreshOrganizations();
    } catch (err) {
      setRenameError(extractErrorMessage(err));
    } finally {
      setRenameSaving(false);
    }
  }

  async function confirmLifecycleAction() {
    if (!orgId || !lifecycleAction) return;
    setLifecycleLoading(true);
    try {
      if (lifecycleAction === "deactivate") {
        await deactivateOrganization(orgId);
      } else {
        await reactivateOrganization(orgId);
      }
      setLifecycleAction(null);
      await refreshOrganizations();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLifecycleLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Overview"
        title={currentOrg?.name || "Your organization"}
        subtitle="Identity and access at a glance: who has access, what roles exist, and what's connected."
        actions={
          canManageOrg &&
          currentOrg && (
            <>
              <Button variant="secondary" icon={<EditIcon width={16} height={16} />} onClick={openRename}>
                Rename
              </Button>
              <Button
                variant={currentOrg.is_active ? "danger" : "primary"}
                onClick={() => setLifecycleAction(currentOrg.is_active ? "deactivate" : "reactivate")}
              >
                {currentOrg.is_active ? "Deactivate" : "Reactivate"}
              </Button>
            </>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      {currentOrg && !currentOrg.is_active && (
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <Badge tone={toneForOrgActive(false)}>Deactivated</Badge>
            <span className="hint-text">
              This organization is deactivated. Its members can no longer sign in until it's reactivated.
            </span>
          </div>
        </Card>
      )}

      <div className="stat-grid">
        <StatCard icon={<UsersIcon />} label="Users" value={users?.length ?? null} hint="Org members" tone="brand" />
        <StatCard
          icon={<ShieldIcon />}
          label="Roles"
          value={roles?.length ?? null}
          hint={roles ? `${customRoleCount} custom` : undefined}
          tone="info"
        />
        <StatCard
          icon={<KeyIcon />}
          label="Service principals"
          value={servicePrincipals?.length ?? null}
          hint={servicePrincipals ? `${activeServicePrincipalCount} active` : undefined}
          tone="warning"
        />
        <StatCard icon={<HistoryIcon />} label="Audit log" value="Live" hint="Every transaction, timestamped" tone="success" />
      </div>

      <Card title="Manage this organization">
        <div className="dashboard-links">
          <Link to="/users">
            <button type="button" className="btn btn--secondary btn--md">
              Manage users
            </button>
          </Link>
          <Link to="/roles">
            <button type="button" className="btn btn--secondary btn--md">
              Manage roles
            </button>
          </Link>
          <Link to="/role-assignments">
            <button type="button" className="btn btn--secondary btn--md">
              Manage role assignments
            </button>
          </Link>
          <Link to="/service-principals">
            <button type="button" className="btn btn--secondary btn--md">
              Manage service principals
            </button>
          </Link>
          {hasPermission(PERMISSIONS.AUDIT_READ) && (
            <Link to="/audit-log">
              <button type="button" className="btn btn--secondary btn--md">
                View audit log
              </button>
            </Link>
          )}
        </div>
      </Card>

      {renaming && (
        <Modal title="Rename organization" onClose={() => setRenaming(false)}>
          <form className="form" onSubmit={handleRename}>
            {renameError && <p className="error-text">{renameError}</p>}
            <label>
              Organization name
              <input type="text" value={renameValue} onChange={(e) => setRenameValue(e.target.value)} required autoFocus />
            </label>
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setRenaming(false)} disabled={renameSaving}>
                Cancel
              </Button>
              <Button type="submit" loading={renameSaving}>
                Save
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {lifecycleAction && currentOrg && (
        <ConfirmDialog
          title={lifecycleAction === "deactivate" ? "Deactivate organization" : "Reactivate organization"}
          message={
            lifecycleAction === "deactivate"
              ? `Deactivate "${currentOrg.name}"? Nothing is deleted - every user, role, and service principal is preserved - but no one will be able to sign in to it until it's reactivated.`
              : `Reactivate "${currentOrg.name}"? Its members will be able to sign in again immediately.`
          }
          confirmLabel={lifecycleAction === "deactivate" ? "Deactivate" : "Reactivate"}
          danger={lifecycleAction === "deactivate"}
          loading={lifecycleLoading}
          onConfirm={confirmLifecycleAction}
          onCancel={() => setLifecycleAction(null)}
        />
      )}
    </div>
  );
}
