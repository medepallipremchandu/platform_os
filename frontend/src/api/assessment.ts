import { assessmentClient } from "./client";
import type {
  AnswerValue,
  BatchEvaluationResponse,
  Evaluation,
  InterviewSession,
  InterviewSessionSummary,
  Question,
  QuestionGenerateConfig,
  QuestionGenerateResponse,
  RunCodeScope,
  TestCaseResult,
} from "../types";

// --- Interview sessions ---

export async function createOrGetInterviewSession(submissionId: string): Promise<InterviewSession> {
  const { data } = await assessmentClient.post<InterviewSession>("/interview-sessions", {
    submission_id: submissionId,
  });
  return data;
}

export async function listInterviewSessions(): Promise<InterviewSessionSummary[]> {
  const { data } = await assessmentClient.get<InterviewSessionSummary[]>("/interview-sessions");
  return data;
}

export async function getInterviewSession(id: string): Promise<InterviewSession> {
  const { data } = await assessmentClient.get<InterviewSession>(`/interview-sessions/${id}`);
  return data;
}

// --- Questions ---

export async function getQuestionsForSkill(skillId: string): Promise<Question[]> {
  const { data } = await assessmentClient.get<Question[]>(`/questions/${skillId}`);
  return data;
}

export async function generateQuestionsBatch(
  configs: QuestionGenerateConfig[],
): Promise<QuestionGenerateResponse[]> {
  const { data } = await assessmentClient.post<QuestionGenerateResponse[]>("/questions/generate-batch", {
    configs,
  });
  return data;
}

export async function runCode(questionId: string, code: string, scope: RunCodeScope): Promise<TestCaseResult[]> {
  const { data } = await assessmentClient.post<{ results: TestCaseResult[] }>(
    `/questions/${questionId}/run-code`,
    { code, scope },
  );
  return data.results;
}

// --- Evaluations ---

export async function submitEvaluation(questionId: string, answer: AnswerValue): Promise<Evaluation> {
  const { data } = await assessmentClient.post<Evaluation>("/evaluations", {
    question_id: questionId,
    ...answer,
  });
  return data;
}

export async function submitBatchEvaluation(
  answers: (AnswerValue & { question_id: string })[],
): Promise<BatchEvaluationResponse> {
  const { data } = await assessmentClient.post<BatchEvaluationResponse>("/evaluations/submit-batch", {
    answers,
  });
  return data;
}
