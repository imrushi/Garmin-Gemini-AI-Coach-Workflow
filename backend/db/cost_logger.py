import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from agents.model_router import ModelResponse
from db.model import AgentRun, get_session

logger = logging.getLogger(__name__)

# ── Cost lookup (per million tokens) ─────────────────────────────────────

_COST_TABLE: list[tuple[str, float, float]] = [
    ("claude-3-5-sonnet", 3.00, 15.00),
    ("claude-3-haiku", 0.25, 1.25),
    ("gemini-flash", 0.075, 0.30),
    ("llama", 0.00, 0.00),
    ("mistral", 0.00, 0.00),
]
_DEFAULT_INPUT_COST = 1.00
_DEFAULT_OUTPUT_COST = 3.00


def _estimate_cost(model_str: str, prompt_tokens: int, completion_tokens: int) -> float:
    model_lower = model_str.lower()
    input_cost = _DEFAULT_INPUT_COST
    output_cost = _DEFAULT_OUTPUT_COST
    for key, ic, oc in _COST_TABLE:
        if key in model_lower:
            input_cost, output_cost = ic, oc
            break
    return (prompt_tokens * input_cost + completion_tokens * output_cost) / 1_000_000


# ── Logging ──────────────────────────────────────────────────────────────

def log_agent_run(
    user_id: str | None,
    agent_type: str,
    response: ModelResponse,
    error: str | None = None,
) -> None:
    cost = _estimate_cost(response.model, response.prompt_tokens, response.completion_tokens)

    with get_session() as session:
        session.add(
            AgentRun(
                user_id=user_id,
                agent_type=agent_type,
                model_str=response.model,
                backend=response.backend,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                estimated_cost_usd=cost,
                latency_ms=response.latency_ms,
                success=error is None,
                error_message=error,
            )
        )

    logger.info(
        "agent_run agent_type=%s tokens=%d cost_usd=%.6f latency_ms=%d",
        agent_type,
        response.total_tokens,
        cost,
        response.latency_ms,
    )


# ── Summary ──────────────────────────────────────────────────────────────

def get_cost_summary(user_id: str, days: int = 7) -> dict:
    since = date.today() - timedelta(days=days)
    with get_session() as session:
        rows = session.execute(
            select(
                AgentRun.agent_type,
                func.count().label("runs"),
                func.sum(AgentRun.total_tokens).label("tokens"),
                func.sum(AgentRun.estimated_cost_usd).label("cost"),
            )
            .where(AgentRun.user_id == user_id, AgentRun.run_date >= since)
            .group_by(AgentRun.agent_type)
        ).all()

    total_runs = 0
    total_tokens = 0
    total_cost = 0.0
    by_agent: dict = {}

    for agent_type, runs, tokens, cost in rows:
        total_runs += runs
        total_tokens += tokens or 0
        total_cost += cost or 0.0
        by_agent[agent_type] = {
            "runs": runs,
            "tokens": tokens or 0,
            "cost_usd": round(cost or 0.0, 6),
        }

    return {
        "total_runs": total_runs,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "by_agent": by_agent,
    }
