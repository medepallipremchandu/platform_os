import { intakeClient } from "./client";
import type {
  AnswerValue,
  AuditLogEntry,
  BatchEvaluationResponse,
  Evaluation,
  InterviewSession,
  InterviewSessionSummary,
  JDAnalysis,
  JDAnalysisSummary,
  JDAnalysisUpdateRequest,
  Question,
  QuestionGenerateConfig,
  QuestionGenerateResponse,
  ResumeAnalysis,
  ResumeAnalysisSummary,
  ResumeAnalysisUpdateRequest,
  Rubric,
  RubricUpdateRequest,
  RunCodeScope,
  Skill,
  SkillUpdateRequest,
  Submission,
  SubmissionSummary,
  TestCaseResult,
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

export async function updateSkill(jdId: string, skillId: string, payload: SkillUpdateRequest): Promise<Skill> {
  const { data } = await intakeClient.patch<Skill>(`/jd-analysis/${jdId}/skills/${skillId}`, payload);
  return data;
}

export async function updateRubric(jdId: string, rubricId: string, payload: RubricUpdateRequest): Promise<Rubric> {
  const { data } = await intakeClient.patch<Rubric>(`/jd-analysis/${jdId}/rubrics/${rubricId}`, payload);
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

export async function updateResumeAnalysis(id: string, payload: ResumeAnalysisUpdateRequest): Promise<ResumeAnalysis> {
  const { data } = await intakeClient.patch<ResumeAnalysis>(`/resume-analysis/${id}`, payload);
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

// --- Interview sessions ---

export async function createOrGetInterviewSession(submissionId: string): Promise<InterviewSession> {
  const { data } = await intakeClient.post<InterviewSession>("/interview-sessions", {
    submission_id: submissionId,
  });
  return data;
}

export async function listInterviewSessions(): Promise<InterviewSessionSummary[]> {
  const { data } = await intakeClient.get<InterviewSessionSummary[]>("/interview-sessions");
  return data;
}

export async function getInterviewSession(id: string): Promise<InterviewSession> {
  const { data } = await intakeClient.get<InterviewSession>(`/interview-sessions/${id}`);
  return data;
}

// --- Questions ---

export async function getQuestionsForSkill(skillId: string): Promise<Question[]> {
  const { data } = await intakeClient.get<Question[]>(`/questions/${skillId}`);
  return data;
}

export async function generateQuestionsBatch(
  configs: QuestionGenerateConfig[],
): Promise<QuestionGenerateResponse[]> {
  const { data } = await intakeClient.post<QuestionGenerateResponse[]>("/questions/generate-batch", {
    configs,
  });
  return data;
}

export async function runCode(questionId: string, code: string, scope: RunCodeScope): Promise<TestCaseResult[]> {
  const { data } = await intakeClient.post<{ results: TestCaseResult[] }>(
    `/questions/${questionId}/run-code`,
    { code, scope },
  );
  return data.results;
}

// --- Evaluations ---

export async function submitEvaluation(questionId: string, answer: AnswerValue): Promise<Evaluation> {
  const { data } = await intakeClient.post<Evaluation>("/evaluations", {
    question_id: questionId,
    ...answer,
  });
  return data;
}

export async function submitBatchEvaluation(
  answers: (AnswerValue & { question_id: string })[],
): Promise<BatchEvaluationResponse> {
  const { data } = await intakeClient.post<BatchEvaluationResponse>("/evaluations/submit-batch", {
    answers,
  });
  return data;
}
