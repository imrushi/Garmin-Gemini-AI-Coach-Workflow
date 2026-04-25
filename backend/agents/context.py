import json
from datetime import date, datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select

from db.model import AgentContext, get_session


class ConversationContext(BaseModel):
    version: int = 1
    agent_type: str = ""
    user_id: str = ""
    date_range: str = ""
    compressed_summary: str = ""
    pinned_facts: dict = {}
    recent_readiness_scores: list[int] = []
    last_training_gate: str = ""
    model_used: str = ""
    total_tokens_used: int = 0
    created_at: str = ""

    def to_system_injection(self) -> str:
        facts_str = json.dumps(self.pinned_facts, indent=2)
        return (
            "[CONTEXT TRANSFER]\n"
            f"Prior agent: {self.agent_type} | Model: {self.model_used}\n"
            f"Period: {self.date_range}\n"
            f"Summary: {self.compressed_summary}\n"
            f"Key facts:\n{facts_str}\n"
            f"Recent readiness scores: {self.recent_readiness_scores}\n"
            f"Last training gate: {self.last_training_gate}\n"
            "Continue analysis maintaining consistency with the above context."
        )

    def to_db_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_db_json(cls, json_str: str) -> "ConversationContext":
        return cls.model_validate_json(json_str)


class AgentContextRepository:

    def save(self, ctx: ConversationContext) -> None:
        with get_session() as session:
            row = AgentContext(
                user_id=ctx.user_id,
                agent_type=ctx.agent_type,
                model_used=ctx.model_used,
                context_json=ctx.to_db_json(),
                token_count=ctx.total_tokens_used,
            )
            session.add(row)

    def load_latest(
        self, user_id: str, agent_type: str
    ) -> ConversationContext | None:
        with get_session() as session:
            row = session.execute(
                select(AgentContext)
                .where(
                    AgentContext.user_id == user_id,
                    AgentContext.agent_type == agent_type,
                )
                .order_by(AgentContext.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            return ConversationContext.from_db_json(row.context_json)

    def exists(self, user_id: str, agent_type: str) -> bool:
        with get_session() as session:
            row = session.execute(
                select(AgentContext.id)
                .where(
                    AgentContext.user_id == user_id,
                    AgentContext.agent_type == agent_type,
                )
                .limit(1)
            ).scalar_one_or_none()
            return row is not None
