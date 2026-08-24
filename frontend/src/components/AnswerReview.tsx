import { toneForQuestionType } from "../lib/tone";
import type { Evaluation, Question } from "../types";
import Badge from "./ui/Badge";

interface Props {
  question: Question;
  evaluation: Evaluation;
}

export default function AnswerReview({ question, evaluation }: Props) {
  return (
    <div className="answer-review">
      <div className="answer-review__header">
        <p className="answer-review__question">{question.question_text}</p>
        <Badge tone={toneForQuestionType(question.question_type)}>{question.question_type}</Badge>
      </div>

      {question.question_type === "mcq" && question.options && (
        <ul className="answer-review__options">
          {question.options.map((option, idx) => {
            const isCorrect = idx === question.correct_option_index;
            const isSelected = idx === evaluation.selected_option_index;
            const cls = isCorrect
              ? "answer-review__option answer-review__option--correct"
              : isSelected
                ? "answer-review__option answer-review__option--incorrect"
                : "answer-review__option";
            return (
              <li key={idx} className={cls}>
                <span>{option}</span>
                {isSelected && <span className="answer-review__tag">Candidate's answer</span>}
                {isCorrect && <span className="answer-review__tag">Correct answer</span>}
              </li>
            );
          })}
        </ul>
      )}

      {question.question_type === "descriptive" && evaluation.candidate_answer && (
        <div className="answer-review__text-answer">
          <h5>Candidate's answer</h5>
          <p>{evaluation.candidate_answer}</p>
        </div>
      )}

      {question.question_type === "coding" && evaluation.candidate_code && (
        <div className="answer-review__text-answer">
          <h5>Candidate's code</h5>
          <pre className="code-editor">{evaluation.candidate_code}</pre>
        </div>
      )}

      {evaluation.test_case_results.length > 0 && (
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
            {evaluation.test_case_results.map((tc, i) => (
              <tr key={i} className={tc.passed ? "test-case-table__pass" : "test-case-table__fail"}>
                <td>
                  <code>{tc.input || "(empty)"}</code>
                  {tc.is_hidden && <Badge tone="info" className="test-case-table__hidden-badge">hidden</Badge>}
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

      <div className="answer-review__score">
        <span>Score</span>
        <strong>{evaluation.overall_score_percentage}%</strong>
      </div>
      {evaluation.summary && <p className="answer-review__summary">{evaluation.summary}</p>}
    </div>
  );
}
