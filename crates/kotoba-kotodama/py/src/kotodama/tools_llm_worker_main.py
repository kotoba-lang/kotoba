"""Generic-primitive worker for com.etzhayyim.tools.llm.* (ADR-2605082000 §2 follow-up).

Replaces per-actor pure-LLM py_primitive nodes (animeka_*.generate_*, etc.)
with a single data-resolved MCP tool. The underlying call routes to
``zeebe_worker_main.task_generic_llm_chat`` so caching, error handling,
and tier resolution stay in one place.

Wired into mcp_dispatch via ``register_overrides`` (the namespace is
``com.etzhayyim.tools.llm``, outside the per-actor convention).
"""

from __future__ import annotations

from typing import Any


_RESERVED_KWARGS = {
    "tier", "system", "user", "user_template", "maxTokens", "temperature",
    # MCP envelope passthrough
    "name", "headers",
}


async def task_llm_chat(
    *,
    tier: str = "fast",
    system: str = "",
    user: str = "",
    user_template: str = "",
    maxTokens: int = 400,
    temperature: float = 0.3,
    **template_vars: Any,
) -> dict[str, Any]:
    """Forward to ``task_generic_llm_chat`` with kwarg names matching the
    underlying primitive. Defer the import so unit tests can stub it.

    Phase E2 (ADR-2605082000): if ``user`` is empty and ``user_template``
    is provided, render ``user`` from the template using the remaining
    kwargs as substitution vars (Python ``str.format`` style). Lets
    LangGraph nodes feed state-derived strings into the prompt without
    a preceding transform.map step:

        config: {
          "input_paths": {"websiteUrl": "websiteUrl",
                          "industry":   "industry"},
          "args": {
            "name":          "com.etzhayyim.tools.llm.chat",
            "system":        "...",
            "user_template": "Analyze {websiteUrl} in {industry}. ..."
          }
        }

    Missing keys in the template render to empty strings (forgiving — the
    LLM can usually carry on with degraded context rather than failing).
    """
    if not user:
        if user_template:
            class _SafeDict(dict):
                def __missing__(self, key: str) -> str:
                    return ""
            try:
                user = user_template.format_map(_SafeDict(template_vars))
            except Exception:
                user = user_template
    if not user:
        return {"error": "user prompt required"}

    try:
        from kotodama.zeebe_worker_main import task_generic_llm_chat
    except Exception as exc:
        return {"error": f"task_generic_llm_chat unavailable: {exc}"}
    try:
        result = await task_generic_llm_chat(
            tier=tier, system=system, user=user,
            maxTokens=int(maxTokens), temperature=float(temperature),
        )
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"llm chat failed: {exc}"}
    if not isinstance(result, dict):
        return {"error": "unexpected non-dict result from task_generic_llm_chat"}
    return result
