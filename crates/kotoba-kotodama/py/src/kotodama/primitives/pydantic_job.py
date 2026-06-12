"""Pydantic v2 L6 boundary validation (ADR-2605080200).

Provides base classes for LangServer job I/O validation, LangGraph BaseModel
state helpers, and Anthropic structured output contracts.

Usage:
    class GrowthProposalInput(ZeebeJobInput):
        actor_did: str
        trigger_signal: str
        eta_at_birth: float

    class GrowthProposalOutput(ZeebeJobOutput):
        proposed_did: str
        eta_score: float

    @worker.task(task_type="shinka.propose_growth")
    async def propose_growth(job: Job) -> dict:
        inp = GrowthProposalInput.from_job(job)
        ...
        return GrowthProposalOutput(proposed_did=did, eta_score=0.72).to_variables()
"""

from __future__ import annotations

import logging
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="ZeebeJobInput")


class ZeebeJobInput(BaseModel):
    """Base class for LangServer job input validation (L6 entry boundary).

    Subclass and declare fields with Pydantic v2 annotations.  Call
    ``from_job(job)`` to parse and validate ``job.variables``.
    """

    model_config = ConfigDict(
        extra="ignore",        # unknown Zeebe variables silently ignored
        populate_by_name=True,
        strict=False,
    )

    @classmethod
    def from_job(cls: Type[T], job: Any) -> T:
        """Parse job.variables dict into a validated input model.

        Raises ``pydantic.ValidationError`` on schema mismatch — LangServer
        will surface this as a BPMN incident, preserving the error details.
        """
        variables: dict[str, Any] = getattr(job, "variables", {}) or {}
        return cls.model_validate(variables)

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        return cls.model_validate(data)


class ZeebeJobOutput(BaseModel):
    """Base class for LangServer job output (L6 exit boundary).

    Returns typed output; ``to_variables()`` serialises to a plain dict
    suitable for return from a ``@worker.task`` handler.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )

    def to_variables(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)


# ---------------------------------------------------------------------------
# LangGraph state helpers
# ---------------------------------------------------------------------------

class BaseModelState(BaseModel):
    """Mixin for LangGraph graph state nodes.

    LangGraph requires state classes to be plain dicts or TypedDicts in its
    older API, but supports Pydantic BaseModel with the ``--allow-model-state``
    flag (langgraph >=0.2.0).  Subclass this alongside any StateGraph schema.

    Example:
        class ProposeState(BaseModelState):
            actor_did: str = ""
            eta_score: float = 0.0
            proposal_text: str = ""
            approved: bool = False
    """

    model_config = ConfigDict(
        extra="allow",         # LangGraph may inject additional keys
        populate_by_name=True,
    )

    def merge(self, updates: dict[str, Any]) -> "BaseModelState":
        """Return a new state with the given fields updated (immutable pattern)."""
        data = self.model_dump()
        data.update(updates)
        return self.__class__.model_validate(data)


# ---------------------------------------------------------------------------
# Anthropic structured output helpers
# ---------------------------------------------------------------------------

class AnthropicStructuredOutput(BaseModel):
    """Base class for Anthropic tool_use / json-mode structured output.

    Subclass and use with ``llm.structured_output(model_cls, messages)``.
    Provides ``from_tool_use`` to parse the ``input`` dict from an
    Anthropic ``ToolUseBlock``.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def from_tool_use(cls: Type[T], input_dict: dict[str, Any]) -> T:  # type: ignore[misc]
        return cls.model_validate(input_dict)

    @classmethod
    def safe_parse(
        cls: Type[T],
        input_dict: dict[str, Any],
        *,
        default: T | None = None,
    ) -> T | None:
        """Parse without raising; log validation errors and return default."""
        try:
            return cls.model_validate(input_dict)
        except ValidationError as exc:
            logger.warning("AnthropicStructuredOutput validation failed: %s", exc)
            return default
