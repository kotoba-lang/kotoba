"""
Yorishiro: clap-derive-demo (kami: bin:clap-derive-demo)
Generator: @etzhayyim/yorishiro v0.1.0 (binary-cli mode)
Per ADR-2605211900 + ADR-2605202200.

Transport: binary-cli
Binary   : clap-derive-demo
Charter purposes: grant

The cell shells out to a local binary via subprocess. The binary MUST be
present on the cell runtime's PATH (or supplied as an absolute path in
the kami manifest). Argv is constructed as a list — never via a shell
string — to keep injection vectors closed.

This file is generator output. Hand edits are overwritten by
`yorishiro regen clap-derive-demo`. Extend the kami manifest instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "clap-derive-demo"
YORISHIRO_KAMI = "bin:clap-derive-demo"
YORISHIRO_BINARY = "clap-derive-demo"
YORISHIRO_PURPOSES = tuple(["grant"])


class ClapDeriveDemoState(TypedDict, total=False):
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


def encode_node(state: dict[str, Any]) -> dict[str, Any]:
    """Demo clap derive-style CLI used by the yorishiro fixture."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if args.get("config") is not None and args.get("config") != "":
        argv.append("--config")
        argv.append(str(args["config"]))
    if args.get("bitrate") is not None and args.get("bitrate") != "":
        argv.append("--bitrate")
        argv.append(str(args["bitrate"]))
    if bool(args.get("lossless")):
        argv.append("--lossless")
    pos = args.get("input_path", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}

def decode_node(state: dict[str, Any]) -> dict[str, Any]:
    """Demo clap derive-style CLI used by the yorishiro fixture."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if bool(args.get("verbose")):
        argv.append("--verbose")
    if args.get("config") is not None and args.get("config") != "":
        argv.append("--config")
        argv.append(str(args["config"]))
    if args.get("sample_rate") is not None and args.get("sample_rate") != "":
        argv.append("--sample-rate")
        argv.append(str(args["sample_rate"]))
    pos = args.get("input_path", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    pos = args.get("output_path", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=300)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(ClapDeriveDemoState)
    g.add_node("encode", encode_node)
    g.add_node("decode", decode_node)

    def _router(state: ClapDeriveDemoState) -> str:
        op = state.get("op") or "encode"
        return op if op in {"encode", "decode"} else "encode"

    g.add_conditional_edges(START, _router, {
        "encode": "encode",
        "decode": "decode",
    })
    g.add_edge("encode", END)
    g.add_edge("decode", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> ClapDeriveDemoState:
    return {
        "op": event.get("op", "encode"),
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
        "ops": ["encode","decode"],
    }


__all__ = [
    "ClapDeriveDemoState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "encode_node",
    "decode_node",
]
