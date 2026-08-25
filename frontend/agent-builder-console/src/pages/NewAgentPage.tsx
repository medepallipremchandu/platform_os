import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createAgent, listModels } from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { LockIcon, SparkleIcon } from "../components/ui/icons";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import type { Model } from "../types";

export default function NewAgentPage() {
  const navigate = useNavigate();
  const canWrite = hasPermission(PERMISSIONS.AGENTS_WRITE);
  const [models, setModels] = useState<Model[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPromptTemplate, setUserPromptTemplate] = useState("");
  const [primaryModelId, setPrimaryModelId] = useState("");
  const [fallbackModelId, setFallbackModelId] = useState("");
  const [maxOutputTokens, setMaxOutputTokens] = useState(8192);
  const [timeoutSeconds, setTimeoutSeconds] = useState(60);
  const [rateLimitPerMinute, setRateLimitPerMinute] = useState(60);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canWrite) return;
    listModels()
      .then(setModels)
      .catch((err) => setError(extractErrorMessage(err)));
  }, [canWrite]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!primaryModelId) return;
    setLoading(true);
    setError(null);
    try {
      const agent = await createAgent({
        name,
        description: description || undefined,
        system_prompt: systemPrompt,
        user_prompt_template: userPromptTemplate,
        primary_model_id: primaryModelId,
        fallback_model_id: fallbackModelId || undefined,
        max_output_tokens: maxOutputTokens,
        timeout_seconds: timeoutSeconds,
        rate_limit_per_minute: rateLimitPerMinute,
      });
      navigate(`/agents/${agent.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setLoading(false);
    }
  }

  if (!canWrite) {
    return (
      <div className="page">
        <PageHeader title="Create agent" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to create agents (talentos.agentbuilder.agents.write)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Create agent"
        subtitle={
          'Write a prompt with {{placeholders}} for the values callers will supply, e.g. "Analyze this job description: {{jd_text}}". Every {{placeholder}} becomes a required input variable automatically.'
        }
      />
      <Card>
        {models.length === 0 && (
          <p className="hint-text">
            No models registered yet - register one on the Models page before creating an agent.
          </p>
        )}
        <form onSubmit={handleSubmit} className="jd-form">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <label>
            System prompt
            <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={4} required />
          </label>
          <label>
            User prompt template
            <textarea
              value={userPromptTemplate}
              onChange={(e) => setUserPromptTemplate(e.target.value)}
              rows={10}
              className="code-editor"
              spellCheck={false}
              required
            />
          </label>
          <label>
            Primary model
            <select value={primaryModelId} onChange={(e) => setPrimaryModelId(e.target.value)} required>
              <option value="">Select a model...</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.model_code} - {m.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Fallback model (optional)
            <select value={fallbackModelId} onChange={(e) => setFallbackModelId(e.target.value)}>
              <option value="">None</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.model_code} - {m.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Max output tokens
            <input
              type="number"
              min={256}
              max={64000}
              value={maxOutputTokens}
              onChange={(e) => setMaxOutputTokens(Number(e.target.value))}
            />
          </label>
          <label>
            Timeout (seconds)
            <input
              type="number"
              min={5}
              max={300}
              value={timeoutSeconds}
              onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            />
          </label>
          <label>
            Rate limit (requests / minute)
            <input
              type="number"
              min={1}
              max={6000}
              value={rateLimitPerMinute}
              onChange={(e) => setRateLimitPerMinute(Number(e.target.value))}
            />
          </label>
          <Button type="submit" icon={<SparkleIcon width={16} height={16} />} loading={loading} disabled={!primaryModelId}>
            Create agent
          </Button>
        </form>
        {error && <p className="error-text">{error}</p>}
      </Card>
    </div>
  );
}
