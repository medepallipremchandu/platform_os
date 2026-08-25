import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import InvalidStateError, LLMProviderError, NotFoundError, RateLimitedError
from app.models.agent import Agent
from app.models.invocation_log import AgentInvocationLog
from app.models.model import Model
from app.services import crypto, prompt_template
from app.services.llm.llm_client import LLMClient, build_provider

logger = logging.getLogger("app.services.invoke")

_OUTPUT_PREVIEW_CHARS = 2000


def _get_agent_for_invoke(db: Session, agent_id: uuid.UUID) -> Agent:
    """Resolves the agent to invoke from the caller's verified `resource_scope` claim
    (see app/api/v1/invoke.py) - never from a path/body parameter."""
    agent = (
        db.query(Agent)
        .options(selectinload(Agent.primary_model), selectinload(Agent.fallback_model))
        .filter(Agent.id == agent_id)
        .first()
    )
    if agent is None:
        raise NotFoundError("Agent not found")
    if not agent.is_published:
        raise NotFoundError("Agent not found")
    return agent


def _check_rate_limit(db: Session, agent: Agent) -> None:
    window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
    count = db.scalar(
        select(func.count())
        .select_from(AgentInvocationLog)
        .where(AgentInvocationLog.agent_id == agent.id, AgentInvocationLog.created_at >= window_start)
    )
    if count >= agent.rate_limit_per_minute:
        raise RateLimitedError(
            f"Rate limit exceeded: {agent.rate_limit_per_minute} requests/minute for this agent"
        )


def _provider_for(model: Model, max_output_tokens: int):
    return build_provider(
        provider=model.provider,
        api_key=crypto.decrypt(model.api_key_encrypted),
        model_id=model.model_id,
        max_output_tokens=max_output_tokens,
        endpoint=model.endpoint,
        api_version=model.api_version,
    )


async def invoke_agent(db: Session, agent_id: uuid.UUID, variables: dict[str, str]) -> dict:
    agent = _get_agent_for_invoke(db, agent_id)
    _check_rate_limit(db, agent)

    missing = [v for v in agent.input_variables if v not in variables]
    if missing:
        raise InvalidStateError(f"Missing required variable(s): {', '.join(missing)}")

    providers = [_provider_for(agent.primary_model, agent.max_output_tokens)]
    if agent.fallback_model_id:
        providers.append(_provider_for(agent.fallback_model, agent.max_output_tokens))
    client = LLMClient(providers=providers, timeout_seconds=agent.timeout_seconds)

    system_prompt = prompt_template.render(agent.system_prompt, variables)
    user_prompt = prompt_template.render(agent.user_prompt_template, variables)

    start = time.perf_counter()
    try:
        result = await client.invoke(system_prompt, user_prompt)
        latency_ms = (time.perf_counter() - start) * 1000
        db.add(
            AgentInvocationLog(
                agent_id=agent.id,
                input_variables=variables,
                output_preview=result.raw_text[:_OUTPUT_PREVIEW_CHARS],
                provider_used=result.provider_used,
                success=True,
                latency_ms=latency_ms,
            )
        )
        db.commit()
        logger.info("Agent %s invoked via %s in %.0fms", agent.agent_code, result.provider_used, latency_ms)
        return {"output": result.output, "provider_used": result.provider_used}
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        db.add(
            AgentInvocationLog(
                agent_id=agent.id,
                input_variables=variables,
                success=False,
                error_message=str(exc)[:_OUTPUT_PREVIEW_CHARS],
                latency_ms=latency_ms,
            )
        )
        db.commit()
        logger.error("Agent %s invocation failed: %s", agent.agent_code, exc)
        raise LLMProviderError(str(exc)) from exc
