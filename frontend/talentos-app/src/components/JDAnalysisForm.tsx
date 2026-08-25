import { useState } from "react";
import Button from "./ui/Button";
import { SparkleIcon } from "./ui/icons";

interface Props {
  loading: boolean;
  onSubmit: (jdText: string) => void;
}

export default function JDAnalysisForm({ loading, onSubmit }: Props) {
  const [jdText, setJdText] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (jdText.trim().length < 20) return;
    onSubmit(jdText);
  }

  return (
    <form onSubmit={handleSubmit} className="jd-form">
      <label htmlFor="jd-text">Job description</label>
      <textarea
        id="jd-text"
        value={jdText}
        onChange={(e) => setJdText(e.target.value)}
        placeholder="Paste the full job description here..."
        rows={10}
      />
      <Button
        type="submit"
        icon={<SparkleIcon width={16} height={16} />}
        loading={loading}
        disabled={jdText.trim().length < 20}
      >
        Analyze job description
      </Button>
    </form>
  );
}
