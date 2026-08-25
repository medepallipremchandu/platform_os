import { useState } from "react";
import { generateQuestionsBatch } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import type { QuestionGenerateConfig, QuestionGenerateResponse, QuestionType, Skill } from "../types";
import Button from "./ui/Button";
import { SparkleIcon } from "./ui/icons";

interface RowState {
  include: boolean;
  numQuestions: number;
  questionType: QuestionType;
}

interface Props {
  skills: Skill[];
  onGenerated: (results: QuestionGenerateResponse[]) => void;
}

const QUESTION_TYPES: { value: QuestionType; label: string }[] = [
  { value: "descriptive", label: "Descriptive" },
  { value: "mcq", label: "Multiple choice" },
  { value: "coding", label: "Coding" },
];

export default function QuestionConfigPanel({ skills, onGenerated }: Props) {
  const [rows, setRows] = useState<Record<string, RowState>>(() =>
    Object.fromEntries(
      skills.map((s) => [s.id, { include: false, numQuestions: 2, questionType: "descriptive" as QuestionType }]),
    ),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateRow(skillId: string, patch: Partial<RowState>) {
    setRows((prev) => ({ ...prev, [skillId]: { ...prev[skillId], ...patch } }));
  }

  const includedCount = Object.values(rows).filter((r) => r.include).length;

  async function handleGenerate() {
    const configs: QuestionGenerateConfig[] = Object.entries(rows)
      .filter(([, row]) => row.include)
      .map(([skillId, row]) => ({
        skill_id: skillId,
        num_questions: row.numQuestions,
        question_type: row.questionType,
      }));
    if (configs.length === 0) return;

    setLoading(true);
    setError(null);
    try {
      const results = await generateQuestionsBatch(configs);
      onGenerated(results);
      setRows((prev) => {
        const next = { ...prev };
        for (const c of configs) next[c.skill_id] = { ...next[c.skill_id], include: false };
        return next;
      });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="question-config-panel">
      <table className="config-table">
        <thead>
          <tr>
            <th></th>
            <th>Skill</th>
            <th>Questions</th>
            <th>Type</th>
          </tr>
        </thead>
        <tbody>
          {skills.map((skill) => {
            const row = rows[skill.id];
            return (
              <tr key={skill.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={row.include}
                    onChange={(e) => updateRow(skill.id, { include: e.target.checked })}
                  />
                </td>
                <td>{skill.name}</td>
                <td>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={row.numQuestions}
                    disabled={!row.include}
                    onChange={(e) => updateRow(skill.id, { numQuestions: Number(e.target.value) })}
                  />
                </td>
                <td>
                  <select
                    value={row.questionType}
                    disabled={!row.include}
                    onChange={(e) => updateRow(skill.id, { questionType: e.target.value as QuestionType })}
                  >
                    {QUESTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Button
        icon={<SparkleIcon width={16} height={16} />}
        onClick={handleGenerate}
        loading={loading}
        disabled={includedCount === 0}
      >
        Generate questions{includedCount ? ` (${includedCount} skill${includedCount > 1 ? "s" : ""})` : ""}
      </Button>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
