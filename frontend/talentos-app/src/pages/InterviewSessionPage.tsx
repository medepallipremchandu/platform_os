import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getInterviewSession, getQuestionsForSkill, submitBatchEvaluation } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import AnswerReview from "../components/AnswerReview";
import QuestionCard from "../components/QuestionCard";
import QuestionConfigPanel from "../components/QuestionConfigPanel";
import ScoreCard from "../components/ScoreCard";
import SkillCard from "../components/SkillCard";
import Tabs from "../components/Tabs";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import { CheckCircleIcon, DocumentIcon } from "../components/ui/icons";
import type {
  AnswerValue,
  BatchEvaluationResponse,
  InterviewSession,
  Question,
  QuestionGenerateResponse,
} from "../types";

function hasContent(question: Question, value: AnswerValue | undefined): boolean {
  if (!value) return false;
  if (question.question_type === "descriptive") return !!value.candidate_answer?.trim();
  if (question.question_type === "mcq") return value.selected_option_index !== undefined;
  return !!value.candidate_code?.trim();
}

type TabKey = "overview" | "skills" | "questions" | "score";

export default function InterviewSessionPage() {
  const { id } = useParams<{ id: string }>();

  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [questionsBySkill, setQuestionsBySkill] = useState<Record<string, Question[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({});
  const [batchResult, setBatchResult] = useState<BatchEvaluationResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getInterviewSession(id)
      .then(async (s) => {
        setSession(s);
        const entries = await Promise.all(
          s.skills.map(async (skill) => [skill.id, await getQuestionsForSkill(skill.id)] as const),
        );
        setQuestionsBySkill(Object.fromEntries(entries));
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  const allQuestions = Object.values(questionsBySkill).flat();
  const evaluationsByQuestionId = Object.fromEntries(
    (batchResult?.evaluations || []).map((e) => [e.question_id, e]),
  );
  const answeredCount = allQuestions.filter((q) => hasContent(q, answers[q.id])).length;

  function handleGenerated(results: QuestionGenerateResponse[]) {
    setQuestionsBySkill((prev) => {
      const next = { ...prev };
      for (const result of results) {
        next[result.skill_id] = [...(next[result.skill_id] || []), ...result.questions];
      }
      return next;
    });
  }

  async function handleFinalSubmit() {
    const payload = allQuestions
      .filter((q) => hasContent(q, answers[q.id]))
      .map((q) => ({ question_id: q.id, ...answers[q.id] }));
    if (payload.length === 0) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await submitBatchEvaluation(payload);
      setBatchResult(result);
      setActiveTab("score");
    } catch (err) {
      setSubmitError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <SkeletonCard />;
  if (error) return <p className="error-text">{error}</p>;
  if (!session) return null;

  return (
    <div className="jd-detail-page">
      <Tabs
        active={activeTab}
        onChange={(key) => setActiveTab(key as TabKey)}
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "skills", label: "Skills & rubrics" },
          { key: "questions", label: "Questions", badge: allQuestions.length },
          { key: "score", label: "Score card" },
        ]}
      />

      {activeTab === "overview" && (
        <Card>
          <div className="jd-detail-header">
            <div>
              <Badge tone="neutral" className="badge--jd-code">
                {session.submission_code}
              </Badge>
              <h2>{session.job_title || "Interview session"}</h2>
            </div>
          </div>
          <div className="audit-summary">
            <span>
              Candidate <strong>{session.candidate_name || "unknown"}</strong> ({session.resume_code}) -
              Requirement {session.jd_code}
            </span>
          </div>
          <p className="hint-text">
            Session created {formatDateTime(session.created_at)}. Skills/rubrics below are a snapshot taken
            from the submission's requirement at the time this session was created.
          </p>
        </Card>
      )}

      {activeTab === "skills" && (
        <>
          <Card title="Skills & rubrics">
            <div className="skill-list">
              {session.skills.map((skill) => (
                <SkillCard key={skill.id} skill={skill} />
              ))}
            </div>
          </Card>

          <Card title="Configure & generate questions">
            <QuestionConfigPanel skills={session.skills} onGenerated={handleGenerated} />
          </Card>
        </>
      )}

      {activeTab === "questions" && (
        <>
          {allQuestions.length === 0 && (
            <Card>
              <EmptyState
                icon={<DocumentIcon width={26} height={26} />}
                title="No questions generated yet"
                description='Go to "Skills & rubrics" to configure and generate some.'
              />
            </Card>
          )}

          {session.skills.map((skill) => {
            const questions = questionsBySkill[skill.id] || [];
            if (questions.length === 0) return null;
            return (
              <Card title={`${skill.name} - questions`} key={skill.id}>
                <div className="question-list">
                  {questions.map((q) => (
                    <QuestionCard
                      key={q.id}
                      question={q}
                      value={answers[q.id] || {}}
                      onChange={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
                      result={evaluationsByQuestionId[q.id]}
                    />
                  ))}
                </div>
              </Card>
            );
          })}

          {allQuestions.length > 0 && (
            <Card title="Final submit" className="final-submit-panel">
              <p className="hint-text">
                Submits every answered question above ({answeredCount}/{allQuestions.length} answered) using
                the code/answer currently entered, and produces the candidate's score card.
              </p>
              <Button
                icon={<CheckCircleIcon width={16} height={16} />}
                onClick={handleFinalSubmit}
                loading={submitting}
                disabled={answeredCount === 0}
              >
                Final submit
              </Button>
              {submitError && <p className="error-text">{submitError}</p>}
            </Card>
          )}
        </>
      )}

      {activeTab === "score" && (
        <Card title="Score card">
          {batchResult ? (
            <>
              <ScoreCard result={batchResult} />
              <h3 className="answer-review-heading">Answer review</h3>
              <div className="answer-review-list">
                {batchResult.evaluations.map((evaluation) => {
                  const question = allQuestions.find((q) => q.id === evaluation.question_id);
                  if (!question) return null;
                  return <AnswerReview key={evaluation.id} question={question} evaluation={evaluation} />;
                })}
              </div>
            </>
          ) : (
            <EmptyState
              icon={<CheckCircleIcon width={26} height={26} />}
              title="No submission yet"
              description='Answer questions in the "Questions" tab and use "Final submit" to see the score card here.'
            />
          )}
        </Card>
      )}
    </div>
  );
}
