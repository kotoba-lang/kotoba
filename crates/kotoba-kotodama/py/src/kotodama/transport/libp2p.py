"""
libp2p transport — Python wrapper around the etzhayyim-libp2p shell scripts.

Per ADR-2605241800 ("shell-thin" intent): this module deliberately does NOT
re-implement the libp2p mount/unmount logic in Python. It shells out to the
canonical scripts under ``10-protocol/etzhayyim-libp2p/scripts/`` and parses
their stdout. The scripts remain the single source of truth.

Public surface (all return values are JSON-serializable):

    ensure_libp2p_enabled() -> (ok, detail)
    self_peer_id()         -> str
    expose_port(port, version="1.0")              -> MountResult
    dial_peer(peer_id, local_port, version="1.0") -> MountResult
    list_mounts()           -> list[dict]
    close_mount(protocol)   -> bool
    local_multiaddr(form)   -> list[str]
    agent_json_service(version="1.0") -> list[dict]
    healthz()               -> dict

Stdlib only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("kotodama.transport.libp2p")

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

# This file lives at:
#   <repo>/20-actors/kotoba-kotodama/py/src/kotodama/transport/libp2p.py
# parents[0]=transport, [1]=kotodama, [2]=src, [3]=py,
# [4]=kotoba-kotodama, [5]=20-actors, [6]=<repo-root>.
_THIS = Path(__file__).resolve()


def _find_repo_root() -> Path:
    """Walk up looking for a directory that contains ``10-protocol/``.

    Falls back to ``parents[6]`` (the layout assumed at write time).
    Override with ``ETZHAYYIM_REPO_ROOT`` if needed.
    """
    override = os.environ.get("ETZHAYYIM_REPO_ROOT")
    if override:
        return Path(override).resolve()
    for cand in _THIS.parents:
        if (cand / "10-protocol" / "etzhayyim-libp2p" / "scripts").is_dir():
            return cand
    # Fallback: original spec layout.
    return _THIS.parents[6] if len(_THIS.parents) > 6 else _THIS.parents[-1]


REPO_ROOT: Path = _find_repo_root()
SCRIPTS_DIR: Path = REPO_ROOT / "10-protocol" / "etzhayyim-libp2p" / "scripts"
PROTOCOL_PREFIX: str = "/x/etzhayyim/xrpc"

_EXPOSE_SH = SCRIPTS_DIR / "expose-xrpc.sh"
_DIAL_SH = SCRIPTS_DIR / "dial-xrpc.sh"
_MULTIADDR_SH = SCRIPTS_DIR / "print-multiaddr.sh"
_AGENT_JSON_SH = SCRIPTS_DIR / "agent-json-libp2p-service.sh"

_DEFAULT_TIMEOUT = 10  # seconds per subprocess call


# --------------------------------------------------------------------------- #
# Dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MountResult:
    ok: bool
    protocol: str           # e.g. "/x/etzhayyim/xrpc/1.0"
    role: str               # "listen" | "forward"
    local_tcp_port: int | None
    peer_id: str | None     # consumer-side: target peer; actor-side: self
    raw_stdout: str
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _run(
    argv: list[str],
    *,
    timeout: int = _DEFAULT_TIMEOUT,
) -> tuple[bool, str, str, str | None]:
    """Run a subprocess; never raise.

    Returns ``(ok, stdout, stderr, error_kind_or_None)``.
    ``error_kind`` is a short tag like ``"FileNotFound"``, ``"Timeout"``,
    ``"NonZeroExit"`` so callers can branch without parsing strings.
    """
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        logger.debug("subprocess FileNotFoundError: %s", exc)
        return (False, "", str(exc), "FileNotFound")
    except subprocess.TimeoutExpired as exc:
        logger.debug("subprocess TimeoutExpired: %s", exc)
        return (False, "", f"timeout after {timeout}s", "Timeout")
    except OSError as exc:
        logger.debug("subprocess OSError: %s", exc)
        return (False, "", str(exc), "OSError")

    if proc.returncode != 0:
        return (False, proc.stdout or "", proc.stderr or "", "NonZeroExit")
    return (True, proc.stdout or "", proc.stderr or "", None)


def _ipfs_available() -> tuple[bool, str | None]:
    """Return (True, version_str) if `ipfs version` succeeds, else (False, None)."""
    ok, out, _err, _kind = _run(["ipfs", "version", "--number"], timeout=5)
    if not ok:
        return (False, None)
    return (True, out.strip() or None)


# Peer-id is base58btc or base32 — accept a lenient alphanumeric range to
# avoid hard-coding multibase rules. Real validation happens server-side.
_PEER_ID_RE = re.compile(r"^[A-Za-z0-9]{32,80}$")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def ensure_libp2p_enabled() -> tuple[bool, str]:
    """Preflight: Kubo on PATH + Experimental.Libp2pStreamMounting=true.

    Returns ``(ok, detail)``. On failure ``detail`` includes the fix command.
    """
    ipfs_ok, version = _ipfs_available()
    if not ipfs_ok:
        return (
            False,
            "Kubo `ipfs` CLI not on PATH. Install: `brew install ipfs` "
            "(or see https://docs.ipfs.tech/install/).",
        )

    ok, out, err, kind = _run(
        ["ipfs", "config", "Experimental.Libp2pStreamMounting"],
        timeout=5,
    )
    if not ok:
        # Daemon may not be required for `ipfs config`, but repo may be missing.
        return (
            False,
            f"`ipfs config` failed ({kind}): {err.strip() or 'no detail'}. "
            "Run `ipfs init` first, then "
            "`ipfs config --json Experimental.Libp2pStreamMounting true`.",
        )

    value = out.strip().lower()
    if value != "true":
        return (
            False,
            "Experimental.Libp2pStreamMounting is not enabled. Fix: "
            "`ipfs config --json Experimental.Libp2pStreamMounting true` "
            "then restart the Kubo daemon.",
        )

    return (
        True,
        f"Kubo {version or '(unknown version)'} present; "
        "Libp2pStreamMounting=true.",
    )


def self_peer_id() -> str:
    """Return this Kubo node's PeerId.

    Raises ``RuntimeError`` if Kubo is unavailable or returns no id.
    """
    ok, out, err, kind = _run(["ipfs", "id", "-f", "<id>"], timeout=5)
    if not ok:
        raise RuntimeError(
            f"self_peer_id: `ipfs id` failed ({kind}): {err.strip() or 'no detail'}"
        )
    pid = out.strip()
    if not pid:
        raise RuntimeError("self_peer_id: empty PeerId returned by `ipfs id`")
    return pid


def expose_port(port: int, version: str = "1.0") -> MountResult:
    """Actor side. Mount ``/x/etzhayyim/xrpc/<version>`` → 127.0.0.1:<port>.

    Idempotent: ``expose-xrpc.sh`` closes any existing mount on the protocol
    before re-listening.
    """
    protocol = f"{PROTOCOL_PREFIX}/{version}"

    if not isinstance(port, int) or not (0 < port < 65536):
        return MountResult(
            ok=False,
            protocol=protocol,
            role="listen",
            local_tcp_port=None,
            peer_id=None,
            raw_stdout="",
            error="InvalidPort",
        )

    if not _EXPOSE_SH.exists():
        return MountResult(
            ok=False,
            protocol=protocol,
            role="listen",
            local_tcp_port=port,
            peer_id=None,
            raw_stdout="",
            error=f"ScriptNotFound: {_EXPOSE_SH}",
        )

    ok, out, err, kind = _run(
        ["bash", str(_EXPOSE_SH), str(port), version],
        timeout=_DEFAULT_TIMEOUT,
    )
    if not ok:
        return MountResult(
            ok=False,
            protocol=protocol,
            role="listen",
            local_tcp_port=port,
            peer_id=None,
            raw_stdout=out,
            error=f"{kind}: {(err or out).strip()}",
        )

    # Try to fill in self peer-id (best-effort; don't fail the result if it
    # can't be determined).
    peer_id: str | None
    try:
        peer_id = self_peer_id()
    except RuntimeError:
        peer_id = None

    return MountResult(
        ok=True,
        protocol=protocol,
        role="listen",
        local_tcp_port=port,
        peer_id=peer_id,
        raw_stdout=out,
        error=None,
    )


def dial_peer(peer_id: str, local_port: int, version: str = "1.0") -> MountResult:
    """Consumer side. Forward 127.0.0.1:<local_port> → /p2p/<peer_id>.

    Idempotent: ``dial-xrpc.sh`` closes any existing mount on the protocol
    before re-forwarding.
    """
    protocol = f"{PROTOCOL_PREFIX}/{version}"

    if not isinstance(peer_id, str) or not _PEER_ID_RE.match(peer_id):
        return MountResult(
            ok=False,
            protocol=protocol,
            role="forward",
            local_tcp_port=local_port if isinstance(local_port, int) else None,
            peer_id=None,
            raw_stdout="",
            error="InvalidPeerId",
        )

    if not isinstance(local_port, int) or not (0 < local_port < 65536):
        return MountResult(
            ok=False,
            protocol=protocol,
            role="forward",
            local_tcp_port=None,
            peer_id=peer_id,
            raw_stdout="",
            error="InvalidPort",
        )

    if not _DIAL_SH.exists():
        return MountResult(
            ok=False,
            protocol=protocol,
            role="forward",
            local_tcp_port=local_port,
            peer_id=peer_id,
            raw_stdout="",
            error=f"ScriptNotFound: {_DIAL_SH}",
        )

    ok, out, err, kind = _run(
        ["bash", str(_DIAL_SH), peer_id, str(local_port), version],
        timeout=_DEFAULT_TIMEOUT,
    )
    if not ok:
        return MountResult(
            ok=False,
            protocol=protocol,
            role="forward",
            local_tcp_port=local_port,
            peer_id=peer_id,
            raw_stdout=out,
            error=f"{kind}: {(err or out).strip()}",
        )

    return MountResult(
        ok=True,
        protocol=protocol,
        role="forward",
        local_tcp_port=local_port,
        peer_id=peer_id,
        raw_stdout=out,
        error=None,
    )


def list_mounts() -> list[dict[str, Any]]:
    """Parse ``ipfs p2p ls`` into a list of mount records.

    Each record:
        {
          "protocol":      str,        # e.g. "/x/etzhayyim/xrpc/1.0"
          "listenAddress": str,        # the first multiaddr column
          "targetAddress": str,        # the second multiaddr column
          "role":          "listen"|"forward",
        }

    Distinguishes by the target column: ``/p2p/...`` ⇒ forward (dial-out),
    otherwise (``/ip4/.../tcp/...``) ⇒ listen (local exposure).

    Returns an empty list on any failure (logged at DEBUG).
    """
    ok, out, err, kind = _run(["ipfs", "p2p", "ls"], timeout=5)
    if not ok:
        logger.debug("list_mounts: ipfs p2p ls failed (%s): %s", kind, err.strip())
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            # Unexpected format; skip but record at debug level.
            logger.debug("list_mounts: unparseable line: %r", line)
            continue
        protocol, listen_addr, target_addr = parts[0], parts[1], parts[2]
        role = "forward" if "/p2p/" in target_addr else "listen"
        rows.append(
            {
                "protocol": protocol,
                "listenAddress": listen_addr,
                "targetAddress": target_addr,
                "role": role,
            }
        )
    return rows


def close_mount(protocol: str) -> bool:
    """Close any active mount on ``protocol``. Returns True on success."""
    if not isinstance(protocol, str) or not protocol:
        return False
    ok, _out, err, kind = _run(
        ["ipfs", "p2p", "close", "--protocol", protocol],
        timeout=5,
    )
    if not ok:
        logger.debug(
            "close_mount(%s) failed (%s): %s", protocol, kind, err.strip()
        )
    return ok


def local_multiaddr(form: str = "peer") -> list[str]:
    """Return Multiaddrs identifying this node, via ``print-multiaddr.sh``.

    ``form`` is one of: ``peer`` | ``dnsaddr`` | ``all-local`` | ``all``.
    Returns ``[]`` on failure.
    """
    if form not in {"peer", "dnsaddr", "all-local", "all"}:
        logger.debug("local_multiaddr: rejecting form=%r", form)
        return []

    if not _MULTIADDR_SH.exists():
        logger.debug("local_multiaddr: script missing at %s", _MULTIADDR_SH)
        return []

    ok, out, err, kind = _run(
        ["bash", str(_MULTIADDR_SH), form],
        timeout=_DEFAULT_TIMEOUT,
    )
    if not ok:
        logger.debug(
            "local_multiaddr(%s) failed (%s): %s", form, kind, err.strip()
        )
        return []

    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def agent_json_service(version: str = "1.0") -> list[dict[str, Any]]:
    """Return parsed JSON from ``agent-json-libp2p-service.sh <version>``.

    Returns ``[]`` on failure.
    """
    if not _AGENT_JSON_SH.exists():
        logger.debug("agent_json_service: script missing at %s", _AGENT_JSON_SH)
        return []

    ok, out, err, kind = _run(
        ["bash", str(_AGENT_JSON_SH), version],
        timeout=_DEFAULT_TIMEOUT,
    )
    if not ok:
        logger.debug(
            "agent_json_service(%s) failed (%s): %s", version, kind, err.strip()
        )
        return []

    try:
        parsed = json.loads(out)
    except json.JSONDecodeError as exc:
        logger.debug("agent_json_service: JSON decode error: %s; raw=%r", exc, out)
        return []

    if not isinstance(parsed, list):
        logger.debug("agent_json_service: expected list, got %r", type(parsed))
        return []

    return parsed


def healthz() -> dict[str, Any]:
    """Return a tolerant health summary.

    Never raises. Shape::

        {
          "ok": bool,
          "kuboVersion":          str | None,
          "libp2pStreamMounting": bool | None,
          "peerId":               str | None,
          "activeMounts":         list[dict],
          "protocolPrefix":       str,
          "scriptsDir":           str,
          "error":                str | None,
          "hint":                 str | None,
        }
    """
    result: dict[str, Any] = {
        "ok": False,
        "kuboVersion": None,
        "libp2pStreamMounting": None,
        "peerId": None,
        "activeMounts": [],
        "protocolPrefix": PROTOCOL_PREFIX,
        "scriptsDir": str(SCRIPTS_DIR),
        "error": None,
        "hint": None,
    }

    ipfs_ok, version = _ipfs_available()
    if not ipfs_ok:
        result["error"] = "KuboNotInstalled"
        result["hint"] = "brew install ipfs"
        return result
    result["kuboVersion"] = version

    cfg_ok, out, err, _kind = _run(
        ["ipfs", "config", "Experimental.Libp2pStreamMounting"],
        timeout=5,
    )
    if cfg_ok:
        result["libp2pStreamMounting"] = out.strip().lower() == "true"
    else:
        result["error"] = "ConfigReadFailed"
        result["hint"] = (
            "Run `ipfs init`, then "
            "`ipfs config --json Experimental.Libp2pStreamMounting true`."
        )
        return result

    if not result["libp2pStreamMounting"]:
        result["hint"] = (
            "Enable with: "
            "`ipfs config --json Experimental.Libp2pStreamMounting true` "
            "then restart the Kubo daemon."
        )

    # PeerId requires a running daemon for some Kubo builds but typically
    # works against the local repo even when offline.
    try:
        result["peerId"] = self_peer_id()
    except RuntimeError as exc:
        result["hint"] = (
            (result["hint"] or "")
            + f" [peerId unavailable: {exc}]"
        ).strip()

    # Active mounts require the daemon; tolerate failure.
    result["activeMounts"] = list_mounts()

    result["ok"] = bool(
        result["kuboVersion"]
        and result["libp2pStreamMounting"]
        and result["peerId"]
    )
    return result


__all__ = [
    "MountResult",
    "PROTOCOL_PREFIX",
    "REPO_ROOT",
    "SCRIPTS_DIR",
    "agent_json_service",
    "close_mount",
    "dial_peer",
    "ensure_libp2p_enabled",
    "expose_port",
    "healthz",
    "list_mounts",
    "local_multiaddr",
    "self_peer_id",
]
