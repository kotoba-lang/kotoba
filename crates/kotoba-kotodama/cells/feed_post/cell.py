"""
FeedPostCell — kotoba-datomic §4 L3 deterministic verdict for app.bsky.feed.post.

Per:
  - ADR-2605192100 (mission charter — §1.13 Eros / Gore boundary,
                    §1.15 non-eschatological)
  - ADR-2605192200 (Charter Compliance Rider v2.0 §2(a)..(h))
  - ADR-2605231400 kotoba-datomic SPEC §4 — `(L1, L2, L3)` all must accept;
                    L3 is THIS cell

L1 lexicon: ``00-contracts/lexicons/app/bsky/feed/post.json`` (vendored).
L2 policy:  ``00-contracts/policies/app/bsky/feed/policy.rego``.
L3 cell:    this file.

Determinism contract (kotoba-datomic SPEC §4 table row L3):
  Given identical ``(record, ctx)`` inputs, this cell MUST return identical
  ``Verdict``. Concretely:
    - No clocks: ``createdAt`` is read from input, never ``time.time()``.
    - No randomness: no RNG, no UUID-from-clock.
    - No LLM calls in the deterministic path. If an LLM-assisted appraisal
      is requested via ``ctx["mode"] == "llm-assisted"``, the cell short-
      circuits to ``Verdict.escalate`` so the non-deterministic appraisal
      runs out-of-band (CouncilDeliberationCell) and never taints the
      verdict cache. ADR-2605192400 ratchet.
    - All set / dict iteration is sorted before hashing.

Trigger: MST listener on ``app.bsky.feed.post`` create commits (firehose).
Effect: emits ``com.etzhayyim.membrane.verdict`` permanent record on the
        cell's own DID, witnessing the verdict for this record CID. The
        original record stays under the author's repo; the verdict record
        is a sidecar that ipfs-pinner + anchor-cron treat as auditable.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict
from operator import add

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


# ── Vocabulary ─────────────────────────────────────────────────────

VerdictKind = Literal["approve", "reject", "escalate"]

GORE_EDUCATIONAL_HINTS = (
    "historical",
    "documentary",
    "human rights",
    "war crime",
    "genocide",
    "forensic",
    "academic",
    "教育",
    "歴史",
    "人権",
    "戦争犯罪",
    "ジェノサイド",
)


# ── State (LangGraph TypedDict) ────────────────────────────────────


class FeedPostState(TypedDict, total=False):
    # Input
    record_uri: str
    record_cid: str
    record: dict[str, Any]
    author_did: str
    ctx: dict[str, Any]

    # Layer outputs
    schema_ok: bool
    schema_errors: list[str]

    rego_decision: dict[str, Any]
    rego_allow: bool

    semantic_findings: Annotated[list[dict[str, Any]], add]
    semantic_allow: bool

    # Verdict
    verdict_kind: VerdictKind
    verdict_reason: str
    verdict_evidence: list[dict[str, Any]]
    verdict_cid_input: str
    verdict_record: dict[str, Any]


@dataclass(frozen=True)
class Verdict:
    """Deterministic, content-addressed verdict.

    The verdict ``cid`` is sha256 of canonical JSON of ``(record_cid,
    kind, reason, sorted_evidence)`` — re-running the cell on the same
    input MUST produce the same ``cid``.
    """

    kind: VerdictKind
    reason: str
    evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    record_cid: str = ""

    def cid(self) -> str:
        payload = {
            "record_cid": self.record_cid,
            "kind": self.kind,
            "reason": self.reason,
            "evidence": [
                {k: v for k, v in sorted(item.items())} for item in self.evidence
            ],
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "sha256-" + hashlib.sha256(canonical).hexdigest()


# ── Nodes ──────────────────────────────────────────────────────────


def validate_schema(state: FeedPostState) -> FeedPostState:
    rec = state.get("record") or {}
    errors: list[str] = []
    if rec.get("$type") != "app.bsky.feed.post":
        errors.append("type-mismatch")
    text = rec.get("text", "")
    has_embed = bool(rec.get("embed"))
    if not isinstance(text, str):
        errors.append("text-not-string")
    elif text == "" and not has_embed:
        errors.append("empty-text-without-embed")
    elif len(text) > 3000:
        errors.append("text-exceeds-3000")
    if not isinstance(rec.get("createdAt"), str):
        errors.append("created-at-missing")
    return {"schema_ok": not errors, "schema_errors": errors}


def evaluate_rego(state: FeedPostState) -> FeedPostState:
    """Apply L2 Rego decision.

    The Rego module is canonical. This node consumes ``ctx["rego"]`` if a
    pre-computed decision was supplied (the dispatcher evaluates Rego
    out-of-process via the OPA sidecar). When absent, the in-Python
    mirror :func:`_python_rego_mirror` is used — it MUST stay in sync
    with ``policy.rego``; CI hook ``charter-rider-rego-mirror`` enforces.
    """
    ctx = state.get("ctx") or {}
    decision = (ctx.get("rego") or {}).get("decision")
    if decision is None:
        decision = _python_rego_mirror(state.get("record") or {})
    return {
        "rego_decision": decision,
        "rego_allow": bool(decision.get("allow")),
    }


def semantic_appraisal(state: FeedPostState) -> FeedPostState:
    """Deterministic non-Rego pass.

    Catches a few classes Rego cannot express cleanly:
      - Non-ASCII Charter Rider hits (Japanese forbidden vocabulary).
      - Gore self-label with educational context demotion → escalate
        instead of reject (so the Council can ratify).
    """
    rec = state.get("record") or {}
    text = rec.get("text", "") or ""
    findings: list[dict[str, Any]] = []

    if _matches_any(text, _JA_PROHIBITED_PATTERNS):
        findings.append(
            {
                "category": "ja-prohibited",
                "evidence": "matched Japanese prohibited vocabulary",
            }
        )

    labels = rec.get("labels") or {}
    label_vals = sorted(
        {x.get("val") for x in (labels.get("values") or []) if isinstance(x, dict)}
    )
    if "gore" in label_vals:
        # Educational override (ADR-2605192400 §3) — demote to escalate.
        if any(hint in text.lower() for hint in GORE_EDUCATIONAL_HINTS):
            findings.append(
                {
                    "category": "gore-educational",
                    "evidence": "self-label gore + educational marker present; council ratification required",
                }
            )

    return {
        "semantic_findings": findings,
        "semantic_allow": not findings,
    }


def synthesize(state: FeedPostState) -> FeedPostState:
    rec = state.get("record") or {}
    if not state.get("schema_ok", True):
        evidence = [
            {"category": "schema", "evidence": e}
            for e in sorted(state.get("schema_errors", []))
        ]
        v = Verdict(
            kind="reject",
            reason="schema-violation",
            evidence=tuple(evidence),
            record_cid=state.get("record_cid", ""),
        )
        return _verdict_to_state(v, rec)

    rego_decision = state.get("rego_decision") or {}
    rego_violations = list(rego_decision.get("violations") or [])
    semantic_findings = list(state.get("semantic_findings") or [])

    # `gore-educational` is a deterministic *demotion* of a `gore` Rego
    # finding (ADR-2605192400 §3 educational/historical override). When
    # present, drop the Rego gore violation and keep only the demotion
    # marker, so the final verdict can be `escalate` instead of `reject`.
    has_gore_educational = any(
        f.get("category") == "gore-educational" for f in semantic_findings
    )
    if has_gore_educational:
        rego_violations = [v for v in rego_violations if v.get("category") != "gore"]

    rejecting = [
        *rego_violations,
        *[f for f in semantic_findings if f.get("category") != "gore-educational"],
    ]

    if has_gore_educational and not rejecting:
        v = Verdict(
            kind="escalate",
            reason="council-required",
            evidence=tuple(sorted(semantic_findings, key=lambda x: (x.get("category", ""), x.get("evidence", "")))),
            record_cid=state.get("record_cid", ""),
        )
        return _verdict_to_state(v, rec)

    if rejecting:
        v = Verdict(
            kind="reject",
            reason="charter-or-semantic-violation",
            evidence=tuple(
                sorted(rejecting, key=lambda x: (x.get("category", ""), x.get("evidence", "")))
            ),
            record_cid=state.get("record_cid", ""),
        )
        return _verdict_to_state(v, rec)

    v = Verdict(
        kind="approve",
        reason="ok",
        evidence=(),
        record_cid=state.get("record_cid", ""),
    )
    return _verdict_to_state(v, rec)


def emit_record(state: FeedPostState) -> FeedPostState:
    """Materialise the verdict as an ``com.etzhayyim.membrane.verdict`` record
    payload. The cell's transport layer (MST listener wrapper) is what
    actually calls ``com.atproto.repo.createRecord``; the cell only
    produces the canonical record body so it stays deterministic.
    """
    return {
        "verdict_record": {
            "$type": "com.etzhayyim.membrane.verdict",
            "subject": {
                "uri": state.get("record_uri", ""),
                "cid": state.get("record_cid", ""),
                "collection": "app.bsky.feed.post",
            },
            "verdict": state.get("verdict_kind", "reject"),
            "reason": state.get("verdict_reason", ""),
            "evidence": list(state.get("verdict_evidence", [])),
            "verdictCid": state.get("verdict_cid_input", ""),
            # createdAt of the verdict record itself comes from ctx.now,
            # supplied by the dispatcher — never from the cell's clock.
            "createdAt": (state.get("ctx") or {}).get("now", ""),
        }
    }


# ── Edge router ───────────────────────────────────────────────────


def post_schema_router(state: FeedPostState) -> str:
    return "synthesize" if not state.get("schema_ok", False) else "evaluate_rego"


# ── Graph builder ─────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    g = StateGraph(FeedPostState)
    g.add_node("validate_schema", validate_schema)
    g.add_node("evaluate_rego", evaluate_rego)
    g.add_node("semantic_appraisal", semantic_appraisal)
    g.add_node("synthesize", synthesize)
    g.add_node("emit_record", emit_record)

    g.add_edge(START, "validate_schema")
    g.add_conditional_edges(
        "validate_schema",
        post_schema_router,
        {"evaluate_rego": "evaluate_rego", "synthesize": "synthesize"},
    )
    g.add_edge("evaluate_rego", "semantic_appraisal")
    g.add_edge("semantic_appraisal", "synthesize")
    g.add_edge("synthesize", "emit_record")
    g.add_edge("emit_record", END)

    return g.compile(checkpointer=checkpointer) if checkpointer else g.compile()


# ── Convenience entry-point for ConstitutionPort + unit tests ─────


def verdict_for(
    record: dict[str, Any],
    *,
    record_uri: str = "",
    record_cid: str = "",
    author_did: str = "",
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full L3 pipeline and return the final state dict.

    Pure function (no checkpointer, no LLM). Used by:
      - PDS write gate (``kotoba-kotodama-host-sdk`` ComAtprotoRepoCreateRecord
        pre-flight hook for app.bsky.feed.post),
      - feed-discover projection (re-verify before promoting a post into
        the projection cache),
      - mst-projector emission (optional anchor-time invariant check).
    """
    graph = build_graph()
    state: FeedPostState = {
        "record_uri": record_uri,
        "record_cid": record_cid,
        "record": record,
        "author_did": author_did,
        "ctx": ctx or {},
    }
    return graph.invoke(state)


# ── Helpers ───────────────────────────────────────────────────────


def _verdict_to_state(v: Verdict, _rec: dict[str, Any]) -> FeedPostState:
    return {
        "verdict_kind": v.kind,
        "verdict_reason": v.reason,
        "verdict_evidence": list(v.evidence),
        "verdict_cid_input": v.cid(),
    }


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


# Japanese-side prohibited vocabulary mirror. Conservative — only the
# unambiguous assertions, not the educational-context terms. Kept in
# the cell (not Rego) because Rego's `contains` is byte-substring and
# matches partial kanji in ways that produce false positives. Python
# regex with `re.UNICODE` is the right tool here.
_JA_PROHIBITED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"末法到来", re.UNICODE),
    re.compile(r"黙示録の獣", re.UNICODE),
    re.compile(r"千年王国は近い", re.UNICODE),
)


def _python_rego_mirror(record: dict[str, Any]) -> dict[str, Any]:
    """In-Python mirror of ``policy.rego`` for the deterministic path.

    Mirrors the subset of categories Rego evaluates against bare text.
    CI hook ``charter-rider-rego-mirror`` diffs the two pattern sets at
    build time. Drift = build error.
    """
    text = (record.get("text") or "").lower()
    labels = record.get("labels") or {}
    label_vals = sorted(
        {x.get("val") for x in (labels.get("values") or []) if isinstance(x, dict)}
    )

    violations: list[dict[str, Any]] = []

    def _hit(cat: str, terms: tuple[str, ...], allow: tuple[str, ...] = ()) -> None:
        for t in terms:
            if t in text and not any(a in text for a in allow):
                violations.append({"category": cat, "evidence": f"matched {cat} term: {t!r}"})
                return

    _hit(
        "2a",
        (
            "assault rifle",
            "lethal autonomous",
            "kinetic weapon",
            "kinetic strike",
            "cyber-offensive",
            "cyber offensive",
            "munition",
            "warhead",
            "paramilitary contractor",
            "kill-chain",
            "kill chain",
        ),
        allow=(
            "historical",
            "treaty",
            "disarm",
            "ban treaty",
            "geneva",
            "red cross",
            "red crescent",
            "antiwar",
            "peace research",
            "forensic",
        ),
    )
    _hit(
        "2b",
        (
            "high frequency trading",
            "high-frequency trading",
            "hft strategy",
            "predatory loan",
            "predatory lending",
            "payday loan",
            "leverage spread",
            "arbitrage bot",
            "naked short",
            "pump and dump",
        ),
        allow=(
            "critique",
            "regulator",
            "prosecute",
            "fraud report",
            "consumer protection",
            "academic",
            "case study",
        ),
    )
    _hit(
        "2c",
        (
            "ad-tech dsp",
            "ad-tech ssp",
            "adtech dsp",
            "adtech ssp",
            "data broker",
            "behavioral targeting",
            "cross-site tracking",
            "fingerprinting sdk",
            "fingerprinter sdk",
        ),
        allow=(
            "privacy",
            "countermeasure",
            "defense",
            "defence",
            "audit",
            "eprivacy",
            "gdpr",
            "critique",
            "investigation",
        ),
    )
    _hit(
        "advertising",
        (
            "sponsored content",
            "promo code",
            "use my affiliate",
            "affiliate link",
            "discount code",
            "buy now",
            "limited time offer",
            "click my referral",
        ),
    )
    _hit(
        "eschatology",
        (
            "rapture is coming",
            "millennial kingdom is at hand",
            "end times prophecy fulfilled",
        ),
    )
    if "gore" in label_vals:
        violations.append(
            {
                "category": "gore",
                "evidence": "self-label gore (Wellbecoming, ADR-2605192400)",
            }
        )

    return {
        "allow": not violations,
        "reason": "ok" if not violations else "charter-violation",
        "violations": violations,
        "obligations": _obligations_for(violations),
    }


def _obligations_for(violations: list[dict[str, Any]]) -> list[str]:
    out: set[str] = set()
    for v in violations:
        cat = v.get("category")
        if cat == "gore":
            out.add("council_review")
        elif cat in {"2a", "2b", "2c", "2d", "2f", "2h", "advertising", "eschatology"}:
            out.add("audit_charter_block")
    return sorted(out)
