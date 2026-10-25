"""Tool handlers for the kotoba Hermes plugin.

This file contains NO answers about kotoba-lang. It turns tool arguments into
an argv, runs `read_authority.cljk` (or `amu`), and turns an exit code into a
protocol answer. The reasoning about what an authority file means lives beside
the data, in the same language, so there is exactly one reader
(the doctrine of ADR-2608197300 §3, as applied by `dashboard_auth/did`).

## The exit codes are the contract

    0  answered              -> tool_result
    1  answered: not present -> tool_result with found=false
    2  could not answer      -> tool_error

1 and 2 are kept apart deliberately. "this feature is not listed in the
authority" is a measurement. "I could not open the authority" is not, and a
caller that cannot tell them apart will report an unread file as a permanent
absence -- the failure class this workspace names in ADR-2608136000.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, Optional

from tools.registry import tool_error, tool_result

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
READER = os.path.join(PLUGIN_DIR, "read_authority.cljk")

TIMEOUT_S = 60


def _workspace() -> Optional[str]:
    ws = os.environ.get("KOTOBA_WORKSPACE")
    return os.path.expanduser(ws) if ws else None


def _nbb() -> Optional[str]:
    return os.environ.get("KOTOBA_NBB") or shutil.which("nbb")


def available() -> bool:
    """Gate for tool dispatch: a configured workspace and a reader to run it."""
    ws = _workspace()
    return bool(ws and os.path.isdir(ws) and _nbb() and os.path.exists(READER))


def _run_reader(command: str, argument: str = "") -> str:
    ws = _workspace()
    if not ws:
        return tool_error(
            "KOTOBA_WORKSPACE is not set. This tool reports what the "
            "kotoba-lang authority files say; without a checkout it can "
            "report nothing, and reporting nothing must not read as "
            "'the feature is absent'."
        )
    nbb = _nbb()
    if not nbb:
        return tool_error("nbb was not found (set KOTOBA_NBB or put it on PATH).")

    argv = [nbb, READER, command, ws]
    if argument:
        argv.append(argument)
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return tool_error(f"the authority reader did not finish in {TIMEOUT_S}s")
    except OSError as exc:
        return tool_error(f"could not run the authority reader: {exc}")

    payload: Dict[str, Any]
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        # No parseable answer. Keep the reader's own words: the cause is
        # usually in them (a broken classpath, a missing namespace), and a
        # handler that discards stderr reports a mystery instead.
        detail = (proc.stderr or proc.stdout or "").strip()[:800]
        return tool_error(
            f"the authority reader produced no answer (exit {proc.returncode})",
            detail=detail,
        )

    if proc.returncode == 2:
        return tool_error(
            "could not read the kotoba-lang authority: "
            f"{payload.get('why', 'unknown')}",
            **{k: v for k, v in payload.items() if k != "ok"},
        )
    # 0 and 1 are both answers. The caller distinguishes them by `found`.
    return tool_result(payload)


# ── kotoba_surface_status ──────────────────────────────────────────────────

SURFACE_STATUS_SCHEMA = {
    "name": "kotoba_surface_status",
    "description": (
        "Is a Kotoba restriction PERMANENT or a backend that has not caught "
        "up? Reads lang/surface-status.edn and returns the entry's "
        "`disposition`: intentional-security-constraint and "
        "intentional-semantic-simplification are permanent; "
        "implemented-partial exists already; not-yet-implemented is a GAP, "
        "not a prohibition. Call this before concluding that Kotoba cannot "
        "express something, and before repeating any readiness claim from "
        "memory or from a document -- every such value in this workspace has "
        "gone stale at least once. The answer carries the authority's own "
        "`as-of` date; if it is old, the checkout is behind, not the language."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "The invariant / surface entry to look up, e.g. "
                    "'bool-is-a-type-not-a-number'. Omit to list every entry "
                    "with its disposition."
                ),
            }
        },
        "required": [],
    },
}


def handle_surface_status(args: Dict[str, Any]) -> str:
    return _run_reader("surface-status", str(args.get("name") or ""))


# ── kotoba_capability_kits ─────────────────────────────────────────────────

CAPABILITY_KITS_SCHEMA = {
    "name": "kotoba_capability_kits",
    "description": (
        "Which backends have QUALIFIED a Kotoba capability kit. Reads every "
        "resources/kotoba/lang/capability-kits/*.edn and returns each kit's "
        "`qualification` map verbatim. The key set differs per kit, so never "
        "summarise across kits, and `pending` records a measured refusal with "
        "a reason -- it does not mean nobody tried. Reading these with grep "
        "truncates silently on wrapped lines, which is why this tool exists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kit": {
                "type": "string",
                "description": "One kit id, e.g. 'ui-v1'. Omit for all kits.",
            }
        },
        "required": [],
    },
}


def handle_capability_kits(args: Dict[str, Any]) -> str:
    return _run_reader("capability-kits", str(args.get("kit") or ""))


# ── kotoba_check ───────────────────────────────────────────────────────────

CHECK_SCHEMA = {
    "name": "kotoba_check",
    "description": (
        "Run `amu check` on one .kotoba file and return its verdict verbatim. "
        "IMPORTANT: `check` returning ok is NOT 'it works'. A value of the "
        "wrong type for document-bool passes check and fails at the value "
        "phase when the export is executed. Treat a passing check as "
        "'the compiler admitted it', and run the export before saying more."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fresh": {
                "type": "boolean",
                "description": "true bypasses the memo (same file closure + same amu -> served verdict) and re-runs amu check."
            },
            "file": {
                "type": "string",
                "description": "Path to the .kotoba file, relative to KOTOBA_WORKSPACE or absolute.",
            }
        },
        "required": ["file"],
    },
}


# ── memo (iteration 20, 2026-09-18) ────────────────────────────────────────
#
# `amu check` is pure (no effect set): the same source closure gives the same
# verdict. ADR-2608160200 allows a memo keyed by the Execution CID exactly when
# the effect set is empty. The key here is symbol-index's FILE CLOSURE HASH
# (every definition's Merkle hash, dependencies folded in — names, comments,
# docstrings and whitespace excluded) plus the amu binary's identity. A comment
# edit is a hit; a body edit anywhere in the closure is a miss.
#
# The memo is a convenience, never an authority: a verdict served from the memo
# says so ("memo": {"hit": true, ...}) and can be bypassed with fresh=true. When
# the closure cannot be computed (no index, no symbol-index) the check runs
# and is NOT memoised — "could not key it" must not look like "keyed it".

MEMO_PATH = os.path.expanduser(os.environ.get("KOTOBA_CHECK_MEMO") or "~/.kotoba-cache/kotoba-check-memo.json")


def _symbol_index_argv(ws: str) -> Optional[list]:
    forced = os.environ.get("KOTOBA_SYMBOL_INDEX")
    if forced:
        forced = os.path.expanduser(forced)
        if forced.endswith(".cljk"):
            kbb = shutil.which("kbb")
            return [kbb, "--backend", "sci", forced] if kbb and os.path.exists(forced) else None
        return [forced] if os.path.exists(forced) else None
    on_path = shutil.which("symbol-index")
    if on_path:
        return [on_path]
    script = os.path.join(ws, "orgs/kotoba-lang/symbol-index/scripts/symbol-index.cljk")
    kbb = shutil.which("kbb")
    if kbb and os.path.exists(script):
        return [kbb, "--backend", "sci", script]
    return None


def _file_closure(ws: str, target: str) -> Dict[str, Any]:
    """{"hash": ..} or {"why": ..} — never a silent None."""
    argv = _symbol_index_argv(ws)
    if not argv:
        return {"why": "symbol-index not found (PATH or orgs/kotoba-lang/symbol-index)"}
    rel = os.path.relpath(target, ws)
    try:
        proc = subprocess.run(argv + ["closure", rel], capture_output=True, text=True, timeout=120, cwd=ws)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"why": f"symbol-index closure failed to run: {exc}"}
    if proc.returncode != 0:
        first = (proc.stdout.strip().splitlines() or [proc.stderr.strip()[:200]])[0]
        return {"why": f"symbol-index closure exit {proc.returncode}: {first[:200]}"}
    for line in proc.stdout.splitlines():
        if line.startswith("closure-file ") and "  #" in line:
            return {"hash": line.rsplit("#", 1)[1].strip()}
    return {"why": "symbol-index closure printed no closure-file line"}


def _amu_identity(amu: str) -> str:
    st = os.stat(amu)
    return f"{amu}:{int(st.st_mtime)}:{st.st_size}"


def _memo_load() -> Dict[str, Any]:
    try:
        with open(MEMO_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _memo_store(memo: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MEMO_PATH), exist_ok=True)
    tmp = MEMO_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(memo, fh, ensure_ascii=False, indent=0)
    os.replace(tmp, MEMO_PATH)


def run_check(ws: str, target: str, fresh: bool = False) -> Dict[str, Any]:
    """The check with its memo. Returns the result dict (tool_result wraps it)."""
    amu = os.environ.get("KOTOBA_AMU") or os.path.join(ws, "orgs/kotoba-lang/amu/bin/amu")
    if not os.path.exists(amu):
        return {"error": f"amu was not found at {amu} (set KOTOBA_AMU)"}

    closure = _file_closure(ws, target)
    key = None
    memo_note: Dict[str, Any] = {"hit": False}
    if "hash" in closure:
        key = closure["hash"] + "|" + _amu_identity(amu)
        memo_note["key"] = closure["hash"]
        if not fresh:
            hit = _memo_load().get(key)
            if isinstance(hit, dict) and "exit" in hit:
                out = dict(hit)
                out["memo"] = {"hit": True, "key": closure["hash"], "stored_at": hit.get("stored_at"),
                               "note": "served from the memo: same file closure (definitions and their dependencies), same amu. fresh=true re-runs."}
                out.pop("stored_at", None)
                return out
    else:
        memo_note["not_keyed"] = closure["why"]

    try:
        proc = subprocess.run([amu, "check", target], capture_output=True, text=True, timeout=300, cwd=ws)
    except subprocess.TimeoutExpired:
        return {"error": "amu check did not finish in 300s"}
    except OSError as exc:
        return {"error": f"could not run amu: {exc}"}

    result = {
        "exit": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "note": (
            "check admitted the module; it did not run it. A "
            "document-bool type error appears only when the export runs."
            if proc.returncode == 0
            else "check refused the module; the reason is in stdout/stderr."
        ),
    }
    if key is not None:
        import time
        memo = _memo_load()
        memo[key] = dict(result, stored_at=int(time.time()))
        try:
            _memo_store(memo)
        except OSError as exc:
            memo_note["store_failed"] = str(exc)
    result["memo"] = memo_note
    return result


def handle_check(args: Dict[str, Any]) -> str:
    ws = _workspace()
    if not ws:
        return tool_error("KOTOBA_WORKSPACE is not set.")
    raw = str(args.get("file") or "").strip()
    if not raw:
        return tool_error("file is required")
    target = raw if os.path.isabs(raw) else os.path.join(ws, raw)
    if not os.path.exists(target):
        return tool_error(f"no such file: {target}")
    out = run_check(ws, target, fresh=bool(args.get("fresh")))
    if "error" in out:
        return tool_error(out["error"])
    return tool_result(out)
