"""Invocation log emit.

R0 writes one NDJSON line per ``.remote()`` to ``~/.kotoba_murakumo/invocations.ndjson``.
R1 promotes to ``com.etzhayyim.murakumo.invocation`` Lexicon record on the
caller's PDS (ADR-2605282000 §"Invocation record").
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path(os.environ.get(
    "KOTOBA_MURAKUMO_LOG",
    str(Path.home() / ".kotoba_murakumo" / "invocations.ndjson"),
))

_LOCK = threading.Lock()


def emit(record: dict[str, Any], *, path: Path | None = None) -> None:
    """Append one NDJSON line. Best-effort: never raises into the caller.

    Resolves the default path at *call* time (not function-definition time)
    so test fixtures reassigning ``_DEFAULT_PATH`` take effect.
    """
    target = path if path is not None else _DEFAULT_PATH
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **record,
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _LOCK, target.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        # Logging must never break inference. The Charter scan + endpoint
        # routing are the real invariants; NDJSON is an observability hint.
        pass
