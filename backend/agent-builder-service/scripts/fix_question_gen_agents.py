"""One-off fix: the initial seed used str.format() on templates that already contained
{{double-brace}} placeholders, which silently collapsed them to {single-brace} and broke
templating for the 3 question-generation agents. This patches their user_prompt_template
in place (same agent_code, same API key - no re-publish needed).

Usage (from agent-builder-service/):
    .venv/Scripts/python.exe scripts/fix_question_gen_agents.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.services.agent_service import update_agent  # noqa: E402
from scripts.seed_models_and_agents import AGENTS  # noqa: E402

TARGET_NAMES = {
    "Question Generation Agent - Descriptive",
    "Question Generation Agent - MCQ",
    "Question Generation Agent - Coding",
}


def main() -> None:
    db = SessionLocal()
    try:
        specs_by_name = {spec["name"]: spec for spec in AGENTS if spec["name"] in TARGET_NAMES}
        for name, spec in specs_by_name.items():
            agent = db.query(Agent).filter(Agent.name == name).first()
            if agent is None:
                print(f"SKIP (not found): {name}")
                continue
            update_agent(db, agent, {"user_prompt_template": spec["user_prompt_template"]})
            print(f"Fixed {agent.agent_code} ({name}) - input_variables now: {agent.input_variables}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
