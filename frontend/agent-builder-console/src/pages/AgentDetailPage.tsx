import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getAgent,
  getAgentUsage,
  listAgentCredentials,
  publishAgent,
  regenerateAgentCredential,
} from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import { CheckCircleIcon, ClockIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import type { Agent, AgentCredential, AgentUsageEntry } from "../types";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [usage, setUsage] = useState<AgentUsageEntry[]>([]);
  const [credentials, setCredentials] = useState<AgentCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  function refresh() {
    if (!id) return;
    Promise.all([getAgent(id), getAgentUsage(id)])
      .then(([a, u]) => {
        setAgent(a);
        setUsage(u);
        // Credential listing requires manage_keys permission - a read-only viewer can still see
        // the agent itself, so don't let this fail the whole page.
        if (a.status === "published") {
          listAgentCredentials(id)
            .then(setCredentials)
            .catch(() => setCredentials([]));
        }
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [id]);

  async function handlePublish() {
    if (!id) return;
    setPublishing(true);
    setError(null);
    try {
      const result = await publishAgent(id);
      setAgent(result.agent);
      if (result.client_secret) setRevealedSecret(result.client_secret);
      listAgentCredentials(id)
        .then(setCredentials)
        .catch(() => setCredentials([]));
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setPublishing(false);
    }
  }

  async function handleRegenerate() {
    if (!id || !window.confirm("Regenerate this agent's invoke credential? The old client_secret stops working immediately."))
      return;
    setRegenerating(true);
    setError(null);
    try {
      const secret = await regenerateAgentCredential(id);
      setRevealedSecret(secret);
      listAgentCredentials(id)
        .then(setCredentials)
        .catch(() => setCredentials([]));
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRegenerating(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error && !agent) return <p className="error-text">{error}</p>;
  if (!agent) return null;

  return (
    <div className="jd-detail-page">
      <Card>
        <div className="jd-detail-header">
          <div>
            <Badge tone="neutral" className="badge--jd-code">
              {agent.agent_code}
            </Badge>
            <h2>{agent.name}</h2>
          </div>
          <div className="jd-detail-header__actions">
            {agent.status === "draft" ? (
              <Button icon={<CheckCircleIcon width={16} height={16} />} onClick={handlePublish} loading={publishing}>
                Publish
              </Button>
            ) : (
              <Button variant="secondary" onClick={handleRegenerate} loading={regenerating}>
                Regenerate credential
              </Button>
            )}
          </div>
        </div>
        <div className="audit-summary">
          <Badge tone={agent.status === "published" ? "success" : "neutral"}>{agent.status}</Badge>{" "}
          Created by <strong>{agent.created_by || "unknown"}</strong> on {formatDateTime(agent.created_at)}
        </div>
        {agent.description && <p>{agent.description}</p>}

        {revealedSecret && (
          <div className="context-block">
            <h4>Client secret (copy now - shown once)</h4>
            <pre className="code-editor">{revealedSecret}</pre>
            <p className="hint-text">
              Pair this with the client_id below and exchange both for a Bearer token via iam-service's
              <code> POST /auth/token</code> to call <code>/invoke</code>.
            </p>
          </div>
        )}

        <div className="context-block">
          <h4>Model</h4>
          <p>
            {agent.primary_model.name} ({agent.primary_model.provider})
            {agent.fallback_model && <> - fallback: {agent.fallback_model.name}</>}
          </p>
        </div>
        <div className="context-block">
          <h4>Limits</h4>
          <p>
            {agent.max_output_tokens} max output tokens - {agent.timeout_seconds}s timeout -{" "}
            {agent.rate_limit_per_minute} requests/minute
          </p>
        </div>
        <div className="context-block">
          <h4>Input variables</h4>
          <p>{agent.input_variables.length > 0 ? agent.input_variables.join(", ") : "none detected"}</p>
        </div>
      </Card>

      <Card title="System prompt">
        <pre className="code-editor">{agent.system_prompt}</pre>
      </Card>

      <Card title="User prompt template">
        <pre className="code-editor">{agent.user_prompt_template}</pre>
      </Card>

      {agent.status === "published" && (
        <Card title="Credentials">
          {credentials.length === 0 ? (
            <EmptyState icon={<ClockIcon width={26} height={26} />} title="No credential on record" />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Client ID</th>
                  <th>Created</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <code>{c.client_id}</code>
                    </td>
                    <td>{formatDateTime(c.created_at)}</td>
                    <td>
                      <Badge tone={c.revoked_at ? "danger" : "success"}>{c.revoked_at ? "revoked" : "active"}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      <Card title="Recent usage">
        {usage.length === 0 ? (
          <EmptyState icon={<ClockIcon width={26} height={26} />} title="No invocations yet" />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Result</th>
                <th>Provider</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((u) => (
                <tr key={u.id}>
                  <td>{formatDateTime(u.created_at)}</td>
                  <td>
                    <Badge tone={u.success ? "success" : "danger"}>{u.success ? "success" : "failed"}</Badge>
                  </td>
                  <td>{u.provider_used || "-"}</td>
                  <td>{Math.round(u.latency_ms)}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
