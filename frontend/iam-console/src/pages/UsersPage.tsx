import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { inviteUser, listOrgUsers, listRoleAssignments, updateUserStatus } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { PlusIcon, UsersIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForUserStatus } from "../lib/tone";
import type { OrgUser } from "../types";

export default function UsersPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canInvite = hasPermission(PERMISSIONS.USERS_INVITE);
  const canManage = hasPermission(PERMISSIONS.USERS_MANAGE);

  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [roleCounts, setRoleCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [pendingStatusChange, setPendingStatusChange] = useState<string | null>(null);

  function load() {
    if (!orgId) return;
    listOrgUsers(orgId)
      .then(setUsers)
      .catch((err) => setError(extractErrorMessage(err)));
    listRoleAssignments(orgId)
      .then((assignments) => {
        const counts: Record<string, number> = {};
        for (const a of assignments) {
          if (a.principal_type === "user") counts[a.principal_id] = (counts[a.principal_id] || 0) + 1;
        }
        setRoleCounts(counts);
      })
      .catch(() => undefined);
  }

  useEffect(load, [orgId]);

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setInviting(true);
    setInviteError(null);
    try {
      await inviteUser(orgId, { email: inviteEmail, display_name: inviteName });
      setShowInvite(false);
      setInviteEmail("");
      setInviteName("");
      load();
    } catch (err) {
      setInviteError(extractErrorMessage(err));
    } finally {
      setInviting(false);
    }
  }

  async function toggleStatus(user: OrgUser) {
    if (!orgId) return;
    const nextStatus = user.membership_status === "disabled" ? "active" : "disabled";
    setPendingStatusChange(user.user_id);
    try {
      await updateUserStatus(orgId, user.user_id, { status: nextStatus });
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setPendingStatusChange(null);
    }
  }

  const columns: Column<OrgUser>[] = [
    {
      key: "email",
      header: "Email",
      render: (user) => (
        <Link to={`/users/${user.user_id}`} className="link">
          {user.email}
        </Link>
      ),
    },
    { key: "name", header: "Display name", render: (user) => user.display_name || "-" },
    {
      key: "status",
      header: "Status",
      render: (user) => <Badge tone={toneForUserStatus(user.membership_status)}>{user.membership_status}</Badge>,
    },
    { key: "roles", header: "Role assignments", render: (user) => roleCounts[user.user_id] || 0, align: "right" },
    { key: "created_at", header: "Created", render: (user) => formatDateTime(user.created_at) },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (user: OrgUser) => (
              <div className="data-table__actions">
                <Button
                  variant={user.membership_status === "disabled" ? "secondary" : "danger"}
                  size="sm"
                  loading={pendingStatusChange === user.user_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleStatus(user);
                  }}
                >
                  {user.membership_status === "disabled" ? "Enable" : "Disable"}
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Identity"
        title="Users"
        subtitle="Members of this organization and the roles assigned to them."
        actions={
          canInvite && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={() => setShowInvite(true)}>
              Invite user
            </Button>
          )
        }
      />

      <Card>
        {error && <p className="error-text">{error}</p>}
        {users === null ? (
          <SkeletonRows rows={5} columns={5} />
        ) : users.length === 0 ? (
          <EmptyState
            icon={<UsersIcon width={26} height={26} />}
            title="No users yet"
            description="Invite someone to this organization to get started."
            action={canInvite ? <Button onClick={() => setShowInvite(true)}>Invite user</Button> : undefined}
          />
        ) : (
          <Table columns={columns} rows={users} getRowKey={(user) => user.id} />
        )}
      </Card>

      {showInvite && (
        <Modal title="Invite user" onClose={() => setShowInvite(false)}>
          <form className="form" onSubmit={handleInvite}>
            {inviteError && <p className="error-text">{inviteError}</p>}
            <label>
              Email
              <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required autoFocus />
            </label>
            <label>
              Display name
              <input type="text" value={inviteName} onChange={(e) => setInviteName(e.target.value)} required />
            </label>
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setShowInvite(false)} disabled={inviting}>
                Cancel
              </Button>
              <Button type="submit" loading={inviting}>
                Send invite
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
