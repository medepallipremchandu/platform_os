import { type FormEvent, useEffect, useState } from "react";
import { extractErrorMessage } from "../api/client";
import { createRoleDefinition, deleteRoleDefinition, listPermissions, listRoleDefinitions, updateRoleDefinition } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import PermissionPicker from "../components/PermissionPicker";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonCard } from "../components/ui/Skeleton";
import { EditIcon, PlusIcon, ShieldIcon, TrashIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForRoleKind } from "../lib/tone";
import type { Permission, RoleDefinition } from "../types";

type EditorState = { mode: "create" } | { mode: "edit"; role: RoleDefinition } | null;

export default function RolesPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canManage = hasPermission(PERMISSIONS.ROLES_MANAGE);

  const [roles, setRoles] = useState<RoleDefinition[] | null>(null);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState>(null);
  const [name, setName] = useState("");
  const [permissionCodes, setPermissionCodes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<RoleDefinition | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  function load() {
    if (!orgId) return;
    listRoleDefinitions(orgId)
      .then(setRoles)
      .catch((err) => setError(extractErrorMessage(err)));
    listPermissions()
      .then(setCatalog)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(load, [orgId]);

  const catalogCodes = catalog.map((p) => p.code);
  const builtinRoles = (roles || []).filter((r) => r.is_builtin);
  const customRoles = (roles || []).filter((r) => !r.is_builtin);

  function openCreate() {
    setName("");
    setPermissionCodes([]);
    setSaveError(null);
    setEditor({ mode: "create" });
  }

  function openEdit(role: RoleDefinition) {
    setName(role.name);
    setPermissionCodes(role.permissions);
    setSaveError(null);
    setEditor({ mode: "edit", role });
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!orgId || !editor) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editor.mode === "create") {
        await createRoleDefinition({ name, organization_id: orgId, permission_codes: permissionCodes });
      } else {
        await updateRoleDefinition(editor.role.id, { name, permission_codes: permissionCodes });
      }
      setEditor(null);
      load();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteLoading(true);
    try {
      await deleteRoleDefinition(deleting.id);
      setDeleting(null);
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Access control"
        title="Roles"
        subtitle="Built-in roles ship with the platform and are read-only. Custom roles combine any subset of the permission catalog."
        actions={
          canManage && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={openCreate}>
              New role
            </Button>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card title="Built-in roles">
        {roles === null ? (
          <div className="role-grid">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : builtinRoles.length === 0 ? (
          <EmptyState icon={<ShieldIcon width={26} height={26} />} title="No built-in roles found" />
        ) : (
          <div className="role-grid">
            {builtinRoles.map((role) => (
              <RoleCard key={role.id} role={role} canManage={false} />
            ))}
          </div>
        )}
      </Card>

      <Card title="Custom roles">
        {roles === null ? null : customRoles.length === 0 ? (
          <EmptyState
            icon={<ShieldIcon width={26} height={26} />}
            title="No custom roles yet"
            description="Combine permissions from any service into a role scoped to this organization."
            action={canManage ? <Button onClick={openCreate}>New role</Button> : undefined}
          />
        ) : (
          <div className="role-grid">
            {customRoles.map((role) => (
              <RoleCard key={role.id} role={role} canManage={canManage} onEdit={openEdit} onDelete={setDeleting} />
            ))}
          </div>
        )}
      </Card>

      {editor && (
        <Modal title={editor.mode === "create" ? "New custom role" : `Edit ${editor.role.name}`} onClose={() => setEditor(null)}>
          <form className="form" onSubmit={handleSave}>
            {saveError && <p className="error-text">{saveError}</p>}
            <label>
              Role name
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </label>
            <label>
              Permissions
              <PermissionPicker catalog={catalogCodes} selected={permissionCodes} onChange={setPermissionCodes} />
            </label>
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setEditor(null)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {editor.mode === "create" ? "Create role" : "Save changes"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {deleting && (
        <ConfirmDialog
          title="Delete role"
          message={`Delete the "${deleting.name}" role? Any role assignments using it will need to be reassigned.`}
          confirmLabel="Delete"
          loading={deleteLoading}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

function RoleCard({
  role,
  canManage,
  onEdit,
  onDelete,
}: {
  role: RoleDefinition;
  canManage: boolean;
  onEdit?: (role: RoleDefinition) => void;
  onDelete?: (role: RoleDefinition) => void;
}) {
  return (
    <div className="role-card">
      <div className="role-card__header">
        <span className="role-card__name">{role.name}</span>
        <Badge tone={toneForRoleKind(role.is_builtin)}>{role.is_builtin ? "Built-in" : "Custom"}</Badge>
      </div>
      <span className="role-card__count">{role.permissions.length} permissions</span>
      {role.is_builtin ? (
        <span className="hint-text" title="Built-in roles ship with the platform and can't be edited or deleted.">
          Read-only
        </span>
      ) : (
        canManage && (
          <div className="role-card__actions">
            <Button variant="secondary" size="sm" icon={<EditIcon width={14} height={14} />} onClick={() => onEdit?.(role)}>
              Edit
            </Button>
            <Button variant="danger" size="sm" icon={<TrashIcon width={14} height={14} />} onClick={() => onDelete?.(role)}>
              Delete
            </Button>
          </div>
        )
      )}
    </div>
  );
}
