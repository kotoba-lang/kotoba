"""
Yorishiro: example-portal (kami: browser:example-portal)
Generator: @etzhayyim/yorishiro v0.1.0 (browser-only mode)
Per ADR-2605211900 + ADR-2605202200.

Transport: browser-only
Base URL : https://example.com
Charter purposes: grant

The cell spawns Playwright's sync_api per invocation, replays the
manifest's step sequence, and extracts text/attributes per the manifest.
The browser binary must be installed on the cell runtime:

    pip install playwright
    playwright install chromium

Hand edits are overwritten by `yorishiro regen example-portal`. Extend the
kami manifest instead.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "example-portal"
YORISHIRO_KAMI = "browser:example-portal"
YORISHIRO_BASE_URL = "https://example.com"
YORISHIRO_PURPOSES = tuple(["grant"])


class ExamplePortalState(TypedDict, total=False):
    op: str
    input: dict[str, Any]
    ok: bool
    extracted: dict[str, Any]
    error: str


def _ensure_playwright() -> tuple[Any, Any] | tuple[None, str]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        return None, "playwright not installed (pip install playwright && playwright install chromium)"
    return sync_playwright, None  # type: ignore[return-value]


def read_heading_node(state: dict[str, Any]) -> dict[str, Any]:
    """Navigates to the kami's base URL, waits for the H1 to render, and extracts its textContent. Exists as the minimum L1 demonstration for browser-only mode."""
    inp = dict(state.get("input") or {})
    pw_factory, err = _ensure_playwright()
    if pw_factory is None:
        return {**state, "ok": False, "error": err or "playwright unavailable"}
    extracted: dict[str, Any] = {}
    try:
        with pw_factory() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context()
                page = ctx.new_page()
                page.goto("https://example.com/")
                page.wait_for_selector("h1", timeout=5000)
                extracted["heading"] = page.locator("h1").first.text_content()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — browser failures surface to state.error
        return {**state, "ok": False, "extracted": extracted, "error": str(exc)}
    return {**state, "ok": True, "extracted": extracted}

def search_term_node(state: dict[str, Any]) -> dict[str, Any]:
    """Hypothetical flow exercising fill + click + scroll + multi-extract — the page itself does NOT have a real search box, but the kami manifest is shaped this way to validate the L1 emitter's required-input derivation."""
    inp = dict(state.get("input") or {})
    pw_factory, err = _ensure_playwright()
    if pw_factory is None:
        return {**state, "ok": False, "error": err or "playwright unavailable"}
    extracted: dict[str, Any] = {}
    try:
        with pw_factory() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context()
                page = ctx.new_page()
                page.goto("https://example.com/search")
                page.wait_for_selector("input[name=q]", timeout=5000)
                page.fill("input[name=q]", str(inp.get("query", "")))
                page.click("button[type=submit]")
                page.wait_for_selector(".result", timeout=8000)
                page.locator(".result:last-child").first.scroll_into_view_if_needed()
                extracted["result_titles"] = page.locator(".result h2").all_text_contents()
                extracted["result_count_label"] = page.locator(".result-count").first.text_content()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 — browser failures surface to state.error
        return {**state, "ok": False, "extracted": extracted, "error": str(exc)}
    return {**state, "ok": True, "extracted": extracted}


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(ExamplePortalState)
    g.add_node("readHeading", read_heading_node)
    g.add_node("searchTerm", search_term_node)

    def _router(state: ExamplePortalState) -> str:
        op = state.get("op") or "readHeading"
        return op if op in {"readHeading", "searchTerm"} else "readHeading"

    g.add_conditional_edges(START, _router, {
        "readHeading": "readHeading",
        "searchTerm": "searchTerm",
    })
    g.add_edge("readHeading", END)
    g.add_edge("searchTerm", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> ExamplePortalState:
    return {
        "op": event.get("op", "readHeading"),
        "input": event.get("input", {}) or {},
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    key = json.dumps(
        {"op": event.get("op"), "input": event.get("input")},
        sort_keys=True,
        default=str,
    )
    return f"yorishiro-{YORISHIRO_NAME}-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def healthz() -> dict[str, Any]:
    pw, err = _ensure_playwright()
    return {
        "ok": pw is not None,
        "yorishiro": YORISHIRO_NAME,
        "kami": YORISHIRO_KAMI,
        "base_url": YORISHIRO_BASE_URL,
        "purposes": list(YORISHIRO_PURPOSES),
        "ops": ["readHeading","searchTerm"],
        "playwright": "available" if pw is not None else err,
    }


__all__ = [
    "ExamplePortalState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "read_heading_node",
    "search_term_node",
]
