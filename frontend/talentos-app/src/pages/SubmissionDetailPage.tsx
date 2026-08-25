import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createOrGetInterviewSession, deleteSubmission, getJDAnalysis, getResumeAnalysis, getSubmission } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { hasAnyPermission, hasPermission, PERMISSIONS } from "../lib/permissions";
import CandidateCallsPanel from "../components/CandidateCallsPanel";
import MatchAnalysisCard from "../components/MatchAnalysisCard";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import { LockIcon, SubmissionIcon, TargetIcon } from "../components/ui/icons";
import type { JDAnalysis, ResumeAnalysis, Submission } from "../types";

export default function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Note: this page also fetches the underlying requirement and applicant records, which are
  // separately gated server-side on REQUIREMENTS_READ/APPLICANTS_READ - a session with
  // SUBMISSIONS_READ but neither of those (an unusual grant combination) would pass this gate
  // but could still see a fetch error for the nested JD/resume detail. Not handled here.
  const canRead = hasPermission(PERMISSIONS.SUBMISSIONS_READ);
  const canDelete = hasPermission(PERMISSIONS.SUBMISSIONS_DELETE);
  const canSeeCalls = hasAnyPermission([PERMISSIONS.VOICEAGENT_CALLS_READ, PERMISSIONS.VOICEAGENT_CALLS_WRITE]);

  const [submission, setSubmission] = useState<Submission | null>(null);
  const [jd, setJd] = useState<JDAnalysis | null>(null);
  const [resume, setResume] = useState<ResumeAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingAssessment, setStartingAssessment] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!id || !canRead) return;
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
  }, [id, canRead]);

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

  if (!canRead) {
    return (
      <Card>
        <EmptyState
          icon={<LockIcon width={26} height={26} />}
          title="Access denied"
          description="Your account doesn't have permission to view submissions (talentos.intake.submissions.read)."
        />
      </Card>
    );
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
            {canDelete && (
              <Button variant="danger" onClick={handleDelete} loading={deleting}>
                Delete
              </Button>
            )}
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

      {canSeeCalls && (
        <Card title="Candidate calls">
          <CandidateCallsPanel submissionId={submission.id} jdAnalysisId={jd.id} candidatePhone={resume.candidate_phone} />
        </Card>
      )}
    </div>
  );
}
