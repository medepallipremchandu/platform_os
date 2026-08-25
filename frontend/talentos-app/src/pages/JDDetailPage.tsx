import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteJDAnalysis, getJDAnalysis, getJDAuditLog, updateJDAnalysis } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { hasAnyPermission, hasPermission, PERMISSIONS } from "../lib/permissions";
import AuditHistory from "../components/AuditHistory";
import CallAgentConfigPanel from "../components/CallAgentConfigPanel";
import JDEditForm from "../components/JDEditForm";
import SkillCard from "../components/SkillCard";
import Tabs from "../components/Tabs";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import { LockIcon } from "../components/ui/icons";
import type { AuditLogEntry, JDAnalysis, Skill } from "../types";

type TabKey = "jd" | "skills" | "calling";

const ALL_TABS: { key: TabKey; label: string }[] = [
  { key: "jd", label: "Requirement" },
  { key: "skills", label: "Skills & rubrics" },
  { key: "calling", label: "Call screening" },
];

export default function JDDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const canRead = hasPermission(PERMISSIONS.REQUIREMENTS_READ);
  const canWrite = hasPermission(PERMISSIONS.REQUIREMENTS_WRITE);
  const canDelete = hasPermission(PERMISSIONS.REQUIREMENTS_DELETE);
  const canSeeCalling = hasAnyPermission([PERMISSIONS.VOICEAGENT_CALLS_READ, PERMISSIONS.VOICEAGENT_CALLS_WRITE]);
  const tabs = ALL_TABS.filter((tab) => tab.key !== "calling" || canSeeCalling);

  const [activeTab, setActiveTab] = useState<TabKey>("jd");
  const [jdAnalysis, setJdAnalysis] = useState<JDAnalysis | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id || !canRead) return;
    setLoading(true);
    setError(null);
    Promise.all([getJDAnalysis(id), getJDAuditLog(id)])
      .then(([jd, log]) => {
        setJdAnalysis(jd);
        setAuditLog(log);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id, canRead]);

  // If the "calling" tab was active and then disappeared (e.g. permissions changed underneath
  // us, or this ran once before the permission check above), never leave activeTab pointing at a
  // tab that's no longer rendered.
  useEffect(() => {
    if (activeTab === "calling" && !canSeeCalling) setActiveTab("jd");
  }, [activeTab, canSeeCalling]);

  async function handleSkillChange(updated: Skill) {
    if (!id) return;
    setJdAnalysis((prev) =>
      prev ? { ...prev, skills: prev.skills.map((s) => (s.id === updated.id ? updated : s)) } : prev,
    );
    try {
      setAuditLog(await getJDAuditLog(id));
    } catch {
      // Non-fatal - the skill/rubric edit itself already succeeded; the audit log will just be
      // stale until the next refresh.
    }
  }

  async function handleSaveEdit(payload: { job_title: string; role_context: string; job_context_summary: string }) {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await updateJDAnalysis(id, payload);
      setJdAnalysis(updated);
      setAuditLog(await getJDAuditLog(id));
      setEditing(false);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!id || !window.confirm("Delete this requirement? It will be hidden from the list but not permanently removed.")) return;
    setDeleting(true);
    try {
      await deleteJDAnalysis(id);
      navigate("/requirements");
    } catch (err) {
      setError(extractErrorMessage(err));
      setDeleting(false);
    }
  }

  if (!canRead) {
    return (
      <Card>
        <EmptyState
          icon={<LockIcon width={26} height={26} />}
          title="Access denied"
          description="Your account doesn't have permission to view requirements (talentos.intake.requirements.read)."
        />
      </Card>
    );
  }

  if (loading) return <SkeletonCard />;
  if (error) return <p className="error-text">{error}</p>;
  if (!jdAnalysis) return null;

  return (
    <div className="jd-detail-page">
      <Tabs active={activeTab} onChange={(key) => setActiveTab(key as TabKey)} tabs={tabs} />

      {activeTab === "jd" && (
        <Card>
          <div className="jd-detail-header">
            <div>
              <Badge tone="neutral" className="badge--jd-code">
                {jdAnalysis.jd_code}
              </Badge>
              <h2>{jdAnalysis.job_title || "Job context"}</h2>
            </div>
            <div className="jd-detail-header__actions">
              <Link to={`/submissions/new?jdAnalysisId=${jdAnalysis.id}`}>
                <Button>Submit an applicant</Button>
              </Link>
              {canWrite && !editing && (
                <Button variant="secondary" onClick={() => setEditing(true)}>
                  Edit
                </Button>
              )}
              {canDelete && (
                <Button variant="danger" onClick={handleDelete} loading={deleting}>
                  Delete
                </Button>
              )}
            </div>
          </div>

          <div className="audit-summary">
            <span>
              Created by <strong>{jdAnalysis.created_by || "unknown"}</strong> on{" "}
              {formatDateTime(jdAnalysis.created_at)}
            </span>
            {jdAnalysis.modified_at && (
              <span>
                {" "}
                - last modified by <strong>{jdAnalysis.modified_by}</strong> on{" "}
                {formatDateTime(jdAnalysis.modified_at)}
              </span>
            )}
          </div>
          <AuditHistory entries={auditLog} />

          {editing ? (
            <JDEditForm jdAnalysis={jdAnalysis} saving={saving} onSave={handleSaveEdit} onCancel={() => setEditing(false)} />
          ) : (
            <>
              {jdAnalysis.job_context_summary && <p>{jdAnalysis.job_context_summary}</p>}
              {jdAnalysis.role_context && (
                <div className="context-block">
                  <h4>Role context</h4>
                  <p>{jdAnalysis.role_context}</p>
                </div>
              )}
            </>
          )}

          {jdAnalysis.responsibilities.length > 0 && (
            <div className="context-block">
              <h4>Responsibilities</h4>
              <ul>
                {jdAnalysis.responsibilities.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {jdAnalysis.qualifications.length > 0 && (
            <div className="context-block">
              <h4>Qualifications</h4>
              <ul>
                {jdAnalysis.qualifications.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {activeTab === "skills" && (
        <Card title="Skills & rubrics">
          <div className="skill-list">
            {jdAnalysis.skills.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                jdId={jdAnalysis.id}
                canEdit={canWrite}
                onSkillChange={handleSkillChange}
              />
            ))}
          </div>
        </Card>
      )}

      {activeTab === "calling" && canSeeCalling && (
        <Card title="Call agent configuration">
          <CallAgentConfigPanel jdAnalysisId={jdAnalysis.id} />
        </Card>
      )}
    </div>
  );
}
