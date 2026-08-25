import { useState } from "react";
import type { ResumeAnalysis, ResumeAnalysisUpdateRequest } from "../types";
import Button from "./ui/Button";

interface Props {
  resume: ResumeAnalysis;
  saving: boolean;
  onSave: (payload: ResumeAnalysisUpdateRequest) => void;
  onCancel: () => void;
}

/** Mirrors JDEditForm's inline-edit-form pattern (same label/input layout, same
 * .jd-edit-form/.jd-edit-form__actions classes) for correcting a candidate's extracted profile
 * fields via PATCH /resume-analysis/{id}. */
export default function ResumeEditForm({ resume, saving, onSave, onCancel }: Props) {
  const [candidateName, setCandidateName] = useState(resume.candidate_name || "");
  const [candidateEmail, setCandidateEmail] = useState(resume.candidate_email || "");
  const [candidatePhone, setCandidatePhone] = useState(resume.candidate_phone || "");
  const [experienceYears, setExperienceYears] = useState(
    resume.total_experience_years != null ? String(resume.total_experience_years) : "",
  );
  const [summary, setSummary] = useState(resume.summary || "");

  return (
    <form
      className="jd-edit-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSave({
          candidate_name: candidateName,
          candidate_email: candidateEmail,
          candidate_phone: candidatePhone,
          total_experience_years: experienceYears === "" ? undefined : Number(experienceYears),
          summary,
        });
      }}
    >
      <label>
        Candidate name
        <input value={candidateName} onChange={(e) => setCandidateName(e.target.value)} />
      </label>
      <label>
        Candidate email
        <input type="email" value={candidateEmail} onChange={(e) => setCandidateEmail(e.target.value)} />
      </label>
      <label>
        Candidate phone
        <input value={candidatePhone} onChange={(e) => setCandidatePhone(e.target.value)} />
      </label>
      <label>
        Total experience (years)
        <input
          type="number"
          min={0}
          step="0.5"
          value={experienceYears}
          onChange={(e) => setExperienceYears(e.target.value)}
        />
      </label>
      <label>
        Summary
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={3} />
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
