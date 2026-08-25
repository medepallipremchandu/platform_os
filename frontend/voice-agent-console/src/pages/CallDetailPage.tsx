import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { cancelCall, getCall, getCallConversation, getCallEvents, getCallSummary } from "../api/voiceAgent";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import Modal from "../components/ui/Modal";
import { SkeletonCard } from "../components/ui/Skeleton";
import { ArrowLeftIcon, ClockIcon, FileTextIcon, HistoryIcon, MessageIcon, XCircleIcon } from "../components/ui/icons";
import { formatDateTime, humanizeStatus } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { toneForCallStatus } from "../lib/tone";
import { isCallInFlight } from "../types";
import type { CallDetail, CallEvent, CallSummaryDetail, ConversationTurn } from "../types";

type Tab = "events" | "transcript" | "summary";

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const canWrite = hasPermission(PERMISSIONS.CALLS_WRITE);

  const [call, setCall] = useState<CallDetail | null>(null);
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [summary, setSummary] = useState<CallSummaryDetail | null>(null);
  const [tab, setTab] = useState<Tab>("transcript");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [graceful, setGraceful] = useState(true);
  const [cancelling, setCancelling] = useState(false);

  function refresh() {
    if (!id) return;
    Promise.all([
      getCall(id),
      getCallEvents(id).catch(() => []),
      getCallConversation(id).catch(() => []),
      getCallSummary(id).catch(() => null),
    ])
      .then(([c, e, conv, s]) => {
        setCall(c);
        setEvents(e);
        setConversation(conv);
        setSummary(s);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, [id]);

  async function handleCancel() {
    if (!id) return;
    setCancelling(true);
    try {
      const updated = await cancelCall(id, graceful);
      setCall(updated);
      setCancelModalOpen(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setCancelling(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error && !call) return <p className="error-text">{error}</p>;
  if (!call) return null;

  const canCancel = canWrite && isCallInFlight(call.status);

  return (
    <div className="jd-detail-page">
      <Button variant="ghost" size="sm" icon={<ArrowLeftIcon width={16} height={16} />} onClick={() => navigate("/calls")}>
        Back to calls
      </Button>

      {error && <p className="error-text">{error}</p>}

      <Card>
        <div className="call-detail-header">
          <div className="call-detail-header__meta">
            <div className="call-detail-header__number">
              <code>{call.to_number}</code>
            </div>
            <div>
              <Badge tone={toneForCallStatus(call.status)}>{humanizeStatus(call.status)}</Badge>{" "}
              {call.root_call_id && <span className="hint-text">retry attempt #{call.attempt_number} of call {call.root_call_id}</span>}
            </div>
          </div>
          {canCancel && (
            <div className="call-detail-header__actions">
              <Button variant="danger" icon={<XCircleIcon width={16} height={16} />} onClick={() => setCancelModalOpen(true)}>
                Cancel call
              </Button>
            </div>
          )}
        </div>

        <div className="detail-grid">
          <div className="detail-grid__item">
            <span className="detail-grid__label">From</span>
            <span className="detail-grid__value">{call.from_number || "-"}</span>
          </div>
          <div className="detail-grid__item">
            <span className="detail-grid__label">Placed</span>
            <span className="detail-grid__value">{formatDateTime(call.created_at)}</span>
          </div>
          <div className="detail-grid__item">
            <span className="detail-grid__label">Connected</span>
            <span className="detail-grid__value">{call.connected_at ? formatDateTime(call.connected_at) : "-"}</span>
          </div>
          <div className="detail-grid__item">
            <span className="detail-grid__label">Ended</span>
            <span className="detail-grid__value">{call.ended_at ? formatDateTime(call.ended_at) : "-"}</span>
          </div>
          <div className="detail-grid__item">
            <span className="detail-grid__label">End reason</span>
            <span className="detail-grid__value">{call.end_reason || "-"}</span>
          </div>
          {call.max_conversation_duration_minutes != null && (
            <div className="detail-grid__item">
              <span className="detail-grid__label">Max duration</span>
              <span className="detail-grid__value">{call.max_conversation_duration_minutes} min</span>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="tabs">
          <button type="button" className={`tabs__tab ${tab === "transcript" ? "tabs__tab--active" : ""}`} onClick={() => setTab("transcript")}>
            <MessageIcon width={15} height={15} /> Transcript
            {conversation.length > 0 && <span className="tabs__badge">{conversation.length}</span>}
          </button>
          <button type="button" className={`tabs__tab ${tab === "events" ? "tabs__tab--active" : ""}`} onClick={() => setTab("events")}>
            <HistoryIcon width={15} height={15} /> Events
            {events.length > 0 && <span className="tabs__badge">{events.length}</span>}
          </button>
          <button type="button" className={`tabs__tab ${tab === "summary" ? "tabs__tab--active" : ""}`} onClick={() => setTab("summary")}>
            <FileTextIcon width={15} height={15} /> Summary
          </button>
        </div>

        <div className="tabs__panel">
          {tab === "transcript" &&
            (conversation.length === 0 ? (
              <EmptyState icon={<MessageIcon width={26} height={26} />} title="No transcript yet" description="Turns will appear here once the conversation starts." />
            ) : (
              <div className="transcript">
                {conversation
                  .slice()
                  .sort((a, b) => a.turn_index - b.turn_index)
                  .map((turn) => (
                    <div className={`transcript__turn transcript__turn--${turn.speaker}`} key={turn.id}>
                      <div className="transcript__bubble">{turn.text}</div>
                      <div className="transcript__meta">
                        {turn.speaker === "ai" ? "AI agent" : "Callee"} - {formatDateTime(turn.created_at)}
                      </div>
                    </div>
                  ))}
              </div>
            ))}

          {tab === "events" &&
            (events.length === 0 ? (
              <EmptyState icon={<ClockIcon width={26} height={26} />} title="No events recorded yet" />
            ) : (
              <div className="event-timeline">
                {events
                  .slice()
                  .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
                  .map((ev) => (
                    <div className="event-timeline__item" key={ev.id}>
                      <div className="event-timeline__dot" />
                      <div className="event-timeline__body">
                        <span className="event-timeline__type">{ev.event_type}</span>
                        <span className="event-timeline__time">{formatDateTime(ev.created_at)}</span>
                        {Object.keys(ev.payload || {}).length > 0 && (
                          <pre className="event-timeline__payload">{JSON.stringify(ev.payload, null, 2)}</pre>
                        )}
                      </div>
                    </div>
                  ))}
              </div>
            ))}

          {tab === "summary" &&
            (!summary ? (
              <EmptyState icon={<FileTextIcon width={26} height={26} />} title="No summary yet" description="A summary is generated once the call completes." />
            ) : (
              <div>
                <p>{summary.summary_text}</p>
                {Object.keys(summary.extracted_fields || {}).length > 0 && (
                  <table className="extracted-fields">
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summary.extracted_fields).map(([key, value]) => (
                        <tr key={key}>
                          <td>
                            <code>{key}</code>
                          </td>
                          <td>{typeof value === "object" ? JSON.stringify(value) : String(value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="hint-text" style={{ marginTop: "var(--space-3)" }}>
                  Generated {formatDateTime(summary.created_at)}
                </p>
              </div>
            ))}
        </div>
      </Card>

      {cancelModalOpen && (
        <Modal
          title="Cancel call"
          onClose={() => setCancelModalOpen(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setCancelModalOpen(false)} disabled={cancelling}>
                Never mind
              </Button>
              <Button variant="danger" onClick={handleCancel} loading={cancelling}>
                Cancel call
              </Button>
            </>
          }
        >
          <div className="form">
            <label className="checklist__item">
              <input type="radio" name="graceful" checked={graceful} onChange={() => setGraceful(true)} />
              Graceful - let the AI wrap up the current turn and say a closing line first
            </label>
            <label className="checklist__item">
              <input type="radio" name="graceful" checked={!graceful} onChange={() => setGraceful(false)} />
              Immediate - hang up right away
            </label>
          </div>
        </Modal>
      )}
    </div>
  );
}
