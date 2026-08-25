import { type FormEvent, useEffect, useState } from "react";
import { extractErrorMessage } from "../api/client";
import { createServicePrincipal, listServicePrincipals, revokeServicePrincipal, rotateServicePrincipalSecret } from "../api/iam";
import { useAuth } from "../components/auth/AuthContext";
import SecretRevealModal from "../components/SecretRevealModal";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { KeyIcon, PlusIcon, RefreshIcon, TrashIcon } from "../components/ui/icons";
import { PERMISSIONS, hasPermission } from "../lib/permissions";
import { toneForRevocation } from "../lib/tone";
import type { ServicePrincipal, ServicePrincipalWithSecret } from "../types";

export default function ServicePrincipalsPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canManage = hasPermission(PERMISSIONS.SERVICE_PRINCIPALS_MANAGE);

  const [principals, setPrincipals] = useState<ServicePrincipal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [bindResource, setBindResource] = useState(false);
  const [resourceType, setResourceType] = useState("agent");
  const [resourceId, setResourceId] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<ServicePrincipalWithSecret | null>(null);
  const [rotating, setRotating] = useState<ServicePrincipal | null>(null);
  const [rotateLoading, setRotateLoading] = useState(false);
  const [revoking, setRevoking] = useState<ServicePrincipal | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);

  function load() {
    if (!orgId) return;
    listServicePrincipals(orgId)
      .then(setPrincipals)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(load, [orgId]);

  function openCreate() {
    setName("");
    setBindResource(false);
    setResourceType("agent");
    setResourceId("");
    setSaveError(null);
    setShowCreate(true);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createServicePrincipal({
        name,
        organization_id: orgId,
        resource_type: bindResource ? resourceType : undefined,
        resource_id: bindResource ? resourceId : undefined,
      });
      setShowCreate(false);
      setRevealed(created);
      load();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function confirmRotate() {
    if (!rotating) return;
    setRotateLoading(true);
    try {
      const result = await rotateServicePrincipalSecret(rotating);
      setRotating(null);
      setRevealed(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRotateLoading(false);
    }
  }

  async function confirmRevoke() {
    if (!revoking) return;
    setRevokeLoading(true);
    try {
      await revokeServicePrincipal(revoking.id);
      setRevoking(null);
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRevokeLoading(false);
    }
  }

  const columns: Column<ServicePrincipal>[] = [
    { key: "name", header: "Name", render: (sp) => sp.name },
    { key: "client_id", header: "Client ID", render: (sp) => <code>{sp.client_id}</code> },
    {
      key: "binding",
      header: "Bound to",
      render: (sp) => (sp.resource_type ? `${sp.resource_type}: ${sp.resource_id}` : <span className="hint-text">Not bound</span>),
    },
    {
      key: "status",
      header: "Status",
      render: (sp) => <Badge tone={toneForRevocation(sp.revoked_at)}>{sp.revoked_at ? "Revoked" : "Active"}</Badge>,
    },
    ...(canManage
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            render: (sp: ServicePrincipal) => (
              <div className="data-table__actions">
                {!sp.revoked_at && (
                  <>
                    <Button variant="secondary" size="sm" icon={<RefreshIcon width={14} height={14} />} onClick={() => setRotating(sp)}>
                      Rotate
                    </Button>
                    <Button variant="danger" size="sm" icon={<TrashIcon width={14} height={14} />} onClick={() => setRevoking(sp)}>
                      Revoke
                    </Button>
                  </>
                )}
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Machine identities"
        title="Service principals"
        subtitle="Non-human credentials for service-to-service calls, optionally bound to one specific resource (e.g. an agent's invoke credential)."
        actions={
          canManage && (
            <Button icon={<PlusIcon width={16} height={16} />} onClick={openCreate}>
              New service principal
            </Button>
          )
        }
      />

      {error && <p className="error-text">{error}</p>}

      <Card>
        {principals === null ? (
          <SkeletonRows rows={5} columns={4} />
        ) : principals.length === 0 ? (
          <EmptyState
            icon={<KeyIcon width={26} height={26} />}
            title="No service principals yet"
            description="Create one for a backend service or a specific resource's invoke credential."
            action={canManage ? <Button onClick={openCreate}>New service principal</Button> : undefined}
          />
        ) : (
          <Table columns={columns} rows={principals} getRowKey={(sp) => sp.id} />
        )}
      </Card>

      {showCreate && (
        <Modal title="New service principal" onClose={() => setShowCreate(false)}>
          <form className="form" onSubmit={handleCreate}>
            {saveError && <p className="error-text">{saveError}</p>}
            <label>
              Name
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
            </label>
            <label style={{ flexDirection: "row", alignItems: "center", gap: "8px" }}>
              <input type="checkbox" checked={bindResource} onChange={(e) => setBindResource(e.target.checked)} />
              Bind to a specific resource (e.g. one agent's invoke credential)
            </label>
            {bindResource && (
              <div className="form__row">
                <label>
                  Resource type
                  <input type="text" value={resourceType} onChange={(e) => setResourceType(e.target.value)} placeholder="agent" required />
                </label>
                <label>
                  Resource ID
                  <input type="text" value={resourceId} onChange={(e) => setResourceId(e.target.value)} required />
                </label>
              </div>
            )}
            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setShowCreate(false)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                Create
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {revealed && (
        <SecretRevealModal
          title="Service principal created"
          clientId={revealed.client_id}
          clientSecret={revealed.client_secret}
          onAcknowledge={() => setRevealed(null)}
        />
      )}

      {rotating && (
        <ConfirmDialog
          title="Rotate secret"
          message={`Rotate the secret for "${rotating.name}"? The old secret's already-issued tokens keep working until they expire (up to 15 minutes), then it stops working entirely.`}
          confirmLabel="Rotate"
          danger={false}
          loading={rotateLoading}
          onConfirm={confirmRotate}
          onCancel={() => setRotating(null)}
        />
      )}

      {revoking && (
        <ConfirmDialog
          title="Revoke service principal"
          message={`Revoke "${revoking.name}"? Anything using this credential will immediately lose access.`}
          confirmLabel="Revoke"
          loading={revokeLoading}
          onConfirm={confirmRevoke}
          onCancel={() => setRevoking(null)}
        />
      )}
    </div>
  );
}
