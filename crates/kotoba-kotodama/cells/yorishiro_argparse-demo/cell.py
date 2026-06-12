"""
Yorishiro: argparse-demo (kami: bin:argparse-demo)
Generator: @etzhayyim/yorishiro v0.1.0 (binary-cli mode)
Per ADR-2605211900 + ADR-2605202200.

Transport: binary-cli
Binary   : argparse-demo
Charter purposes: grant

The cell shells out to a local binary via subprocess. The binary MUST be
present on the cell runtime's PATH (or supplied as an absolute path in
the kami manifest). Argv is constructed as a list — never via a shell
string — to keep injection vectors closed.

This file is generator output. Hand edits are overwritten by
`yorishiro regen argparse-demo`. Extend the kami manifest instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "argparse-demo"
YORISHIRO_KAMI = "bin:argparse-demo"
YORISHIRO_BINARY = "argparse-demo"
YORISHIRO_PURPOSES = tuple(["grant"])


class ArgparseDemoState(TypedDict, total=False):
    op: str
    args: dict[str, Any]
    exit_code: int
    stdout: str
    stderr: str
    error: str


def _resolve_binary(binary: str) -> str | None:
    if "/" in binary:
        return binary
    return shutil.which(binary)


def _run(argv: list[str], timeout: int) -> tuple[int, str, str, str | None]:
    bin_path = _resolve_binary(argv[0])
    if not bin_path:
        return -1, "", "", f"binary not found on PATH: {argv[0]}"
    try:
        proc = subprocess.run(
            [bin_path, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr, None
    except subprocess.TimeoutExpired as exc:
        return -1, "", "", f"timeout after {exc.timeout}s"
    except Exception as exc:  # noqa: BLE001 — binary failures surface to state.error
        return -1, "", "", str(exc)


def main_node(state: dict[str, Any]) -> dict[str, Any]:
    """Demo argparse CLI used by the yorishiro source-repo fixture."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if args.get("max_rows") is not None and args.get("max_rows") != "":
        argv.append("--max-rows")
        argv.append(str(args["max_rows"]))
    if args.get("encoding") is not None and args.get("encoding") != "":
        argv.append("--encoding")
        argv.append(str(args["encoding"]))
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if bool(args.get("dry_run")):
        argv.append("--dry-run")
    pos = args.get("source_path", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    pos = args.get("output_path", "-")
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(ArgparseDemoState)
    g.add_node("main", main_node)

    def _router(state: ArgparseDemoState) -> str:
        op = state.get("op") or "main"
        return op if op in {"main"} else "main"

    g.add_conditional_edges(START, _router, {
        "main": "main",
    })
    g.add_edge("main", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> ArgparseDemoState:
    return {
        "op": event.get("op", "main"),
        "args": event.get("args", {}) or {},
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    key = json.dumps(
        {"op": event.get("op"), "args": event.get("args")},
        sort_keys=True,
        default=str,
    )
    return f"yorishiro-{YORISHIRO_NAME}-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "yorishiro": YORISHIRO_NAME,
        "kami": YORISHIRO_KAMI,
        "binary": YORISHIRO_BINARY,
        "binary_resolved": _resolve_binary(YORISHIRO_BINARY),
        "purposes": list(YORISHIRO_PURPOSES),
        "ops": ["main"],
    }


__all__ = [
    "ArgparseDemoState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "main_node",
]
