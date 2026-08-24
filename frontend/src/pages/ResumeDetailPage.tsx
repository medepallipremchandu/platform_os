import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { deleteResumeAnalysis, getResumeAnalysis, getResumeAuditLog } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import AuditHistory from "../components/AuditHistory";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import { SkeletonCard } from "../components/ui/Skeleton";
import type { AuditLogEntry, ResumeAnalysis } from "../types";

export default function ResumeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [resume, setResume] = useState<ResumeAnalysis | null>(null);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.all([getResumeAnalysis(id), getResumeAuditLog(id)])
      .then(([r, log]) => {
        setResume(r);
        setAuditLog(log);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleDelete() {
    if (!id || !window.confirm("Delete this applicant? It will be hidden from the list but not permanently removed.")) return;
    setDeleting(true);
    try {
      await deleteResumeAnalysis(id);
      navigate("/applicants");
    } catch (err) {
      setError(extractErrorMessage(err));
      setDeleting(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error) return <p className="error-text">{error}</p>;
  if (!resume) return null;

  return (
    <div className="jd-detail-page">
      <Card>
        <div className="jd-detail-header">
          <div>
            <Badge tone="neutral" className="badge--jd-code">
              {resume.resume_code}
            </Badge>
            <h2>{resume.candidate_name || "Candidate"}</h2>
          </div>
          <div className="jd-detail-header__actions">
            <Link to={`/submissions/new?resumeAnalysisId=${resume.id}`}>
              <Button>Submit against a requirement</Button>
            </Link>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </div>
        </div>

        <div className="audit-summary">
          <span>
            Uploaded by <strong>{resume.created_by || "unknown"}</strong> on {formatDateTime(resume.created_at)}
          </span>
          {resume.modified_at && (
            <span>
              {" "}
              - last modified by <strong>{resume.modified_by}</strong> on {formatDateTime(resume.modified_at)}
            </span>
          )}
        </div>
        <AuditHistory entries={auditLog} />

        <p className="hint-text">
          {resume.original_filename} ({resume.file_type}) - {resume.candidate_email || "no email"} -{" "}
          {resume.candidate_phone || "no phone"} -{" "}
          {resume.total_experience_years != null ? `${resume.total_experience_years} years experience` : "experience unknown"}
        </p>
        {resume.summary && <p>{resume.summary}</p>}
      </Card>

      <Card title="Skills">
        <ul className="rubric-list">
          {resume.skills.map((s, i) => (
            <li key={i}>
              <div className="rubric-list__row">
                <strong>{s.name}</strong>
                <span>
                  {s.proficiency || "-"}
                  {s.years_experience != null ? ` (${s.years_experience}y)` : ""}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Work history">
        {resume.work_history.map((w, i) => (
          <div className="context-block" key={i}>
            <h4>
              {w.title} - {w.company} ({w.start_date || "?"} - {w.end_date || "?"})
            </h4>
            <p>{w.description}</p>
          </div>
        ))}
      </Card>

      <Card title="Education & certifications">
        <div className="context-block">
          <h4>Education</h4>
          <ul>
            {resume.education.map((e, i) => (
              <li key={i}>
                {e.degree} {e.field_of_study} - {e.institution} ({e.graduation_year || "?"})
              </li>
            ))}
          </ul>
        </div>
        {resume.certifications.length > 0 && (
          <div className="context-block">
            <h4>Certifications</h4>
            <ul>
              {resume.certifications.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
