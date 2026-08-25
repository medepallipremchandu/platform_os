import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { inviteUser, listOrgUsers, listRoleAssignments, updateOrgUser } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import FilterBar, { FilterBarField } from "../components/ui/FilterBar";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column, type SortDirection } from "../components/ui/Table";
import { EditIcon, PlusIcon, UsersIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForUserStatus } from "../lib/tone";
import type { OrgUser, UserStatus } from "../types";

type StatusFilter = "" | UserStatus;
type SortKey = "name" | "created_at";

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
  const [editing, setEditing] = useState<OrgUser | null>(null);
  const [editName, setEditName] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

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
      await updateOrgUser(orgId, user.user_id, { status: nextStatus });
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setPendingStatusChange(null);
    }
  }

  function openEdit(user: OrgUser) {
    setEditing(user);
    setEditName(user.display_name || "");
    setEditError(null);
  }

  async function handleEditSave(e: FormEvent) {
    e.preventDefault();
    if (!orgId || !editing) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await updateOrgUser(orgId, editing.user_id, { display_name: editName });
      setEditing(null);
      load();
    } catch (err) {
      setEditError(extractErrorMessage(err));
    } finally {
      setEditSaving(false);
    }
  }

  function toggleSort(key: string) {
    if (key !== "name" && key !== "created_at") return;
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  }

  // Client-side search/filter/sort over the already-fetched list - an organization's member
  // list is admin-configured (not application-scale data), so this doesn't need server-side
  // pagination. Revisit if a single org's membership ever grows into the thousands.
  const visibleUsers = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = (users || []).filter((u) => {
      if (statusFilter && u.membership_status !== statusFilter) return false;
      if (q && !u.email.toLowerCase().includes(q) && !(u.display_name || "").toLowerCase().includes(q)) return false;
      return true;
    });
    list = [...list].sort((a, b) => {
      const diff =
        sortKey === "name"
          ? (a.display_name || a.email).localeCompare(b.display_name || b.email)
          : new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sortDirection === "asc" ? diff : -diff;
    });
    return list;
  }, [users, query, statusFilter, sortKey, sortDirection]);

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
    { key: "name", header: "Display name", sortable: true, render: (user) => user.display_name || "-" },
    {
      key: "status",
      header: "Status",
      render: (user) => <Badge tone={toneForUserStatus(user.membership_status)}>{user.membership_status}</Badge>,
    },
    { key: "roles", header: "Role assignments", render: (user) => roleCounts[user.user_id] || 0, align: "right" },
    { key: "created_at", header: "Created", sortable: true, render: (user) => formatDateTime(user.created_at) },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (user: OrgUser) => (
              <div className="data-table__actions">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<EditIcon width={14} height={14} />}
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(user);
                  }}
                >
                  Edit
                </Button>
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
        <FilterBar>
          <FilterBarField label="Search" htmlFor="users-search">
            <SearchInput value={query} onChange={setQuery} placeholder="Search by name or email..." />
          </FilterBarField>
          <FilterBarField label="Status" htmlFor="users-status">
            <select id="users-status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="invited">Invited</option>
              <option value="disabled">Disabled</option>
            </select>
          </FilterBarField>
        </FilterBar>
      </Card>

      <Card>
        {error && <p className="error-text">{error}</p>}
        {users === null ? (
          <SkeletonRows rows={5} columns={5} />
        ) : visibleUsers.length === 0 ? (
          <EmptyState
            icon={<UsersIcon width={26} height={26} />}
            title={users.length === 0 ? "No users yet" : "No users match your filters"}
            description={users.length === 0 ? "Invite someone to this organization to get started." : undefined}
            action={users.length === 0 && canInvite ? <Button onClick={() => setShowInvite(true)}>Invite user</Button> : undefined}
          />
        ) : (
          <Table
            columns={columns}
            rows={visibleUsers}
            getRowKey={(user) => user.id}
            sortKey={sortKey}
            sortDirection={sortDirection}
            onSort={toggleSort}
          />
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

      {editing && (
        <Modal title={`Edit ${editing.email}`} onClose={() => setEditing(null)}>
          <form className="form" onSubmit={handleEditSave}>
            {editError && <p className="error-text">{editError}</p>}
            <label>
              Display name
              <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} required autoFocus />
            </label>
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)} disabled={editSaving}>
                Cancel
              </Button>
              <Button type="submit" loading={editSaving}>
                Save
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
