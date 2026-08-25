import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJDAnalyses, listResumeAnalyses, listSubmissions } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import StatCard from "../components/ui/StatCard";
import { DocumentIcon, SubmissionIcon, TargetIcon, UsersIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import { toneForScore } from "../lib/tone";
import type { JDAnalysisSummary, ResumeAnalysisSummary, SubmissionSummary } from "../types";

export default function DashboardPage() {
  const [jds, setJds] = useState<JDAnalysisSummary[] | null>(null);
  const [resumes, setResumes] = useState<ResumeAnalysisSummary[] | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listJDAnalyses(), listResumeAnalyses(), listSubmissions()])
      .then(([jdList, resumeList, submissionList]) => {
        setJds(jdList);
        setResumes(resumeList);
        setSubmissions(submissionList);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  const scoredSubmissions = (submissions || []).filter((s) => s.overall_match_percentage != null);
  const averageMatch = scoredSubmissions.length
    ? Math.round(
        scoredSubmissions.reduce((sum, s) => sum + (s.overall_match_percentage || 0), 0) /
          scoredSubmissions.length,
      )
    : null;
  const recentSubmissions = (submissions || []).slice(0, 5);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Overview"
        title="Welcome back"
        subtitle="A snapshot of requirements, applicants, and submissions across your pipeline."
      />

      {error && <p className="error-text">{error}</p>}

      <div className="stat-grid">
        <StatCard
          icon={<DocumentIcon />}
          label="Requirements"
          value={jds?.length ?? null}
          hint="Job descriptions analyzed"
          tone="brand"
        />
        <StatCard
          icon={<UsersIcon />}
          label="Applicants"
          value={resumes?.length ?? null}
          hint="Resumes analyzed"
          tone="info"
        />
        <StatCard
          icon={<SubmissionIcon />}
          label="Submissions"
          value={submissions?.length ?? null}
          hint="JD x applicant pairings"
          tone="warning"
        />
        <StatCard
          icon={<TargetIcon />}
          label="Avg. match score"
          value={averageMatch != null ? `${averageMatch}%` : "-"}
          hint="Across scored submissions"
          tone="success"
        />
      </div>

      <Card
        title="Recent submissions"
        actions={
          <Link to="/submissions" className="link">
            View all
          </Link>
        }
      >
        {submissions === null ? (
          <SkeletonRows rows={4} columns={4} />
        ) : recentSubmissions.length === 0 ? (
          <EmptyState
            icon={<SubmissionIcon width={28} height={28} />}
            title="No submissions yet"
            description="Pair a requirement with an applicant to run a match analysis."
            action={
              <Link to="/submissions/new">
                <button type="button">New submission</button>
              </Link>
            }
          />
        ) : (
          <ul className="activity-list">
            {recentSubmissions.map((s) => (
              <li key={s.id} className="activity-list__item">
                <Link to={`/submissions/${s.id}`} className="activity-list__main">
                  <span className="activity-list__title">
                    {s.job_title || s.jd_code} &times; {s.candidate_name || s.resume_code}
                  </span>
                  <span className="activity-list__meta">{formatDateTime(s.created_at)}</span>
                </Link>
                {s.overall_match_percentage != null && (
                  <Badge tone={toneForScore(s.overall_match_percentage)}>{s.overall_match_percentage}% match</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
