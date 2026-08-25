import { useState } from "react";
import { extractErrorMessage } from "../api/client";
import { updateRubric, updateSkill } from "../api/intake";
import type { Rubric, Skill } from "../types";
import Badge from "./ui/Badge";
import Button from "./ui/Button";
import { EditIcon } from "./ui/icons";

interface Props {
  skill: Skill;
  /** Both `jdId` and `canEdit` must be present for edit affordances to render - `jdId` is needed
   * to call the PATCH endpoints, `canEdit` reflects whether the session holds
   * `talentos.intake.requirements.write`. Read-only callers (e.g. InterviewSessionPage, which
   * shows a point-in-time snapshot of a submission's skills, not the live requirement) can omit
   * both and get the original read-only card. */
  jdId?: string;
  canEdit?: boolean;
  /** Called with the patched skill after a successful skill- or rubric-level save, so the parent
   * can update its own `jdAnalysis` state without a full page reload. */
  onSkillChange?: (updated: Skill) => void;
}

export default function SkillCard({ skill, jdId, canEdit = false, onSkillChange }: Props) {
  const canEditThis = canEdit && !!jdId;
  const rubricWeightTotal = skill.rubrics.reduce((sum, r) => sum + r.weight_percentage, 0);

  const [editingSkill, setEditingSkill] = useState(false);
  const [skillName, setSkillName] = useState(skill.name);
  const [skillDescription, setSkillDescription] = useState(skill.description || "");
  const [savingSkill, setSavingSkill] = useState(false);
  const [skillError, setSkillError] = useState<string | null>(null);

  const [editingRubricId, setEditingRubricId] = useState<string | null>(null);
  const [rubricDescription, setRubricDescription] = useState("");
  const [rubricWeight, setRubricWeight] = useState(0);
  const [savingRubric, setSavingRubric] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);

  function startEditSkill() {
    setSkillName(skill.name);
    setSkillDescription(skill.description || "");
    setSkillError(null);
    setEditingSkill(true);
  }

  async function handleSaveSkill() {
    if (!jdId) return;
    setSavingSkill(true);
    setSkillError(null);
    try {
      const updated = await updateSkill(jdId, skill.id, { name: skillName, description: skillDescription });
      onSkillChange?.(updated);
      setEditingSkill(false);
    } catch (err) {
      setSkillError(extractErrorMessage(err));
    } finally {
      setSavingSkill(false);
    }
  }

  function startEditRubric(rubric: Rubric) {
    setRubricDescription(rubric.description || "");
    setRubricWeight(rubric.weight_percentage);
    setRubricError(null);
    setEditingRubricId(rubric.id);
  }

  async function handleSaveRubric(rubric: Rubric) {
    if (!jdId) return;
    setSavingRubric(true);
    setRubricError(null);
    try {
      const updated = await updateRubric(jdId, rubric.id, {
        description: rubricDescription,
        weight_percentage: rubricWeight,
      });
      onSkillChange?.({
        ...skill,
        rubrics: skill.rubrics.map((r) => (r.id === updated.id ? updated : r)),
      });
      setEditingRubricId(null);
    } catch (err) {
      // The backend's 422 detail is already a human-readable sentence explaining exactly which
      // weight change would break the skill's ~100% invariant - surface it verbatim rather than
      // a generic "something went wrong".
      setRubricError(extractErrorMessage(err));
    } finally {
      setSavingRubric(false);
    }
  }

  return (
    <div className="skill-card">
      <div className="skill-card__header">
        <h3>{skill.name}</h3>
        <div className="skill-card__header-actions">
          <Badge tone="brand">{rubricWeightTotal}% weighted</Badge>
          {canEditThis && !editingSkill && (
            <Button
              variant="ghost"
              size="sm"
              icon={<EditIcon width={14} height={14} />}
              onClick={startEditSkill}
              aria-label="Edit skill"
            >
              Edit
            </Button>
          )}
        </div>
      </div>

      {editingSkill ? (
        <form
          className="jd-edit-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSaveSkill();
          }}
        >
          <label>
            Name
            <input value={skillName} onChange={(e) => setSkillName(e.target.value)} />
          </label>
          <label>
            Description
            <textarea value={skillDescription} onChange={(e) => setSkillDescription(e.target.value)} rows={2} />
          </label>
          {skillError && <p className="error-text">{skillError}</p>}
          <div className="jd-edit-form__actions">
            <Button type="submit" size="sm" loading={savingSkill}>
              Save changes
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => setEditingSkill(false)} disabled={savingSkill}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        skill.description && <p className="skill-card__description">{skill.description}</p>
      )}

      <ul className="rubric-list">
        {skill.rubrics.map((rubric) => (
          <li key={rubric.id}>
            {editingRubricId === rubric.id ? (
              <form
                className="rubric-edit-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSaveRubric(rubric);
                }}
              >
                <strong>{rubric.name}</strong>
                <label>
                  Description
                  <textarea value={rubricDescription} onChange={(e) => setRubricDescription(e.target.value)} rows={2} />
                </label>
                <label>
                  Weight %
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step="0.1"
                    value={rubricWeight}
                    onChange={(e) => setRubricWeight(Number(e.target.value))}
                  />
                </label>
                {rubricError && <p className="error-text">{rubricError}</p>}
                <div className="jd-edit-form__actions">
                  <Button type="submit" size="sm" loading={savingRubric}>
                    Save
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setEditingRubricId(null)}
                    disabled={savingRubric}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <>
                <div className="rubric-list__row">
                  <strong>{rubric.name}</strong>
                  <span className="rubric-list__row-actions">
                    {rubric.weight_percentage}%
                    {canEditThis && (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<EditIcon width={12} height={12} />}
                        onClick={() => startEditRubric(rubric)}
                        aria-label={`Edit ${rubric.name} rubric`}
                      />
                    )}
                  </span>
                </div>
                {rubric.description && <p>{rubric.description}</p>}
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
