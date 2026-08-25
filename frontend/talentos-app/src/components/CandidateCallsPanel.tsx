import { useCallback, useEffect, useRef, useState } from "react";
import { getJDCallConfig, getSubmissionCallConversation, listSubmissionCalls, triggerSubmissionCall } from "../api/voiceAgent";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { isTerminalCallStatus, toneForCallStatus } from "../lib/tone";
import type { ConversationTurn, SubmissionCall } from "../types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import EmptyState from "./ui/EmptyState";
import { SkeletonRows } from "./ui/Skeleton";
import { PhoneIcon } from "./ui/icons";

const POLL_INTERVAL_MS = 10_000;

interface Props {
  submissionId: string;
  jdAnalysisId: string;
  candidatePhone: string | null;
}

/** Submission detail page panel: trigger an AI phone screen for this candidate, see past
 * attempts, and view a selected attempt's live transcript + cached summary/extracted fields.
 * Polls GET /submissions/{id}/calls every ~10s while any call is still in flight, and stops once
 * every call is terminal - see lib/tone.ts's isTerminalCallStatus (mirrors the backend's own). */
export default function CandidateCallsPanel({ submissionId, jdAnalysisId, candidatePhone }: Props) {
  const canPlaceCalls = hasPermission(PERMISSIONS.VOICEAGENT_CALLS_WRITE);

  const [calls, setCalls] = useState<SubmissionCall[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [callConfigEnabled, setCallConfigEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationTurn[] | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshCalls = useCallback(async () => {
    const rows = await listSubmissionCalls(submissionId);
    setCalls(rows);
    return rows;
  }, [submissionId]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([refreshCalls(), getJDCallConfig(jdAnalysisId)])
      .then(([, config]) => setCallConfigEnabled(config?.enabled ?? false))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submissionId, jdAnalysisId]);

  // Poll while anything is non-terminal; stop once everything settles.
  useEffect(() => {
    const anyInFlight = (calls || []).some((c) => !isTerminalCallStatus(c.status));
    if (!anyInFlight) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(() => {
      refreshCalls().catch(() => undefined);
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [calls, refreshCalls]);

  async function handleCallCandidate() {
    setTriggering(true);
    setError(null);
    try {
      const call = await triggerSubmissionCall(submissionId);
      setCalls((prev) => [...(prev || []), call]);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setTriggering(false);
    }
  }

  async function handleSelectCall(callId: string) {
    setSelectedCallId(callId);
    setConversation(null);
    setConversationLoading(true);
    try {
      const turns = await getSubmissionCallConversation(submissionId, callId);
      setConversation(turns);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setConversationLoading(false);
    }
  }

  if (loading) return <SkeletonRows rows={2} columns={3} />;

  const disabledReason = !candidatePhone
    ? "This candidate has no phone number on file."
    : !callConfigEnabled
      ? "AI phone screening isn't configured (or is disabled) for this requirement yet."
      : null;

  const selectedCall = calls?.find((c) => c.id === selectedCallId) || null;

  // A single candidate's call attempts today - realistically a handful per submission, so this
  // filter is applied client-side over the already-fetched list. If this ever needs to scale to
  // large per-candidate call histories, this should move to server-side filtering/pagination
  // (like listCalls in voice-agent-console's CallsPage) instead.
  const availableStatuses = Array.from(new Set((calls || []).map((c) => c.status)));
  const visibleCalls = statusFilter ? (calls || []).filter((c) => c.status === statusFilter) : calls;

  return (
    <div className="candidate-calls">
      <div className="candidate-calls__header">
        {canPlaceCalls && (
          <Button icon={<PhoneIcon width={16} height={16} />} onClick={handleCallCandidate} loading={triggering} disabled={!!disabledReason}>
            Call candidate
          </Button>
        )}
        {canPlaceCalls && disabledReason && <span className="hint-text">{disabledReason}</span>}
      </div>

      {error && <p className="error-text">{error}</p>}

      {calls && calls.length > 0 && (
        <div className="filter-bar">
          <div className="filter-bar__field">
            <label htmlFor="call-status-filter">Status</label>
            <select id="call-status-filter" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              {availableStatuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {!visibleCalls || visibleCalls.length === 0 ? (
        <EmptyState
          icon={<PhoneIcon width={24} height={24} />}
          title={calls && calls.length > 0 ? "No calls match this filter" : "No call attempts yet"}
        />
      ) : (
        <ul className="call-list">
          {visibleCalls.map((call) => (
            <li
              key={call.id}
              className={`call-list__item ${call.id === selectedCallId ? "call-list__item--selected" : ""}`}
              onClick={() => handleSelectCall(call.id)}
            >
              <div className="call-list__main">
                <span className="call-list__attempt">Attempt {call.attempt_number}</span>
                <span className="call-list__meta">{formatDateTime(call.created_at)}</span>
              </div>
              <Badge tone={toneForCallStatus(call.status)}>{call.status}</Badge>
              {call.end_reason && <span className="call-list__end-reason">{call.end_reason}</span>}
            </li>
          ))}
        </ul>
      )}

      {selectedCall && (
        <div className="call-detail">
          <h4>Attempt {selectedCall.attempt_number} transcript</h4>
          {conversationLoading ? (
            <SkeletonRows rows={3} columns={1} />
          ) : conversation && conversation.length > 0 ? (
            <ul className="call-transcript">
              {conversation.map((turn, i) => (
                <li key={turn.id ?? i} className={`call-transcript__turn call-transcript__turn--${turn.speaker.toLowerCase()}`}>
                  <span className="call-transcript__speaker">{turn.speaker}</span>
                  <span className="call-transcript__text">{turn.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint-text">No transcript available yet.</p>
          )}

          {(selectedCall.summary_text || selectedCall.extracted_fields) && (
            <div className="call-summary">
              <h4>Summary</h4>
              {selectedCall.summary_text && <p>{selectedCall.summary_text}</p>}
              {selectedCall.extracted_fields && Object.keys(selectedCall.extracted_fields).length > 0 && (
                <dl className="call-summary__fields">
                  {Object.entries(selectedCall.extracted_fields).map(([key, value]) => (
                    <div key={key} className="call-summary__field">
                      <dt>{key}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
