export interface Rubric {
  id: string;
  name: string;
  description: string | null;
  weight_percentage: number;
}

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  rubrics: Rubric[];
}

export interface JDAnalysis {
  id: string;
  jd_code: string;
  job_title: string | null;
  role_context: string | null;
  job_context_summary: string | null;
  responsibilities: string[];
  qualifications: string[];
  skills: Skill[];
  created_by: string | null;
  created_at: string;
  modified_by: string | null;
  modified_at: string | null;
  deleted_by: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
}

export interface JDAnalysisSummary {
  id: string;
  jd_code: string;
  job_title: string | null;
  skills_count: number;
  created_by: string | null;
  created_at: string;
  modified_by: string | null;
  modified_at: string | null;
  is_deleted: boolean;
}

export interface JDAnalysisUpdateRequest {
  job_title?: string;
  role_context?: string;
  job_context_summary?: string;
  responsibilities?: string[];
  qualifications?: string[];
}

export interface AuditLogEntry {
  id: string;
  action: "created" | "updated" | "deleted";
  changed_by: string;
  changes: Record<string, { old: unknown; new: unknown }> | null;
  changed_at: string;
}

export type QuestionType = "descriptive" | "mcq" | "coding";

export interface RubricMap {
  rubric_id: string;
  rubric_name: string;
  weight_percentage: number;
  evaluation_criteria: string;
}

export interface QuestionTestCase {
  id: string;
  input: string;
  expected_output: string;
  is_hidden: boolean;
}

export interface Question {
  id: string;
  question_type: QuestionType;
  question_text: string;
  difficulty: string | null;
  created_at: string;
  rubric_maps: RubricMap[];
  options: string[] | null;
  correct_option_index: number | null;
  language: string | null;
  starter_code: string | null;
  test_cases: QuestionTestCase[];
}

export interface QuestionGenerateResponse {
  skill_id: string;
  skill_name: string;
  questions: Question[];
}

export interface QuestionGenerateConfig {
  skill_id: string;
  num_questions: number;
  question_type: QuestionType;
}

export interface RubricScore {
  rubric_id: string;
  rubric_name: string;
  expected_weight_percentage: number;
  achieved_score_percentage: number;
  weighted_contribution: number;
  feedback: string | null;
}

export interface TestCaseResult {
  input: string;
  expected_output: string;
  actual_output: string;
  passed: boolean;
  is_hidden: boolean;
  stderr: string | null;
  execution_time_ms: number | null;
}

export interface Evaluation {
  id: string;
  question_id: string;
  candidate_answer: string | null;
  selected_option_index: number | null;
  candidate_code: string | null;
  overall_score_percentage: number;
  summary: string | null;
  rubric_scores: RubricScore[];
  test_case_results: TestCaseResult[];
  created_at: string;
}

export interface AnswerValue {
  candidate_answer?: string;
  selected_option_index?: number;
  candidate_code?: string;
}

export type RunCodeScope = "sample" | "visible";

export interface SkillScore {
  skill_id: string;
  skill_name: string;
  average_score_percentage: number;
  question_count: number;
}

export interface BatchEvaluationResponse {
  overall_score_percentage: number;
  evaluations: Evaluation[];
  skill_scores: SkillScore[];
}

export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

// --- Resume analysis (intake-matching-service) ---

export interface ResumeSkill {
  name: string;
  years_experience: number | null;
  proficiency: string | null;
}

export interface WorkHistoryItem {
  company: string;
  title: string;
  start_date: string | null;
  end_date: string | null;
  description: string;
}

export interface EducationItem {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  graduation_year: string | null;
}

export interface ResumeAnalysis {
  id: string;
  resume_code: string;
  original_filename: string;
  file_type: string;
  candidate_name: string | null;
  candidate_email: string | null;
  candidate_phone: string | null;
  total_experience_years: number | null;
  summary: string | null;
  skills: ResumeSkill[];
  work_history: WorkHistoryItem[];
  education: EducationItem[];
  certifications: string[];
  created_by: string | null;
  created_at: string;
  modified_by: string | null;
  modified_at: string | null;
  deleted_by: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
}

export interface ResumeAnalysisSummary {
  id: string;
  resume_code: string;
  candidate_name: string | null;
  total_experience_years: number | null;
  created_by: string | null;
  created_at: string;
  modified_by: string | null;
  modified_at: string | null;
  is_deleted: boolean;
}

// --- Submissions & matching (intake-matching-service) ---

export interface SkillMatch {
  skill_name: string;
  jd_weight_percentage: number;
  required_level: string;
  candidate_evidence: string;
  match_percentage: number;
  verdict: string;
}

export interface MatchAnalysis {
  overall_match_percentage: number;
  skill_matches: SkillMatch[];
  strengths: string[];
  gaps: string[];
  market_context_commentary: string | null;
  recommendation: string | null;
  created_at: string;
}

export interface Submission {
  id: string;
  submission_code: string;
  jd_analysis_id: string;
  resume_analysis_id: string;
  match_analysis: MatchAnalysis | null;
  created_by: string | null;
  created_at: string;
  modified_by: string | null;
  modified_at: string | null;
  deleted_by: string | null;
  deleted_at: string | null;
  is_deleted: boolean;
}

export interface SubmissionSummary {
  id: string;
  submission_code: string;
  jd_code: string;
  job_title: string | null;
  resume_code: string;
  candidate_name: string | null;
  overall_match_percentage: number | null;
  created_by: string | null;
  created_at: string;
  is_deleted: boolean;
}

// --- Interview sessions (assessment-service) ---

export interface InterviewSession {
  id: string;
  submission_id: string;
  submission_code: string;
  jd_code: string;
  job_title: string | null;
  resume_code: string;
  candidate_name: string | null;
  skills: Skill[];
  created_at: string;
}

export interface InterviewSessionSummary {
  id: string;
  submission_id: string;
  submission_code: string;
  jd_code: string;
  job_title: string | null;
  resume_code: string;
  candidate_name: string | null;
  created_at: string;
}
