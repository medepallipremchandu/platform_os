import { intakeClient } from "./client";
import type {
  AuditLogEntry,
  JDAnalysis,
  JDAnalysisSummary,
  JDAnalysisUpdateRequest,
  ResumeAnalysis,
  ResumeAnalysisSummary,
  Submission,
  SubmissionSummary,
} from "../types";

// --- JD analysis ---

export async function listJDAnalyses(): Promise<JDAnalysisSummary[]> {
  const { data } = await intakeClient.get<JDAnalysisSummary[]>("/jd-analysis");
  return data;
}

export async function analyzeJD(jdText: string): Promise<JDAnalysis> {
  const { data } = await intakeClient.post<JDAnalysis>("/jd-analysis", { jd_text: jdText });
  return data;
}

export async function getJDAnalysis(id: string): Promise<JDAnalysis> {
  const { data } = await intakeClient.get<JDAnalysis>(`/jd-analysis/${id}`);
  return data;
}

export async function updateJDAnalysis(id: string, payload: JDAnalysisUpdateRequest): Promise<JDAnalysis> {
  const { data } = await intakeClient.patch<JDAnalysis>(`/jd-analysis/${id}`, payload);
  return data;
}

export async function deleteJDAnalysis(id: string): Promise<JDAnalysis> {
  const { data } = await intakeClient.delete<JDAnalysis>(`/jd-analysis/${id}`);
  return data;
}

export async function getJDAuditLog(id: string): Promise<AuditLogEntry[]> {
  const { data } = await intakeClient.get<AuditLogEntry[]>(`/jd-analysis/${id}/audit-log`);
  return data;
}

// --- Resume analysis ---

export async function listResumeAnalyses(): Promise<ResumeAnalysisSummary[]> {
  const { data } = await intakeClient.get<ResumeAnalysisSummary[]>("/resume-analysis");
  return data;
}

export async function analyzeResume(file: File): Promise<ResumeAnalysis> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await intakeClient.post<ResumeAnalysis>("/resume-analysis", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getResumeAnalysis(id: string): Promise<ResumeAnalysis> {
  const { data } = await intakeClient.get<ResumeAnalysis>(`/resume-analysis/${id}`);
  return data;
}

export async function deleteResumeAnalysis(id: string): Promise<ResumeAnalysis> {
  const { data } = await intakeClient.delete<ResumeAnalysis>(`/resume-analysis/${id}`);
  return data;
}

export async function getResumeAuditLog(id: string): Promise<AuditLogEntry[]> {
  const { data } = await intakeClient.get<AuditLogEntry[]>(`/resume-analysis/${id}/audit-log`);
  return data;
}

// --- Submissions & matching ---

export async function listSubmissions(): Promise<SubmissionSummary[]> {
  const { data } = await intakeClient.get<SubmissionSummary[]>("/submissions");
  return data;
}

export async function createSubmission(jdAnalysisId: string, resumeAnalysisId: string): Promise<Submission> {
  const { data } = await intakeClient.post<Submission>("/submissions", {
    jd_analysis_id: jdAnalysisId,
    resume_analysis_id: resumeAnalysisId,
  });
  return data;
}

export async function getSubmission(id: string): Promise<Submission> {
  const { data } = await intakeClient.get<Submission>(`/submissions/${id}`);
  return data;
}

export async function deleteSubmission(id: string): Promise<Submission> {
  const { data } = await intakeClient.delete<Submission>(`/submissions/${id}`);
  return data;
}

export async function getSubmissionAuditLog(id: string): Promise<AuditLogEntry[]> {
  const { data } = await intakeClient.get<AuditLogEntry[]>(`/submissions/${id}/audit-log`);
  return data;
}
