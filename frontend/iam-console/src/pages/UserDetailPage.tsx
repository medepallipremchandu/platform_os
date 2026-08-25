import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { deleteRoleAssignment, listOrgUsers, listRoleAssignments } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { ArrowLeftIcon, LinkIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForScopeType, toneForUserStatus } from "../lib/tone";
import type { OrgUser, RoleAssignment } from "../types";

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canManageAssignments = hasPermission(PERMISSIONS.ROLE_ASSIGNMENTS_MANAGE);

  const [user, setUser] = useState<OrgUser | null | undefined>(undefined);
  const [assignments, setAssignments] = useState<RoleAssignment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<RoleAssignment | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);

  function load() {
    if (!orgId || !id) return;
    listOrgUsers(orgId)
      .then((users) => setUser(users.find((u) => u.user_id === id) ?? null))
      .catch((err) => setError(extractErrorMessage(err)));
    listRoleAssignments(orgId)
      .then((all) => setAssignments(all.filter((a) => a.principal_type === "user" && a.principal_id === id)))
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(load, [orgId, id]);

  async function confirmRevoke() {
    if (!revoking) return;
    setRevokeLoading(true);
    setRevokeError(null);
    try {
      await deleteRoleAssignment(revoking.id);
      setRevoking(null);
      load();
    } catch (err) {
      setRevokeError(extractErrorMessage(err));
    } finally {
      setRevokeLoading(false);
    }
  }

  const columns: Column<RoleAssignment>[] = [
    { key: "role", header: "Role", render: (a) => a.role_name },
    {
      key: "scope",
      header: "Scope",
      render: (a) => (
        <Badge tone={toneForScopeType(a.scope_type)}>
          {a.scope_type === "organization" ? "Organization" : a.scope_id.split(":").pop()}
        </Badge>
      ),
    },
    ...(canManageAssignments
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (a: RoleAssignment) => (
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
        eyebrow="Users"
        title={user?.display_name || user?.email || "User"}
        subtitle={user ? user.email : undefined}
        actions={
          <Link to="/users">
            <Button variant="secondary" icon={<ArrowLeftIcon width={16} height={16} />}>
              Back to users
            </Button>
          </Link>
        }
      />

      {error && <p className="error-text">{error}</p>}

      {user === undefined ? (
        <Card>
          <SkeletonRows rows={3} columns={2} />
        </Card>
      ) : user === null ? (
        <Card>
          <EmptyState title="User not found" description="This user may have been removed from the organization." />
        </Card>
      ) : (
        <>
          <Card title="Details">
            <p>
              Status: <Badge tone={toneForUserStatus(user.membership_status)}>{user.membership_status}</Badge>
            </p>
          </Card>

          <Card title="Role assignments">
            {assignments === null ? (
              <SkeletonRows rows={2} columns={2} />
            ) : assignments.length === 0 ? (
              <EmptyState
                icon={<LinkIcon width={26} height={26} />}
                title="No role assignments"
                description="This user has no roles assigned in this organization yet."
                action={
                  canManageAssignments ? (
                    <Button onClick={() => navigate(`/role-assignments?principal_id=${user.user_id}`)}>Assign a role</Button>
                  ) : undefined
                }
              />
            ) : (
              <Table columns={columns} rows={assignments} getRowKey={(a) => a.id} />
            )}
          </Card>
        </>
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke role assignment"
          message={`Remove the "${revoking.role_name}" role from this user?`}
          confirmLabel="Revoke"
          loading={revokeLoading}
          onConfirm={confirmRevoke}
          onCancel={() => {
            setRevoking(null);
            setRevokeError(null);
          }}
        />
      )}
      {revokeError && <p className="error-text">{revokeError}</p>}
    </div>
  );
}
