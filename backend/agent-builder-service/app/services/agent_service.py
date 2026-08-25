import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidStateError, NotFoundError
from app.models.agent import Agent
from app.models.agent_credential import AgentCredential
from app.models.model import Model
from app.services import agent_credentials
from app.services.prompt_template import extract_variables

logger = logging.getLogger("app.services.agent")


def _next_agent_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('agent_code_seq')")).scalar_one()
    return f"AGT{seq_value:02d}"


def _as_uuid(value) -> uuid.UUID | None:
    """Callers are inconsistent about this: the API layer passes `actor.org_id` straight through
    as a string, while a row's organization_id comes back from SQLAlchemy as a UUID. Comparing
    the two with != is silently always True, which turns an isolation check into a blanket
    rejection - so normalize before comparing rather than trusting either side."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _assert_models_belong_to_org(db: Session, organization_id, *model_ids) -> None:
    """A model id arrives in the request body, so it must be checked against the caller's own
    organization before it is stored.

    Without this an agent could be bound to another tenant's model row - and since a model row
    carries that tenant's encrypted provider API key, invoking the agent would spend their
    quota against their credentials. The agent's own organization_id is taken from the token
    and was never the hole; the model reference was.

    Reported as a 404, not a 403: whether a model id exists in some other organization is
    itself information this caller is not entitled to."""
    expected = _as_uuid(organization_id)
    for model_id in model_ids:
        if model_id is None:
            continue
        model = db.get(Model, model_id)
        if model is None or _as_uuid(model.organization_id) != expected:
            raise NotFoundError(f"Model {model_id} not found")


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
    _assert_models_belong_to_org(db, organization_id, primary_model_id, fallback_model_id)
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
    if agent.is_archived:
        raise InvalidStateError("Archived agents are read-only - create a new agent instead")
    # Re-checked on edit as well as create: an agent legitimately owned by this organization can
    # still be re-pointed at another tenant's model, which is the same hole by a slower route.
    _assert_models_belong_to_org(
        db, agent.organization_id, updates.get("primary_model_id"), updates.get("fallback_model_id")
    )
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

    Archived agents can never be published: archive is meant to be a terminal, safe state
    (it revokes the invoke credential specifically so the agent stops working) - silently
    letting `/publish` flip status back to "published" (and mint a fresh credential, since the
    old one was just revoked) would make archiving trivially reversible and defeat the point
    of the soft-delete.
    """
    if agent.is_archived:
        raise InvalidStateError("Archived agents cannot be published - create a new agent instead")

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


def archive_agent(db: Session, agent: Agent, actor: str) -> Agent:
    """Soft-deletes an agent: flips status to 'archived' (the row is never removed - the
    invocation log and audit trail must survive) and revokes its active invoke credential in
    iam-service so it can no longer be exchanged for a new access token. Idempotent calls raise
    rather than silently no-op, so a double-click surfaces as a 422 the UI can ignore/disable
    against, not a false-success."""
    if agent.is_archived:
        raise InvalidStateError("Agent is already archived")

    for credential in agent.credentials:
        if credential.is_active:
            agent_credentials.revoke_service_principal(service_principal_id=credential.service_principal_id)
            credential.revoked_at = datetime.now(timezone.utc)

    agent.status = "archived"
    agent.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    logger.info("Agent %s (%s) archived by %s", agent.agent_code, agent.id, actor)
    return agent
