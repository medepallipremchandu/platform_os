import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { listOrgUsers, listRoleDefinitions, listServicePrincipals } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";
import StatCard from "../components/ui/StatCard";
import { HistoryIcon, KeyIcon, ShieldIcon, UsersIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import type { OrgUser, RoleDefinition, ServicePrincipal } from "../types";

export default function DashboardPage() {
  const { claims, organizations } = useAuth();
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [roles, setRoles] = useState<RoleDefinition[] | null>(null);
  const [servicePrincipals, setServicePrincipals] = useState<ServicePrincipal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="page">
      <PageHeader
        eyebrow="Overview"
        title={currentOrg?.name || "Your organization"}
        subtitle="Identity and access at a glance: who has access, what roles exist, and what's connected."
      />

      {error && <p className="error-text">{error}</p>}

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
    </div>
  );
}
