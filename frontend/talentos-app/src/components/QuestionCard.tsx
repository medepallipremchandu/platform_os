import { useState } from "react";
import { runCode } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { toneForDifficulty, toneForQuestionType } from "../lib/tone";
import type { AnswerValue, Evaluation, Question, TestCaseResult } from "../types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import EvaluationResult from "./EvaluationResult";

interface Props {
  question: Question;
  value: AnswerValue;
  onChange: (value: AnswerValue) => void;
  result?: Evaluation;
}

export default function QuestionCard({ question, value, onChange, result }: Props) {
  const [running, setRunning] = useState<"sample" | "visible" | null>(null);
  const [runResults, setRunResults] = useState<TestCaseResult[] | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const totalWeight = question.rubric_maps.reduce((sum, m) => sum + m.weight_percentage, 0);
  const visibleTestCases = question.test_cases.filter((tc) => !tc.is_hidden);
  const hiddenCount = question.test_cases.length - visibleTestCases.length;

  async function handleRun(scope: "sample" | "visible") {
    if (!value.candidate_code?.trim()) return;
    setRunning(scope);
    setRunError(null);
    try {
      const results = await runCode(question.id, value.candidate_code, scope);
      setRunResults(results);
    } catch (err) {
      setRunError(extractErrorMessage(err));
    } finally {
      setRunning(null);
    }
  }

  return (
    <div className="question-card">
      <div className="question-card__header">
        <p className="question-card__text">{question.question_text}</p>
        <div className="question-card__badges">
          <Badge tone={toneForQuestionType(question.question_type)}>{question.question_type}</Badge>
          {question.difficulty && <Badge tone={toneForDifficulty(question.difficulty)}>{question.difficulty}</Badge>}
        </div>
      </div>

      <ul className="rubric-map-list">
        {question.rubric_maps.map((m) => (
          <li key={m.rubric_id}>
            <strong>{m.rubric_name}</strong> ({m.weight_percentage}%) - {m.evaluation_criteria}
          </li>
        ))}
      </ul>
      <p className="question-card__total-weight">Total rubric weight: {totalWeight}%</p>

      {question.question_type === "coding" && visibleTestCases.length > 0 && (
        <div className="test-case-preview">
          <h5>
            Sample test cases ({question.language})
            {hiddenCount > 0 && ` - plus ${hiddenCount} hidden test case${hiddenCount > 1 ? "s" : ""} used on submit`}
          </h5>
          <ul>
            {visibleTestCases.map((tc) => (
              <li key={tc.id}>
                <code>input: {tc.input || "(empty)"}</code>
                <code>expected: {tc.expected_output}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {question.question_type === "descriptive" && (
        <textarea
          placeholder="Paste or type the candidate's answer here..."
          value={value.candidate_answer || ""}
          onChange={(e) => onChange({ candidate_answer: e.target.value })}
          rows={4}
        />
      )}

      {question.question_type === "mcq" && (
        <div className="mcq-options">
          {(question.options || []).map((option, idx) => (
            <label key={idx} className="mcq-options__option">
              <input
                type="radio"
                name={`question-${question.id}`}
                checked={value.selected_option_index === idx}
                onChange={() => onChange({ selected_option_index: idx })}
              />
              {option}
            </label>
          ))}
        </div>
      )}

      {question.question_type === "coding" && (
        <div className="coding-answer">
          <textarea
            className="code-editor"
            value={value.candidate_code ?? question.starter_code ?? ""}
            onChange={(e) => onChange({ candidate_code: e.target.value })}
            rows={8}
            spellCheck={false}
          />
          <div className="coding-answer__run-buttons">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleRun("sample")}
              loading={running === "sample"}
              disabled={running !== null || !value.candidate_code?.trim()}
            >
              Run
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleRun("visible")}
              loading={running === "visible"}
              disabled={running !== null || !value.candidate_code?.trim()}
            >
              Run all testcases
            </Button>
          </div>
          {runError && <p className="error-text">{runError}</p>}
          {runResults && (
            <table className="test-case-table">
              <thead>
                <tr>
                  <th>Input</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {runResults.map((tc, i) => (
                  <tr key={i} className={tc.passed ? "test-case-table__pass" : "test-case-table__fail"}>
                    <td>
                      <code>{tc.input || "(empty)"}</code>
                    </td>
                    <td>
                      <code>{tc.expected_output}</code>
                    </td>
                    <td>
                      <code>{tc.stderr ? tc.stderr : tc.actual_output}</code>
                    </td>
                    <td>{tc.passed ? "Pass" : "Fail"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {result && <EvaluationResult evaluation={result} />}
    </div>
  );
}
