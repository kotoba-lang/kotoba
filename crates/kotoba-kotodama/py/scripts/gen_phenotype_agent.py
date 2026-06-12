"""Generate one PhenotypeAgent file for a given DID.

Usage:
  uv run python -m scripts.gen_phenotype_agent --did did:web:alice.example.com
  uv run python -m scripts.gen_phenotype_agent --did did:plc:abc... --output-dir <path>

S2 of ADR-2605172300. The template lives in
``kotodama.phenotype_agents._template`` and is rendered with three
substitutions: DID, short hash, generated timestamp, event weights.

LLM mode (per ADR-2605171300): when ``--llm`` is passed, the generator
instead consults OpenRouter ``google/gemini-3.1-flash-lite`` (or local
Murakumo / Ollama fallback) to specialize the event_weights dict based
on the adherent's stated focus (e.g., more weight on "study" for a
scholar, more on "service" for a community helper). Steady-state
generation runs without ``--llm`` and produces deterministic output.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

# Make the package importable when running from repo root without an
# installed wheel.
_HERE = Path(__file__).resolve()
_PKG_SRC = _HERE.parent.parent / "src"
if str(_PKG_SRC) not in sys.path:
    sys.path.insert(0, str(_PKG_SRC))

from kotodama.phenotype_agents._registry import did_short_hash, AGENT_PACKAGE  # noqa: E402
from kotodama.phenotype_agents._template import TEMPLATE  # noqa: E402
from kotodama.eligibility.scoring import DEFAULT_EVENT_WEIGHTS  # noqa: E402


def render(did: str, event_weights: dict[str, float] | None = None) -> str:
    weights = event_weights or dict(DEFAULT_EVENT_WEIGHTS)
    short = did_short_hash(did)
    now = dt.datetime.now(tz=dt.timezone.utc).isoformat(timespec="seconds")
    body = TEMPLATE
    body = body.replace("{{did}}", did)
    body = body.replace("{{short_hash}}", short)
    body = body.replace("{{generated_at_iso}}", now)
    body = body.replace("{{event_weights_repr}}", repr(dict(weights)))
    return body


def default_output_dir() -> Path:
    return _PKG_SRC / "kotodama" / "phenotype_agents"


def write_agent(did: str, output_dir: Path | None = None) -> Path:
    out_dir = output_dir or default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    short = did_short_hash(did)
    out_path = out_dir / f"a{short}.py"
    out_path.write_text(render(did), encoding="utf-8")
    return out_path


def _maybe_llm_weights(did: str, focus: str | None) -> dict[str, float] | None:
    """Call OpenRouter / Murakumo / Ollama to specialize event_weights.

    Returns ``None`` if no LLM credentials are configured or ``focus``
    is not provided, signaling the caller to fall back to defaults.
    """
    if not focus:
        return None
    # Match ADR-2605171300's env-driven fallback chain.
    if os.environ.get("OPENROUTER_API_KEY"):
        # TODO(S2.1): wire the actual OpenRouter call. Kept stubbed so
        #             gen_phenotype_agent stays deterministic in CI by
        #             default and only opts into a network call when
        #             --llm + OPENROUTER_API_KEY are both present.
        return None
    if os.environ.get("GEMINI_API_KEY"):
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate one PhenotypeAgent .py file")
    p.add_argument("--did", required=True, help="Adherent DID, e.g., did:web:alice.example.com")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Output directory (default: src/{AGENT_PACKAGE.replace('.', '/')}/)",
    )
    p.add_argument("--llm", action="store_true", help="Specialize event_weights via LLM (opt-in)")
    p.add_argument("--focus", default=None, help="Adherent focus hint for LLM (e.g., 'scholar')")
    args = p.parse_args(argv)

    weights = None
    if args.llm:
        weights = _maybe_llm_weights(args.did, args.focus)

    out_dir = args.output_dir or default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    short = did_short_hash(args.did)
    out_path = out_dir / f"a{short}.py"
    out_path.write_text(render(args.did, weights), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
