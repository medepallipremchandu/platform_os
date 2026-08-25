import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createOrGetInterviewSession, deleteSubmission, getJDAnalysis, getResumeAnalysis, getSubmission } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import MatchAnalysisCard from "../components/MatchAnalysisCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import { SubmissionIcon, TargetIcon } from "../components/ui/icons";
import type { JDAnalysis, ResumeAnalysis, Submission } from "../types";

export default function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [submission, setSubmission] = useState<Submission | null>(null);
  const [jd, setJd] = useState<JDAnalysis | null>(null);
  const [resume, setResume] = useState<ResumeAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingAssessment, setStartingAssessment] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getSubmission(id)
      .then(async (s) => {
        setSubmission(s);
        const [jdResult, resumeResult] = await Promise.all([
          getJDAnalysis(s.jd_analysis_id),
          getResumeAnalysis(s.resume_analysis_id),
        ]);
        setJd(jdResult);
        setResume(resumeResult);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleStartAssessment() {
    if (!id) return;
    setStartingAssessment(true);
    setError(null);
    try {
      const session = await createOrGetInterviewSession(id);
      navigate(`/interview-sessions/${session.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setStartingAssessment(false);
    }
  }

  async function handleDelete() {
    if (!id || !window.confirm("Delete this submission?")) return;
    setDeleting(true);
    try {
      await deleteSubmission(id);
      navigate("/submissions");
    } catch (err) {
      setError(extractErrorMessage(err));
      setDeleting(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error) return <p className="error-text">{error}</p>;
  if (!submission || !jd || !resume) return null;

  return (
    <div className="jd-detail-page">
      <Card>
        <div className="jd-detail-header">
          <div>
            <Badge tone="neutral" className="badge--jd-code">
              {submission.submission_code}
            </Badge>
            <h2>
              {jd.job_title} &times; {resume.candidate_name}
            </h2>
          </div>
          <div className="jd-detail-header__actions">
            <Button icon={<TargetIcon width={16} height={16} />} onClick={handleStartAssessment} loading={startingAssessment}>
              Start assessment
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </div>
        </div>
        <div className="audit-summary">
          <span>
            Created by <strong>{submission.created_by || "unknown"}</strong> on{" "}
            {formatDateTime(submission.created_at)}
          </span>
        </div>
        <p className="hint-text">
          Requirement: <Link to={`/requirements/${jd.id}`}>{jd.jd_code}</Link> - Applicant:{" "}
          <Link to={`/applicants/${resume.id}`}>{resume.resume_code}</Link>
        </p>
      </Card>

      <Card title="Match analysis">
        {submission.match_analysis ? (
          <MatchAnalysisCard match={submission.match_analysis} />
        ) : (
          <EmptyState icon={<SubmissionIcon width={26} height={26} />} title="No match analysis available" />
        )}
      </Card>
    </div>
  );
}
