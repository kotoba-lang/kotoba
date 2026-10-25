"""kotoba — Hermes tools for the kotoba-lang authorities.

Three questions an agent answers wrong from memory, and one tool each:

  kotoba_surface_status   is this refusal permanent, or a backend that has
                          not caught up? (they arrive as the same message)
  kotoba_capability_kits  which backends have qualified this capability?
                          (the key set differs per kit; grep truncates)
  kotoba_check            did the compiler admit this guest? (and a standing
                          reminder that admitted is not run)

## Why the plugin decides nothing

The reasoning lives in `read_authority.cljk`, beside the data and in the same
language. An EDN reader written here in Python would be a second reader: two
answers that agree until the day they do not, with no test that would notice.
This is the shape `plugins/dashboard_auth/did` established in this workspace
(ADR-2608197300 sections 3 and 5) -- the plugin language is dictated by the
host, and a file that holds no decision costs nothing by being in it.

## Why it registers nothing without a workspace

`available()` gates dispatch on a real checkout and a real `nbb`. A tool that
answered "not found" from an unconfigured machine would be reporting an
unread authority as an absent feature, which is precisely the confusion the
tools exist to prevent.
"""

from __future__ import annotations

from plugins.kotoba.tools import (
    CAPABILITY_KITS_SCHEMA,
    CHECK_SCHEMA,
    SURFACE_STATUS_SCHEMA,
    available,
    handle_capability_kits,
    handle_check,
    handle_surface_status,
)

_TOOLS = (
    ("kotoba_surface_status", SURFACE_STATUS_SCHEMA, handle_surface_status, "🚧"),
    ("kotoba_capability_kits", CAPABILITY_KITS_SCHEMA, handle_capability_kits, "🧩"),
    ("kotoba_check", CHECK_SCHEMA, handle_check, "✅"),
)


def register(ctx) -> None:
    """Register the kotoba tools. Called once by the Hermes plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="kotoba",
            schema=schema,
            handler=handler,
            check_fn=available,
            emoji=emoji,
        )
