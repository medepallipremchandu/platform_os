import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeResume } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import ResumeUploadForm from "../components/ResumeUploadForm";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";

export default function NewResumeAnalysisPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(file: File) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeResume(file);
      navigate(`/applicants/${result.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Applicants"
        title="Analyze a resume"
        subtitle="Legacy .doc files aren't supported - convert to .docx or .pdf first. This calls the LLM provider and may take up to a minute."
      />
      <Card>
        <ResumeUploadForm loading={loading} onSubmit={handleAnalyze} />
        {error && <p className="error-text">{error}</p>}
      </Card>
    </div>
  );
}
