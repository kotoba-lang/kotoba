"""
Yorishiro: pdftotext (kami: bin:pdftotext)
Generator: @etzhayyim/yorishiro v0.1.0 (binary-cli mode)
Per ADR-2605211900 + ADR-2605202200.

Transport: binary-cli
Binary   : pdftotext
Charter purposes: grant

The cell shells out to a local binary via subprocess. The binary MUST be
present on the cell runtime's PATH (or supplied as an absolute path in
the kami manifest). Argv is constructed as a list — never via a shell
string — to keep injection vectors closed.

This file is generator output. Hand edits are overwritten by
`yorishiro regen pdftotext`. Extend the kami manifest instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


YORISHIRO_NAME = "pdftotext"
YORISHIRO_KAMI = "bin:pdftotext"
YORISHIRO_BINARY = "pdftotext"
YORISHIRO_PURPOSES = tuple(["grant"])


class PdftotextState(TypedDict, total=False):
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


def convert_node(state: dict[str, Any]) -> dict[str, Any]:
    """Invoke `pdftotext [flags] <pdf_file> [text_file]`. When `text_file` is '-' (default) the result lands on stdout; the cell captures stdout and returns it in the response."""
    args = dict(state.get("args") or {})
    argv: list[str] = [YORISHIRO_BINARY]
    if args.get("first_page") is not None and args.get("first_page") != "":
        argv.append("-f")
        argv.append(str(args["first_page"]))
    if args.get("last_page") is not None and args.get("last_page") != "":
        argv.append("-l")
        argv.append(str(args["last_page"]))
    if bool(args.get("layout")):
        argv.append("-layout")
    if bool(args.get("raw")):
        argv.append("-raw")
    if args.get("encoding") is not None and args.get("encoding") != "":
        argv.append("-enc")
        argv.append(str(args["encoding"]))
    pos = args.get("pdf_file", None)
    if pos is not None and pos != "":
        argv.append(str(pos))
    pos = args.get("text_file", "-")
    if pos is not None and pos != "":
        argv.append(str(pos))
    code, out, err, fatal = _run(argv, timeout=60)
    if fatal:
        return {**state, "exit_code": code, "stdout": out, "stderr": err, "error": fatal}
    return {**state, "exit_code": code, "stdout": out, "stderr": err}


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(PdftotextState)
    g.add_node("convert", convert_node)

    def _router(state: PdftotextState) -> str:
        op = state.get("op") or "convert"
        return op if op in {"convert"} else "convert"

    g.add_conditional_edges(START, _router, {
        "convert": "convert",
    })
    g.add_edge("convert", END)

    return g.compile(checkpointer=checkpointer)


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ───────────────────────────


def state_from_event(event: dict[str, Any]) -> PdftotextState:
    return {
        "op": event.get("op", "convert"),
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
        "ops": ["convert"],
    }


__all__ = [
    "PdftotextState",
    "build_graph",
    "state_from_event",
    "thread_id_from_event",
    "healthz",
    "convert_node",
]
