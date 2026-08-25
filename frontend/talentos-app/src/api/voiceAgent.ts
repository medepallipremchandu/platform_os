import { intakeClient } from "./client";
import type { ConversationTurn, JDCallAgentConfig, SubmissionCall } from "../types";

/** Everything here calls THIS app's own backend (talentos-app), which mediates the actual
 * voice-agent-service call placement using its own machine credential - the only thing the
 * frontend talks to voice-agent-service for directly is the read-only call-agent dropdown, see
 * src/api/voiceAgentDirect.ts. */

// --- JD call-agent configuration ---

export async function getJDCallConfig(jdAnalysisId: string): Promise<JDCallAgentConfig | null> {
  const { data } = await intakeClient.get<JDCallAgentConfig | null>(`/jd-analysis/${jdAnalysisId}/call-config`);
  return data;
}

export async function setJDCallConfig(
  jdAnalysisId: string,
  payload: JDCallAgentConfig,
): Promise<JDCallAgentConfig> {
  const { data } = await intakeClient.put<JDCallAgentConfig>(`/jd-analysis/${jdAnalysisId}/call-config`, payload);
  return data;
}

// --- Submission calls ---

export async function listSubmissionCalls(submissionId: string): Promise<SubmissionCall[]> {
  const { data } = await intakeClient.get<SubmissionCall[]>(`/submissions/${submissionId}/calls`);
  return data;
}

export async function triggerSubmissionCall(submissionId: string): Promise<SubmissionCall> {
  const { data } = await intakeClient.post<SubmissionCall>(`/submissions/${submissionId}/calls`);
  return data;
}

export async function getSubmissionCallConversation(
  submissionId: string,
  callId: string,
): Promise<ConversationTurn[]> {
  const { data } = await intakeClient.get<ConversationTurn[]>(
    `/submissions/${submissionId}/calls/${callId}/conversation`,
  );
  return data;
}
