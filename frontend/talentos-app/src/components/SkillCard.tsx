import type { Skill } from "../types";
import Badge from "./ui/Badge";

interface Props {
  skill: Skill;
}

export default function SkillCard({ skill }: Props) {
  const rubricWeightTotal = skill.rubrics.reduce((sum, r) => sum + r.weight_percentage, 0);

  return (
    <div className="skill-card">
      <div className="skill-card__header">
        <h3>{skill.name}</h3>
        <Badge tone="brand">{rubricWeightTotal}% weighted</Badge>
      </div>
      {skill.description && <p className="skill-card__description">{skill.description}</p>}

      <ul className="rubric-list">
        {skill.rubrics.map((rubric) => (
          <li key={rubric.id}>
            <div className="rubric-list__row">
              <strong>{rubric.name}</strong>
              <span>{rubric.weight_percentage}%</span>
            </div>
            {rubric.description && <p>{rubric.description}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
