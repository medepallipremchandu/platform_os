import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidStateError
from app.models.agent import Agent
from app.models.agent_credential import AgentCredential
from app.services import agent_credentials
from app.services.prompt_template import extract_variables

logger = logging.getLogger("app.services.agent")


def _next_agent_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('agent_code_seq')")).scalar_one()
    return f"AGT{seq_value:02d}"


def create_agent(
    db: Session,
    name: str,
    description: str | None,
    system_prompt: str,
    user_prompt_template: str,
    primary_model_id,
    fallback_model_id,
    max_output_tokens: int,
    timeout_seconds: float,
    rate_limit_per_minute: int,
    actor: str,
    organization_id: uuid.UUID,
) -> Agent:
    agent = Agent(
        agent_code=_next_agent_code(db),
        organization_id=organization_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        input_variables=extract_variables(system_prompt, user_prompt_template),
        primary_model_id=primary_model_id,
        fallback_model_id=fallback_model_id,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        rate_limit_per_minute=rate_limit_per_minute,
        status="draft",
        created_by=actor,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    logger.info("Agent %s (%s) created by %s", agent.agent_code, agent.id, actor)
    return agent


_UPDATABLE_FIELDS = (
    "name",
    "description",
    "system_prompt",
    "user_prompt_template",
    "primary_model_id",
    "fallback_model_id",
    "max_output_tokens",
    "timeout_seconds",
    "rate_limit_per_minute",
)


def update_agent(db: Session, agent: Agent, updates: dict) -> Agent:
    for field in _UPDATABLE_FIELDS:
        if field in updates and updates[field] is not None:
            setattr(agent, field, updates[field])
    agent.input_variables = extract_variables(agent.system_prompt, agent.user_prompt_template)
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    return agent


def publish_agent(db: Session, agent: Agent, actor: str) -> tuple[Agent, str | None]:
    """Publishes the current draft. Returns (agent, plaintext_client_secret) -
    plaintext_client_secret is only non-None the first time a credential is issued;
    republishing an already-keyed agent doesn't rotate it (use regenerate_key for that).

    On first publish, mints a resource-bound ServicePrincipal in iam-service
    (design doc §6) using this service's own machine identity - never the publishing
    user's token.
    """
    plaintext_client_secret = None
    if not any(c.is_active for c in agent.credentials):
        response = agent_credentials.create_resource_bound_service_principal(
            agent_name=agent.name, organization_id=agent.organization_id, agent_id=agent.id
        )
        sp = response["service_principal"]
        plaintext_client_secret = response["client_secret"]
        db.add(
            AgentCredential(
                agent_id=agent.id,
                service_principal_id=sp["id"],
                client_id=sp["client_id"],
            )
        )
    agent.status = "published"
    agent.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    logger.info("Agent %s published by %s", agent.agent_code, actor)
    return agent, plaintext_client_secret


def regenerate_key(db: Session, agent: Agent) -> str:
    if not agent.is_published:
        raise InvalidStateError("Publish the agent before generating a credential")
    active = next((c for c in agent.credentials if c.is_active), None)
    if active is None:
        raise InvalidStateError("This agent has no active credential to rotate")
    return agent_credentials.rotate_service_principal_secret(service_principal_id=active.service_principal_id)
