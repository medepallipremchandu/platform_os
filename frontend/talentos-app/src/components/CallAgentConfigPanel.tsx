import { useEffect, useState } from "react";
import { getJDCallConfig, setJDCallConfig } from "../api/voiceAgent";
import { listCallAgentConfigs } from "../api/voiceAgentDirect";
import { extractErrorMessage } from "../api/client";
import type { CallAgentConfig, JDCallAgentConfig } from "../types";
import Button from "./ui/Button";
import EmptyState from "./ui/EmptyState";
import { SkeletonLine } from "./ui/Skeleton";
import { PhoneIcon } from "./ui/icons";

const VOICE_AGENT_CONSOLE_URL = import.meta.env.VITE_VOICE_AGENT_CONSOLE_URL || "http://localhost:5177";

interface Props {
  jdAnalysisId: string;
}

/** JD detail page section: which voice-agent-service call-agent config (if any) candidates
 * under this JD get AI-screened with. The dropdown itself is populated by a direct, read-only
 * call to voice-agent-service (src/api/voiceAgentDirect.ts); saving goes through this app's own
 * backend (src/api/voiceAgent.ts). */
export default function CallAgentConfigPanel({ jdAnalysisId }: Props) {
  const [callAgents, setCallAgents] = useState<CallAgentConfig[] | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([listCallAgentConfigs(), getJDCallConfig(jdAnalysisId)])
      .then(([agents, config]) => {
        setCallAgents(agents);
        applyConfig(agents, config);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jdAnalysisId]);

  function applyConfig(agents: CallAgentConfig[], config: JDCallAgentConfig | null) {
    if (config) {
      setSelectedId(config.call_agent_config_id);
      setEnabled(config.enabled);
    } else if (agents.length > 0) {
      setSelectedId(agents[0].id);
    }
  }

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true);
    setError(null);
    try {
      await setJDCallConfig(jdAnalysisId, { call_agent_config_id: selectedId, enabled });
      setSavedAt(Date.now());
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="call-agent-config">
        <SkeletonLine width="60%" />
        <SkeletonLine width="40%" />
      </div>
    );
  }

  if (error) return <p className="error-text">{error}</p>;

  if (!callAgents || callAgents.length === 0) {
    return (
      <EmptyState
        icon={<PhoneIcon width={24} height={24} />}
        title="No call agent configs available yet"
        description="Create a call agent config (script + retry policy) in voice-agent-console first, then come back here to assign one to this requirement."
        action={
          <a href={VOICE_AGENT_CONSOLE_URL} target="_blank" rel="noreferrer">
            <Button variant="secondary">Open voice-agent-console</Button>
          </a>
        }
      />
    );
  }

  return (
    <div className="call-agent-config">
      <label>
        Call agent config
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          {callAgents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name}
              {agent.description ? ` - ${agent.description}` : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="call-agent-config__toggle-row">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        AI phone screening enabled for candidates under this requirement
      </label>
      <div className="call-agent-config__actions">
        <Button onClick={handleSave} loading={saving} disabled={!selectedId}>
          Save
        </Button>
        {savedAt && !saving && <span className="call-agent-config__saved-hint">Saved</span>}
      </div>
    </div>
  );
}
