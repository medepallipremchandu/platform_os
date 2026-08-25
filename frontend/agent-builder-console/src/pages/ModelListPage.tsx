import { useEffect, useState } from "react";
import { createModel, listModels } from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { PlusIcon, SparkleIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import type { Model, ModelProvider } from "../types";

const columns: Column<Model>[] = [
  { key: "code", header: "Code", render: (m) => <Badge tone="neutral">{m.model_code}</Badge> },
  { key: "name", header: "Name", render: (m) => m.name },
  { key: "provider", header: "Provider", render: (m) => <Badge tone="brand">{m.provider}</Badge> },
  { key: "model_id", header: "Model / deployment", render: (m) => <code>{m.model_id}</code> },
  { key: "created_by", header: "Registered by", render: (m) => m.created_by || "-" },
  { key: "created_at", header: "Registered on", render: (m) => formatDateTime(m.created_at) },
];

export default function ModelListPage() {
  const [models, setModels] = useState<Model[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [provider, setProvider] = useState<ModelProvider>("claude");
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [apiVersion, setApiVersion] = useState("");

  function refresh() {
    listModels()
      .then(setModels)
      .catch((err) => setError(extractErrorMessage(err)));
  }

  useEffect(refresh, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createModel({
        name,
        provider,
        model_id: modelId,
        api_key: apiKey,
        endpoint: provider === "azure_openai" ? endpoint : undefined,
        api_version: provider === "azure_openai" ? apiVersion : undefined,
      });
      setName("");
      setModelId("");
      setApiKey("");
      setEndpoint("");
      setApiVersion("");
      setShowForm(false);
      refresh();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Models"
        subtitle="The catalog of ready-to-use model deployments agents pick from. Credentials are encrypted at rest."
        actions={
          <Button icon={<PlusIcon width={16} height={16} />} onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "Register model"}
          </Button>
        }
      />

      {showForm && (
        <Card title="Register a model">
          <form onSubmit={handleSubmit} className="jd-form">
            <label>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude Sonnet 5" required />
            </label>
            <label>
              Provider
              <select value={provider} onChange={(e) => setProvider(e.target.value as ModelProvider)}>
                <option value="claude">Claude (Anthropic)</option>
                <option value="azure_openai">Azure OpenAI</option>
              </select>
            </label>
            <label>
              {provider === "claude" ? "Model name" : "Deployment name"}
              <input value={modelId} onChange={(e) => setModelId(e.target.value)} required />
            </label>
            <label>
              API key
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
            </label>
            {provider === "azure_openai" && (
              <>
                <label>
                  Endpoint
                  <input
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    placeholder="https://your-resource.openai.azure.com"
                    required
                  />
                </label>
                <label>
                  API version
                  <input value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} placeholder="2025-04-01-preview" required />
                </label>
              </>
            )}
            <Button type="submit" icon={<SparkleIcon width={16} height={16} />} loading={saving}>
              Register model
            </Button>
          </form>
          {error && <p className="error-text">{error}</p>}
        </Card>
      )}

      <Card>
        {!showForm && error && <p className="error-text">{error}</p>}
        {models === null ? (
          <SkeletonRows rows={3} columns={6} />
        ) : models.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No models registered yet"
            description="Register a Claude or Azure OpenAI deployment so agents have something to run on."
          />
        ) : (
          <Table columns={columns} rows={models} getRowKey={(m) => m.id} />
        )}
      </Card>
    </div>
  );
}
