import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { createCall, listCallAgentConfigs, listProviders } from "../api/voiceAgent";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";
import SearchableSelect from "../components/ui/SearchableSelect";
import { PlusIcon, TrashIcon } from "../components/ui/icons";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import type { CallAgentConfig, CallAgentField, CallAgentFieldType, TelephonyProviderConfig } from "../types";

type Mode = "agent" | "inline";

const FIELD_TYPES: CallAgentFieldType[] = ["string", "number", "boolean", "date"];

export default function PlaceCallPage() {
  const navigate = useNavigate();
  const canWrite = hasPermission(PERMISSIONS.CALLS_WRITE);

  const [mode, setMode] = useState<Mode>("agent");
  const [configs, setConfigs] = useState<CallAgentConfig[]>([]);
  const [providers, setProviders] = useState<TelephonyProviderConfig[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [toNumber, setToNumber] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");

  // --- Mode: saved call agent ---
  const [callAgentConfigId, setCallAgentConfigId] = useState<string | null>(null);

  // --- Mode: inline (ad-hoc) ---
  const [providerId, setProviderId] = useState<string | null>(null);
  const [persona, setPersona] = useState("");
  const [objective, setObjective] = useState("");
  const [consentLine, setConsentLine] = useState("");
  const [closingLine, setClosingLine] = useState("");
  const [fields, setFields] = useState<CallAgentField[]>([]);
  const [maxDuration, setMaxDuration] = useState(10);

  useEffect(() => {
    Promise.all([listCallAgentConfigs().catch(() => []), listProviders().catch(() => [])]).then(([c, p]) => {
      setConfigs(c.filter((cfg) => !cfg.deactivated_at));
      setProviders(p.filter((prov) => !prov.revoked_at));
    });
  }, []);

  function addField() {
    setFields((f) => [...f, { name: "", type: "string", description: "" }]);
  }
  function updateField(idx: number, patch: Partial<CallAgentField>) {
    setFields((f) => f.map((field, i) => (i === idx ? { ...field, ...patch } : field)));
  }
  function removeField(idx: number) {
    setFields((f) => f.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const call =
        mode === "agent"
          ? await createCall({
              call_agent_config_id: callAgentConfigId!,
              to_number: toNumber,
              webhook_url: webhookUrl || undefined,
            })
          : await createCall({
              to_number: toNumber,
              telephony_provider_config_id: providerId!,
              call_script: { persona, objective, consent_line: consentLine, closing_line: closingLine, fields },
              max_conversation_duration_minutes: maxDuration,
              webhook_url: webhookUrl || undefined,
            });
      navigate(`/calls/${call.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const canSubmit =
    !!toNumber && (mode === "agent" ? !!callAgentConfigId : !!providerId && !!persona && !!objective && !!consentLine && !!closingLine);

  if (!canWrite) {
    return (
      <div className="page">
        <PageHeader title="Place a call" />
        <Card>
          <p className="error-text">Your account doesn't have permission to place calls (talentos.voiceagent.calls.write).</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader title="Place a call" subtitle="Pick a saved call agent, or build one inline for a one-off." />

      <Card>
        <form className="form" onSubmit={handleSubmit}>
          {error && <p className="error-text">{error}</p>}

          <div className="tabs">
            <button type="button" className={`tabs__tab ${mode === "agent" ? "tabs__tab--active" : ""}`} onClick={() => setMode("agent")}>
              Use a saved call agent
            </button>
            <button type="button" className={`tabs__tab ${mode === "inline" ? "tabs__tab--active" : ""}`} onClick={() => setMode("inline")}>
              Build one-off
            </button>
          </div>

          <div className="tabs__panel">
            {mode === "agent" ? (
              <div className="form" style={{ gap: "var(--space-4)" }}>
                <label>
                  Call agent
                  <SearchableSelect
                    options={configs.map((c) => ({ value: c.id, label: c.name, description: c.description || undefined }))}
                    value={callAgentConfigId}
                    onChange={setCallAgentConfigId}
                    placeholder="Search call agents..."
                  />
                </label>
                {configs.length === 0 && (
                  <p className="hint-text">No active call agents yet - create one on the Call Agents page, or build one below.</p>
                )}
              </div>
            ) : (
              <div className="form" style={{ gap: "var(--space-4)" }}>
                <label>
                  Provider
                  <SearchableSelect
                    options={providers.map((p) => ({ value: p.id, label: `${p.name} (${p.phone_number})`, description: p.provider }))}
                    value={providerId}
                    onChange={setProviderId}
                    placeholder="Search providers..."
                  />
                </label>
                <label>
                  Persona
                  <textarea value={persona} onChange={(e) => setPersona(e.target.value)} rows={2} required />
                </label>
                <label>
                  Objective
                  <textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={2} required />
                </label>
                <div className="form__row">
                  <label>
                    Consent line
                    <textarea value={consentLine} onChange={(e) => setConsentLine(e.target.value)} rows={2} required />
                  </label>
                  <label>
                    Closing line
                    <textarea value={closingLine} onChange={(e) => setClosingLine(e.target.value)} rows={2} required />
                  </label>
                </div>
                <label>
                  Max conversation duration (minutes)
                  <input type="number" min={1} max={120} value={maxDuration} onChange={(e) => setMaxDuration(Number(e.target.value))} />
                </label>

                <div className="form__section-title">Fields to extract</div>
                <div className="repeatable-list">
                  {fields.map((field, idx) => (
                    <div className="repeatable-list__row" key={idx}>
                      <input placeholder="Field name" value={field.name} onChange={(e) => updateField(idx, { name: e.target.value })} required />
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
              </div>
            )}
          </div>

          <hr className="form__divider" />

          <div className="form__row">
            <label>
              Destination number
              <input value={toNumber} onChange={(e) => setToNumber(e.target.value)} placeholder="+15551234567" required />
            </label>
            <label>
              Webhook URL (optional)
              <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="https://..." />
            </label>
          </div>

          <div className="form__actions">
            <Button type="button" variant="secondary" onClick={() => navigate("/calls")} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" loading={saving} disabled={!canSubmit}>
              Place call
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
