import { toneForScore, toneForVerdict } from "../lib/tone";
import type { MatchAnalysis } from "../types";
import Badge from "./ui/Badge";

interface Props {
  match: MatchAnalysis;
}

const VERDICT_OPTION_CLASS: Record<string, string> = {
  success: "answer-review__option--correct",
  danger: "answer-review__option--incorrect",
};

export default function MatchAnalysisCard({ match }: Props) {
  return (
    <div className="match-analysis">
      <div className="score-card__overall">
        <span>Overall match</span>
        <Badge tone={toneForScore(match.overall_match_percentage)} className="score-card__overall-badge">
          {match.overall_match_percentage}%
        </Badge>
      </div>

      <ul className="answer-review__options">
        {match.skill_matches.map((sm, i) => {
          const tone = toneForVerdict(sm.verdict);
          const optionClass = VERDICT_OPTION_CLASS[tone] || "";
          return (
            <li key={i} className={`answer-review__option ${optionClass}`}>
              <div>
                <strong>{sm.skill_name}</strong> ({sm.jd_weight_percentage}% weight) - {sm.match_percentage}% -{" "}
                {sm.verdict}
                <p className="rubric-score-list__feedback">
                  Required: {sm.required_level}. Evidence: {sm.candidate_evidence}
                </p>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="context-block">
        <h4>Strengths</h4>
        <ul>
          {match.strengths.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      </div>
      {match.gaps.length > 0 && (
        <div className="context-block">
          <h4>Gaps</h4>
          <ul>
            {match.gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}
      {match.market_context_commentary && (
        <div className="context-block">
          <h4>Market context</h4>
          <p>{match.market_context_commentary}</p>
        </div>
      )}
      {match.recommendation && (
        <div className="context-block">
          <h4>Recommendation</h4>
          <p>{match.recommendation}</p>
        </div>
      )}
    </div>
  );
}
