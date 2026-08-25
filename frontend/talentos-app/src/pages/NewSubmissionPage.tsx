import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { createSubmission, listJDAnalyses, listResumeAnalyses } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";
import { TargetIcon } from "../components/ui/icons";
import type { JDAnalysisSummary, ResumeAnalysisSummary } from "../types";

export default function NewSubmissionPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [jds, setJds] = useState<JDAnalysisSummary[]>([]);
  const [resumes, setResumes] = useState<ResumeAnalysisSummary[]>([]);
  const [jdAnalysisId, setJdAnalysisId] = useState(searchParams.get("jdAnalysisId") || "");
  const [resumeAnalysisId, setResumeAnalysisId] = useState(searchParams.get("resumeAnalysisId") || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listJDAnalyses(), listResumeAnalyses()])
      .then(([jdList, resumeList]) => {
        setJds(jdList);
        setResumes(resumeList);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jdAnalysisId || !resumeAnalysisId) return;
    setLoading(true);
    setError(null);
    try {
      const submission = await createSubmission(jdAnalysisId, resumeAnalysisId);
      navigate(`/submissions/${submission.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Submissions"
        title="New submission"
        subtitle="Pairs a requirement with an applicant and runs the match analysis. This calls the LLM provider and may take up to a minute."
      />
      <Card>
        <form onSubmit={handleSubmit} className="jd-form">
          <label htmlFor="jd-select">Job requirement</label>
          <select id="jd-select" value={jdAnalysisId} onChange={(e) => setJdAnalysisId(e.target.value)}>
            <option value="">Select a requirement...</option>
            {jds.map((jd) => (
              <option key={jd.id} value={jd.id}>
                {jd.jd_code} - {jd.job_title || "untitled"}
              </option>
            ))}
          </select>

          <label htmlFor="resume-select">Applicant</label>
          <select id="resume-select" value={resumeAnalysisId} onChange={(e) => setResumeAnalysisId(e.target.value)}>
            <option value="">Select an applicant...</option>
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.resume_code} - {r.candidate_name || "unknown"}
              </option>
            ))}
          </select>

          <Button
            type="submit"
            icon={<TargetIcon width={16} height={16} />}
            loading={loading}
            disabled={!jdAnalysisId || !resumeAnalysisId}
          >
            Create submission &amp; run match analysis
          </Button>
        </form>
        {error && <p className="error-text">{error}</p>}
      </Card>
    </div>
  );
}
