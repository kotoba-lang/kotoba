"""
Yorishiro: cobra-demo (kami: bin:cobra-demo)
Generator: @etzhayyim/yorishiro v0.1.0 (binary-cli mode)
Per ADR-2605211900 + ADR-2605202200.

Transport: binary-cli
Binary   : cobra-demo
Charter purposes: grant

The cell shells out to a local binary via subprocess. The binary MUST be
present on the cell runtime's PATH (or supplied as an absolute path in
the kami manifest). Argv is constructed as a list — never via a shell
string — to keep injection vectors closed.

This file is generator output. Hand edits are overwritten by
`yorishiro regen cobra-demo`. Extend the kami manifest instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "cobra-demo"
YORISHIRO_KAMI = "bin:cobra-demo"
YORISHIRO_BINARY = "cobra-demo"
YORISHIRO_PURPOSES = tuple(["grant"])


class CobraDemoState(TypedDict, total=False):
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


def cobra_demo_node(state: dict[str, Any]) -> dict[str, Any]:
    """Longer description of the cobra demo CLI."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if args.get("config") is not None and args.get("config") != "":
        argv.append("--config")
        argv.append(str(args["config"]))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}

def greet_node(state: dict[str, Any]) -> dict[str, Any]:
    """Print a greeting for NAME with optional shouting."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if args.get("config") is not None and args.get("config") != "":
        argv.append("--config")
        argv.append(str(args["config"]))
    if bool(args.get("shout")):
        argv.append("--shout")
    if args.get("lang") is not None and args.get("lang") != "":
        argv.append("--lang")
        argv.append(str(args["lang"]))
    pos = args.get("arg0", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}

def render_node(state: dict[str, Any]) -> dict[str, Any]:
    """Render output to file or stdout."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if args.get("config") is not None and args.get("config") != "":
        argv.append("--config")
        argv.append(str(args["config"]))
    if args.get("max_rows") is not None and args.get("max_rows") != "":
        argv.append("--max-rows")
        argv.append(str(args["max_rows"]))
    if args.get("quality") is not None and args.get("quality") != "":
        argv.append("--quality")
        argv.append(str(args["quality"]))
    pos = args.get("arg0", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(CobraDemoState)
    g.add_node("cobra-demo", cobra_demo_node)
    g.add_node("greet", greet_node)
    g.add_node("render", render_node)

    def _router(state: CobraDemoState) -> str:
        op = state.get("op") or "cobra-demo"
        return op if op in {"cobra-demo", "greet", "render"} else "cobra-demo"

    g.add_conditional_edges(START, _router, {
        "cobra-demo": "cobra-demo",
        "greet": "greet",
        "render": "render",
    })
    g.add_edge("cobra-demo", END)
    g.add_edge("greet", END)
    g.add_edge("render", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> CobraDemoState:
    return {
        "op": event.get("op", "cobra-demo"),
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
        "ops": ["cobra-demo","greet","render"],
    }


__all__ = [
    "CobraDemoState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "cobra_demo_node",
    "greet_node",
    "render_node",
]
