import { useState } from "react";
import type { JDAnalysis } from "../types";
import Button from "./ui/Button";

interface Props {
  jdAnalysis: JDAnalysis;
  saving: boolean;
  onSave: (payload: { job_title: string; role_context: string; job_context_summary: string }) => void;
  onCancel: () => void;
}

export default function JDEditForm({ jdAnalysis, saving, onSave, onCancel }: Props) {
  const [jobTitle, setJobTitle] = useState(jdAnalysis.job_title || "");
  const [roleContext, setRoleContext] = useState(jdAnalysis.role_context || "");
  const [summary, setSummary] = useState(jdAnalysis.job_context_summary || "");

  return (
    <form
      className="jd-edit-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({ job_title: jobTitle, role_context: roleContext, job_context_summary: summary });
      }}
    >
      <label>
        Job title
        <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
      </label>
      <label>
        Role context
        <textarea value={roleContext} onChange={(e) => setRoleContext(e.target.value)} rows={3} />
      </label>
      <label>
        Job context summary
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={2} />
      </label>
      <div className="jd-edit-form__actions">
        <Button type="submit" loading={saving}>
          Save changes
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
