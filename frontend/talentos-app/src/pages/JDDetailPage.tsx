import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteJDAnalysis, getJDAnalysis, getJDAuditLog, updateJDAnalysis } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import AuditHistory from "../components/AuditHistory";
import JDEditForm from "../components/JDEditForm";
import SkillCard from "../components/SkillCard";
import Tabs from "../components/Tabs";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { SkeletonCard } from "../components/ui/Skeleton";
import type { AuditLogEntry, JDAnalysis } from "../types";

type TabKey = "jd" | "skills";

export default function JDDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<TabKey>("jd");
  const [jdAnalysis, setJdAnalysis] = useState<JDAnalysis | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.all([getJDAnalysis(id), getJDAuditLog(id)])
      .then(([jd, log]) => {
        setJdAnalysis(jd);
        setAuditLog(log);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

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

  if (loading) return <SkeletonCard />;
  if (error) return <p className="error-text">{error}</p>;
  if (!jdAnalysis) return null;

  return (
    <div className="jd-detail-page">
      <Tabs
        active={activeTab}
        onChange={(key) => setActiveTab(key as TabKey)}
        tabs={[
          { key: "jd", label: "Requirement" },
          { key: "skills", label: "Skills & rubrics" },
        ]}
      />

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
              {!editing && (
                <Button variant="secondary" onClick={() => setEditing(true)}>
                  Edit
                </Button>
              )}
              <Button variant="danger" onClick={handleDelete} loading={deleting}>
                Delete
              </Button>
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
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
