import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { listOrgUsers } from "../api/iam";
import { createCallAgentConfig, getCallAgentConfig, listProviders, updateCallAgentConfig } from "../api/voiceAgent";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";
import SearchableSelect from "../components/ui/SearchableSelect";
import { SkeletonCard } from "../components/ui/Skeleton";
import VisibilityPicker from "../components/ui/VisibilityPicker";
import { LockIcon, PlusIcon, TrashIcon } from "../components/ui/icons";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { RETRYABLE_CALL_STATUSES } from "../types";
import type { CallAgentField, CallAgentFieldType, OrgUser, TelephonyProviderConfig, Visibility } from "../types";

const FIELD_TYPES: CallAgentFieldType[] = ["string", "number", "boolean", "date"];

export default function CallAgentFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const canWrite = hasPermission(PERMISSIONS.CALLAGENTS_WRITE);

  const [providers, setProviders] = useState<TelephonyProviderConfig[]>([]);
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [persona, setPersona] = useState("");
  const [objective, setObjective] = useState("");
  const [consentLine, setConsentLine] = useState("");
  const [closingLine, setClosingLine] = useState("");
  const [fields, setFields] = useState<CallAgentField[]>([]);
  const [maxDuration, setMaxDuration] = useState(10);
  const [retryMaxAttempts, setRetryMaxAttempts] = useState(3);
  const [retryIntervalMinutes, setRetryIntervalMinutes] = useState(60);
  const [retryOnStatuses, setRetryOnStatuses] = useState<string[]>(["NO_ANSWER", "BUSY"]);
  const [providerId, setProviderId] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<Visibility>("organization");
  const [grantUserIds, setGrantUserIds] = useState<string[]>([]);

  useEffect(() => {
    listProviders()
      .then(setProviders)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  useEffect(() => {
    if (!isEdit || !id) return;
    getCallAgentConfig(id)
      .then((c) => {
        setName(c.name);
        setDescription(c.description || "");
        setPersona(c.persona);
        setObjective(c.objective);
        setConsentLine(c.consent_line);
        setClosingLine(c.closing_line);
        setFields(c.fields);
        setMaxDuration(c.max_conversation_duration_minutes);
        setRetryMaxAttempts(c.retry_max_attempts);
        setRetryIntervalMinutes(c.retry_interval_minutes);
        setRetryOnStatuses(c.retry_on_statuses);
        setProviderId(c.telephony_provider_config_id);
        setVisibility(c.visibility);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  useEffect(() => {
    if (visibility !== "restricted") return;
    listOrgUsers()
      .then(setUsers)
      .catch((err) => setUsersError(extractErrorMessage(err)));
  }, [visibility]);

  function addField() {
    setFields((f) => [...f, { name: "", type: "string", description: "" }]);
  }

  function updateField(idx: number, patch: Partial<CallAgentField>) {
    setFields((f) => f.map((field, i) => (i === idx ? { ...field, ...patch } : field)));
  }

  function removeField(idx: number) {
    setFields((f) => f.filter((_, i) => i !== idx));
  }

  function toggleRetryStatus(status: string) {
    setRetryOnStatuses((s) => (s.includes(status) ? s.filter((x) => x !== status) : [...s, status]));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!providerId) return;
    setSaving(true);
    setError(null);
    const payload = {
      name,
      description: description || undefined,
      persona,
      objective,
      consent_line: consentLine,
      closing_line: closingLine,
      fields,
      max_conversation_duration_minutes: maxDuration,
      retry_max_attempts: retryMaxAttempts,
      retry_interval_minutes: retryIntervalMinutes,
      retry_on_statuses: retryOnStatuses,
      telephony_provider_config_id: providerId,
      visibility,
      grant_user_ids: visibility === "restricted" ? grantUserIds : undefined,
    };
    try {
      if (isEdit && id) {
        await updateCallAgentConfig(id, payload);
      } else {
        await createCallAgentConfig(payload);
      }
      navigate("/call-agents");
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!canWrite) {
    return (
      <div className="page">
        <PageHeader title={isEdit ? "Edit call agent" : "New call agent"} />
        <Card>
          <p className="hint-text">
            <LockIcon width={14} height={14} /> Your account doesn't have permission to manage call agent configs
            (talentos.voiceagent.callagents.write).
          </p>
        </Card>
      </div>
    );
  }

  if (loading) return <SkeletonCard />;

  return (
    <div className="page">
      <PageHeader
        title={isEdit ? "Edit call agent" : "Create call agent"}
        subtitle="The reusable script + retry policy + provider bundle a call is placed through."
      />
      <Card>
        <form className="form" onSubmit={handleSubmit}>
          {error && <p className="error-text">{error}</p>}

          <div className="form__row">
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label>
              Description
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
          </div>

          <label>
            Provider
            <SearchableSelect
              options={providers
                .filter((p) => !p.revoked_at)
                .map((p) => ({ value: p.id, label: `${p.name} (${p.phone_number})`, description: p.provider }))}
              value={providerId}
              onChange={setProviderId}
              placeholder="Search providers..."
            />
          </label>
          {providers.length === 0 && (
            <p className="hint-text">No providers registered yet - register one on the Providers page first.</p>
          )}

          <div className="form__section-title">Conversation script</div>
          <label>
            Persona
            <textarea
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              rows={3}
              placeholder="e.g. A friendly, professional scheduling assistant named Ava."
              required
            />
          </label>
          <label>
            Objective
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              rows={3}
              placeholder="What this call is trying to accomplish."
              required
            />
          </label>
          <div className="form__row">
            <label>
              Consent line
              <textarea
                value={consentLine}
                onChange={(e) => setConsentLine(e.target.value)}
                rows={2}
                placeholder="e.g. This call may be recorded for quality purposes - is that okay?"
                required
              />
            </label>
            <label>
              Closing line
              <textarea
                value={closingLine}
                onChange={(e) => setClosingLine(e.target.value)}
                rows={2}
                placeholder="e.g. Thanks for your time, have a great day."
                required
              />
            </label>
          </div>

          <div className="form__section-title">Fields to extract</div>
          <div className="repeatable-list">
            {fields.length === 0 && (
              <p className="repeatable-list__empty">
                No fields yet - add one below (e.g. "interested", boolean, "Whether the callee wants to proceed").
              </p>
            )}
            {fields.map((field, idx) => (
              <div className="repeatable-list__row" key={idx}>
                <input
                  placeholder="Field name"
                  value={field.name}
                  onChange={(e) => updateField(idx, { name: e.target.value })}
                  required
                />
                <select value={field.type} onChange={(e) => updateField(idx, { type: e.target.value as CallAgentFieldType })}>
                  {FIELD_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="Description"
                  value={field.description}
                  onChange={(e) => updateField(idx, { description: e.target.value })}
                  required
                />
                <button type="button" className="repeatable-list__remove" onClick={() => removeField(idx)} aria-label="Remove field">
                  <TrashIcon width={16} height={16} />
                </button>
              </div>
            ))}
          </div>
          <Button type="button" variant="secondary" size="sm" icon={<PlusIcon width={14} height={14} />} onClick={addField}>
            Add field
          </Button>

          <div className="form__section-title">Limits &amp; retry policy</div>
          <div className="form__row">
            <label>
              Max conversation duration (minutes)
              <input
                type="number"
                min={1}
                max={120}
                value={maxDuration}
                onChange={(e) => setMaxDuration(Number(e.target.value))}
              />
            </label>
            <label>
              Retry max attempts
              <input
                type="number"
                min={0}
                max={10}
                value={retryMaxAttempts}
                onChange={(e) => setRetryMaxAttempts(Number(e.target.value))}
              />
            </label>
            <label>
              Retry interval (minutes)
              <input
                type="number"
                min={1}
                max={1440}
                value={retryIntervalMinutes}
                onChange={(e) => setRetryIntervalMinutes(Number(e.target.value))}
              />
            </label>
          </div>
          <div className="form__field">
            <span className="form__field-label">Retry on these statuses</span>
            <div className="checklist">
              {RETRYABLE_CALL_STATUSES.map((status) => (
                <label className="checklist__item" key={status}>
                  <input type="checkbox" checked={retryOnStatuses.includes(status)} onChange={() => toggleRetryStatus(status)} />
                  {status}
                </label>
              ))}
            </div>
          </div>

          <hr className="form__divider" />

          <VisibilityPicker
            visibility={visibility}
            onVisibilityChange={setVisibility}
            grantUserIds={grantUserIds}
            onGrantUserIdsChange={setGrantUserIds}
            users={users}
            usersError={usersError}
          />
          {isEdit && visibility === "restricted" && (
            <p className="hint-text">
              The current grant list isn't returned by the read API - re-selecting people here replaces the full grant list on save.
            </p>
          )}

          <div className="form__actions">
            <Button type="button" variant="secondary" onClick={() => navigate("/call-agents")} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" loading={saving} disabled={!providerId}>
              {isEdit ? "Save changes" : "Create call agent"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
