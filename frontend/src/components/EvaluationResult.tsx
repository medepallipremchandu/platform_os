import type { Evaluation } from "../types";
import Badge from "./ui/Badge";

interface Props {
  evaluation: Evaluation;
}

export default function EvaluationResult({ evaluation }: Props) {
  return (
    <div className="evaluation-result">
      <div className="evaluation-result__overall">
        <span>Overall score</span>
        <strong>{evaluation.overall_score_percentage}%</strong>
      </div>
      {evaluation.summary && <p className="evaluation-result__summary">{evaluation.summary}</p>}

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

      {evaluation.rubric_scores.length > 0 && (
        <ul className="rubric-score-list">
          {evaluation.rubric_scores.map((score) => (
            <li key={score.rubric_id} className="rubric-score-list__item">
              <div className="rubric-score-list__header">
                <span>{score.rubric_name}</span>
                <span>
                  {score.achieved_score_percentage}% of {score.expected_weight_percentage}% weight -&gt;{" "}
                  <strong>{score.weighted_contribution} pts</strong>
                </span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-bar__fill"
                  style={{ width: `${Math.min(score.achieved_score_percentage, 100)}%` }}
                />
              </div>
              {score.feedback && <p className="rubric-score-list__feedback">{score.feedback}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
