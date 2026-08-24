import { toneForScore } from "../lib/tone";
import type { BatchEvaluationResponse } from "../types";
import Badge from "./ui/Badge";

interface Props {
  result: BatchEvaluationResponse;
}

export default function ScoreCard({ result }: Props) {
  return (
    <div className="score-card">
      <div className="score-card__overall">
        <span>Overall score</span>
        <Badge tone={toneForScore(result.overall_score_percentage)} className="score-card__overall-badge">
          {result.overall_score_percentage}%
        </Badge>
      </div>
      <table className="score-card__table">
        <thead>
          <tr>
            <th>Skill</th>
            <th>Questions answered</th>
            <th>Average score</th>
          </tr>
        </thead>
        <tbody>
          {result.skill_scores.map((s) => (
            <tr key={s.skill_id}>
              <td>{s.skill_name}</td>
              <td>{s.question_count}</td>
              <td>
                <Badge tone={toneForScore(s.average_score_percentage)}>{s.average_score_percentage}%</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
