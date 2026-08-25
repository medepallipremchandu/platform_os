import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeJD } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import JDAnalysisForm from "../components/JDAnalysisForm";
import Card from "../components/ui/Card";
import PageHeader from "../components/ui/PageHeader";

export default function NewJDAnalysisPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze(jdText: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeJD(jdText);
      navigate(`/requirements/${result.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Requirements"
        title="Analyze a job description"
        subtitle="Extracts job/role context and weighted skill rubrics. Calls the LLM provider and can take up to a minute or two for large/detailed JDs."
      />
      <Card>
        <JDAnalysisForm loading={loading} onSubmit={handleAnalyze} />
        {error && <p className="error-text">{error}</p>}
      </Card>
    </div>
  );
}
