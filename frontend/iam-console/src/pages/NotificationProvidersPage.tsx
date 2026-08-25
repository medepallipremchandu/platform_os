import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { extractErrorMessage } from "../api/client";
import {
  archiveProviderConfig,
  createProviderConfig,
  getResolvedProviders,
  listEmailLogs,
  listProviderCatalog,
  listProviderConfigs,
  testProviderConfig,
  updateProviderConfig,
} from "../api/notifications";
import { useAuth } from "../components/auth/AuthContext";
import Badge, { type BadgeTone } from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import PageHeader from "../components/ui/PageHeader";
import StatCard from "../components/ui/StatCard";
import Table, { type Column } from "../components/ui/Table";
import { KeyIcon, PlusIcon, RefreshIcon, SparkleIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { PERMISSIONS, hasPermission, isSuperAdmin } from "../lib/permissions";
import type {
  EmailLogEntry,
  NotificationProviderConfig,
  ProviderKind,
  ProviderSpec,
  ResolvedProviders,
} from "../types";

type Editor = { mode: "create"; kind: ProviderKind } | { mode: "edit"; config: NotificationProviderConfig } | null;

const KIND_COPY: Record<ProviderKind, { title: string; blurb: string; fallback: string }> = {
  email: {
    title: "Email provider",
    blurb:
      "How this organization's invitations, password resets and other transactional mail physically leave the platform.",
    fallback: "Using the platform default. Add a provider to send through your own relay or API instead.",
  },
  queue: {
    title: "Queue provider",
    blurb:
      "Which message broker this organization's notifications are dispatched onto before delivery. Bring your own Redis, RabbitMQ, SQS or Postgres.",
    fallback: "Using the platform broker. Add a provider to route this organization's notifications through your own.",
  },
};

const STATUS_TONE: Record<string, BadgeTone> = {
  sent: "success",
  queued_to_org_queue: "info",
  logged_no_smtp_configured: "warning",
  failed: "danger",
};

/** Per-organization notification providers - the tenant-configurable half of the notification
 * pipeline, served by notification-service rather than iam-service.
 *
 * The forms here are rendered entirely from the provider catalog the backend publishes
 * (`/providers/catalog`), never from a hardcoded field list per vendor. That is deliberate: a
 * provider added on the backend shows up here, with the right inputs and the right secret
 * masking, without this file changing.
 */
export default function NotificationProvidersPage() {
  const { claims } = useAuth();
  const orgId = claims?.org_id;
  const canManage = hasPermission(PERMISSIONS.NOTIFICATION_PROVIDERS_MANAGE) || isSuperAdmin();

  const [catalog, setCatalog] = useState<ProviderSpec[]>([]);
  const [configs, setConfigs] = useState<NotificationProviderConfig[] | null>(null);
  const [resolved, setResolved] = useState<ResolvedProviders | null>(null);
  const [logs, setLogs] = useState<EmailLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [editor, setEditor] = useState<Editor>(null);
  const [providerKey, setProviderKey] = useState("");
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [enableNow, setEnableNow] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [archiving, setArchiving] = useState<NotificationProviderConfig | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    listProviderConfigs(orgId)
      .then(setConfigs)
      .catch((err) => setError(extractErrorMessage(err)));
    getResolvedProviders(orgId)
      .then(setResolved)
      .catch(() => setResolved(null));
    if (hasPermission(PERMISSIONS.NOTIFICATION_LOGS_READ) || canManage) {
      listEmailLogs(orgId, 25)
        .then((page) => setLogs(page.items))
        .catch(() => setLogs([]));
    }
  }, [orgId, canManage]);

  useEffect(() => {
    listProviderCatalog()
      .then(setCatalog)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  useEffect(load, [load]);

  const specsByKind = useMemo(() => {
    const grouped: Record<ProviderKind, ProviderSpec[]> = { email: [], queue: [] };
    for (const spec of catalog) grouped[spec.kind]?.push(spec);
    return grouped;
  }, [catalog]);

  const activeSpec = useMemo(() => {
    if (!editor) return null;
    const kind = editor.mode === "create" ? editor.kind : editor.config.kind;
    const key = editor.mode === "create" ? providerKey : editor.config.provider;
    return catalog.find((spec) => spec.kind === kind && spec.key === key) ?? null;
  }, [editor, providerKey, catalog]);

  function openCreate(kind: ProviderKind) {
    const first = specsByKind[kind][0];
    setProviderKey(first?.key ?? "");
    setName("");
    setValues(defaultsFor(first));
    setEnableNow(true);
    setSaveError(null);
    setEditor({ mode: "create", kind });
  }

  function openEdit(config: NotificationProviderConfig) {
    setProviderKey(config.provider);
    setName(config.name);
    setValues({ ...config.config });
    setEnableNow(config.is_enabled);
    setSaveError(null);
    setEditor({ mode: "edit", config });
  }

  function onProviderChange(kind: ProviderKind, key: string) {
    setProviderKey(key);
    setValues(defaultsFor(catalog.find((spec) => spec.kind === kind && spec.key === key)));
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!orgId || !editor) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editor.mode === "create") {
        await createProviderConfig(orgId, {
          kind: editor.kind,
          provider: providerKey,
          name,
          // Blank secret fields are dropped rather than sent: on an edit an empty box means
          // "keep the stored secret", and on a create it means the optional field was skipped.
          config: stripBlanks(values),
          is_enabled: enableNow,
        });
      } else {
        await updateProviderConfig(orgId, editor.config.id, {
          name,
          config: stripBlanks(values),
          is_enabled: enableNow,
        });
      }
      setEditor(null);
      load();
    } catch (err) {
      setSaveError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function runTest(config: NotificationProviderConfig) {
    if (!orgId) return;
    setTesting(config.id);
    setTestResult(null);
    try {
      setTestResult(await testProviderConfig(orgId, config.id));
    } catch (err) {
      setTestResult({ ok: false, message: extractErrorMessage(err) });
    } finally {
      setTesting(null);
      load();
    }
  }

  async function toggleEnabled(config: NotificationProviderConfig) {
    if (!orgId) return;
    try {
      await updateProviderConfig(orgId, config.id, { is_enabled: !config.is_enabled });
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  async function confirmArchive() {
    if (!orgId || !archiving) return;
    setArchiveLoading(true);
    try {
      await archiveProviderConfig(orgId, archiving.id);
      setArchiving(null);
      load();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setArchiveLoading(false);
    }
  }

  // A null org_id never reaches here - RequireOrganization guards the route - but `load`
  // still checks, since it also runs from callbacks.

  return (
    <div className="page">
      <PageHeader
        eyebrow="Notifications"
        title="Notification providers"
        subtitle="Bring your own mail relay and your own message broker. Anything you don't configure falls back to the platform default, so this is entirely optional."
        actions={
          <Button variant="secondary" icon={<RefreshIcon width={15} height={15} />} onClick={load}>
            Refresh
          </Button>
        }
      />

      {error && <p className="error-text">{error}</p>}

      {resolved && (
        <Card title="In effect right now">
          <div className="stat-grid">
            <StatCard
              icon={<SparkleIcon />}
              label="Email provider"
              value={providerLabel(catalog, resolved.email_provider)}
              hint={resolved.email_scope === "organization" ? "Yours" : "Platform default"}
              tone={resolved.email_scope === "organization" ? "success" : "brand"}
            />
            <StatCard
              icon={<KeyIcon />}
              label="Queue provider"
              value={providerLabel(catalog, resolved.queue_provider)}
              hint={resolved.queue_scope === "organization" ? "Yours" : "Platform default"}
              tone={resolved.queue_scope === "organization" ? "success" : "brand"}
            />
          </div>
        </Card>
      )}

      {(["email", "queue"] as ProviderKind[]).map((kind) => {
        const rows = (configs || []).filter((config) => config.kind === kind);
        return (
          <Card
            key={kind}
            title={KIND_COPY[kind].title}
            actions={
              canManage && (
                <Button size="sm" icon={<PlusIcon width={14} height={14} />} onClick={() => openCreate(kind)}>
                  Add
                </Button>
              )
            }
          >
            <p className="hint-text">{KIND_COPY[kind].blurb}</p>
            {configs === null ? null : rows.length === 0 ? (
              <EmptyState
                icon={<SparkleIcon width={26} height={26} />}
                title={`No ${kind} provider configured`}
                description={KIND_COPY[kind].fallback}
                action={canManage ? <Button onClick={() => openCreate(kind)}>Add {kind} provider</Button> : undefined}
              />
            ) : (
              <Table
                columns={configColumns(catalog, canManage, {
                  onEdit: openEdit,
                  onTest: runTest,
                  onToggle: toggleEnabled,
                  onArchive: setArchiving,
                  testingId: testing,
                })}
                rows={rows}
                getRowKey={(config) => config.id}
              />
            )}
          </Card>
        );
      })}

      <Card title="Recent deliveries">
        <p className="hint-text">
          One row per email this organization sent. "Logged, not sent" means no email provider was configured
          anywhere, so the message - link included - went to the service log instead.
        </p>
        {logs.length === 0 ? (
          <EmptyState icon={<SparkleIcon width={26} height={26} />} title="Nothing sent yet" />
        ) : (
          <Table
            columns={[
              { key: "created_at", header: "When", render: (row: EmailLogEntry) => formatDateTime(row.created_at) },
              { key: "to_email", header: "To", render: (row: EmailLogEntry) => row.to_email },
              { key: "template", header: "Template", render: (row: EmailLogEntry) => <code>{row.template}</code> },
              {
                key: "status",
                header: "Status",
                render: (row: EmailLogEntry) => (
                  <Badge tone={STATUS_TONE[row.status] ?? "neutral"}>{statusLabel(row.status)}</Badge>
                ),
              },
              {
                key: "provider",
                header: "Via",
                render: (row: EmailLogEntry) =>
                  row.provider ? (
                    <span title={row.error_message ?? undefined}>
                      {row.provider}
                      {row.provider_scope === "platform" ? " (platform)" : ""}
                    </span>
                  ) : (
                    "-"
                  ),
              },
            ]}
            rows={logs}
            getRowKey={(row) => row.id}
          />
        )}
      </Card>

      {editor && (
        <Modal
          title={
            editor.mode === "create"
              ? `Add ${editor.kind} provider`
              : `Edit ${editor.config.name}`
          }
          onClose={() => setEditor(null)}
        >
          <form className="form" onSubmit={handleSave}>
            {saveError && <p className="error-text">{saveError}</p>}

            {editor.mode === "create" && (
              <label>
                Provider
                <select value={providerKey} onChange={(e) => onProviderChange(editor.kind, e.target.value)}>
                  {specsByKind[editor.kind].map((spec) => (
                    <option key={spec.key} value={spec.key}>
                      {spec.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {activeSpec && <p className="hint-text">{activeSpec.description}</p>}

            <label>
              Name
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Production relay"
              />
            </label>

            {activeSpec?.fields.map((field) => {
              const stored =
                editor.mode === "edit" && field.secret && editor.config.secrets_set.includes(field.name);
              if (field.type === "bool") {
                return (
                  <label key={field.name} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={Boolean(values[field.name])}
                      onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.checked }))}
                    />
                    {field.label}
                    {field.help && <span className="hint-text"> {field.help}</span>}
                  </label>
                );
              }
              return (
                <label key={field.name}>
                  {field.label}
                  {field.secret && " (write-only)"}
                  <input
                    type={field.secret ? "password" : field.type === "int" ? "number" : "text"}
                    value={String(values[field.name] ?? "")}
                    onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                    // A secret already on file may be left blank to keep it - so it is only
                    // "required" when there is nothing stored to fall back on.
                    required={field.required && !stored}
                    placeholder={stored ? "Stored - leave blank to keep" : field.placeholder ?? undefined}
                  />
                  {field.help && <span className="hint-text">{field.help}</span>}
                </label>
              );
            })}

            <label className="checkbox-label">
              <input type="checkbox" checked={enableNow} onChange={(e) => setEnableNow(e.target.checked)} />
              Enable this provider
              <span className="hint-text"> Enabling it disables any other {activeSpec?.kind} provider.</span>
            </label>

            <div className="form__actions">
              <Button type="button" variant="secondary" onClick={() => setEditor(null)} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {editor.mode === "create" ? "Add provider" : "Save changes"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {testResult && (
        <Modal title={testResult.ok ? "Connection succeeded" : "Connection failed"} onClose={() => setTestResult(null)}>
          <p className={testResult.ok ? undefined : "error-text"}>{testResult.message}</p>
          <div className="form__actions">
            <Button onClick={() => setTestResult(null)}>Close</Button>
          </div>
        </Modal>
      )}

      {archiving && (
        <ConfirmDialog
          title="Remove provider"
          message={`Remove "${archiving.name}"? It is archived rather than deleted, and disabled immediately - this organization falls back to the platform default unless another provider of the same kind is enabled.`}
          confirmLabel="Remove"
          loading={archiveLoading}
          onConfirm={confirmArchive}
          onCancel={() => setArchiving(null)}
        />
      )}
    </div>
  );
}

function statusLabel(status: string): string {
  if (status === "logged_no_smtp_configured") return "Logged, not sent";
  if (status === "queued_to_org_queue") return "Queued to your broker";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function defaultsFor(spec: ProviderSpec | undefined): Record<string, unknown> {
  if (!spec) return {};
  return Object.fromEntries(
    spec.fields.filter((field) => field.default !== null && field.default !== undefined).map((f) => [f.name, f.default]),
  );
}

/** Blank strings are removed rather than sent as "". On an edit, an omitted secret means "keep
 * the stored one" server-side, and sending "" would be indistinguishable from clearing it. */
function stripBlanks(values: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== "" && value !== undefined));
}

function providerLabel(catalog: ProviderSpec[], key: string): string {
  if (key === "platform-default") return "Platform broker";
  return catalog.find((spec) => spec.key === key)?.label ?? key;
}

function configColumns(
  catalog: ProviderSpec[],
  canManage: boolean,
  handlers: {
    onEdit: (config: NotificationProviderConfig) => void;
    onTest: (config: NotificationProviderConfig) => void;
    onToggle: (config: NotificationProviderConfig) => void;
    onArchive: (config: NotificationProviderConfig) => void;
    testingId: string | null;
  },
): Column<NotificationProviderConfig>[] {
  return [
    {
      key: "name",
      header: "Name",
      render: (config) => (
        <>
          <strong>{config.name}</strong>
          <div className="hint-text">{catalog.find((s) => s.key === config.provider)?.label ?? config.provider}</div>
        </>
      ),
    },
    {
      key: "enabled",
      header: "Status",
      render: (config) => (
        <Badge tone={config.is_enabled ? "success" : "neutral"}>{config.is_enabled ? "Enabled" : "Disabled"}</Badge>
      ),
    },
    {
      key: "test",
      header: "Last test",
      render: (config) =>
        config.last_test_at ? (
          <span title={config.last_test_message ?? undefined}>
            <Badge tone={config.last_test_ok ? "success" : "danger"}>{config.last_test_ok ? "Passed" : "Failed"}</Badge>{" "}
            <span className="hint-text">{formatDateTime(config.last_test_at)}</span>
          </span>
        ) : (
          <span className="hint-text">Never tested</span>
        ),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (config) =>
        canManage ? (
          <div className="data-table__actions">
            <Button
              variant="secondary"
              size="sm"
              loading={handlers.testingId === config.id}
              onClick={() => handlers.onTest(config)}
            >
              Test
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handlers.onEdit(config)}>
              Edit
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handlers.onToggle(config)}>
              {config.is_enabled ? "Disable" : "Enable"}
            </Button>
            <Button variant="danger" size="sm" onClick={() => handlers.onArchive(config)}>
              Remove
            </Button>
          </div>
        ) : null,
    },
  ];
}
