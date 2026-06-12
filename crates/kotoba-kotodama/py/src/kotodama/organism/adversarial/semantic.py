
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class SemanticScanResult:
    """Result of an L2 semantic adversarial scan."""
    suspicious: bool = False
    severity: Literal["none", "low", "medium", "high"] = "none"
    flagged_patterns: list[str] = field(default_factory=list)
    reason: str = ""


# L2 Semantic Threat Patterns
# (a) Prompt injection
PROMPT_INJECTION_PATTERNS = {
    "ignore_instructions": re.compile(r"ignore\s+(?:(?:previous|prior|above)\s+)?(?:instructions?|prompts?)", re.IGNORECASE),
    "disregard_above": re.compile(r"disregard\s+(?:above|prior|the)?", re.IGNORECASE),
    "system_command": re.compile(r"^\s*system\s*:", re.IGNORECASE),
    "user_end_tag": re.compile(r"<\s*/\s*user\s*>", re.IGNORECASE),
    "you_are_now": re.compile(r"you\s+are\s+now", re.IGNORECASE),
    "new_persona": re.compile(r"act\s+as\s+(?:if\s+)?[A-Za-z]+", re.IGNORECASE),
    "reveal_secrets": re.compile(r"reveal\s+(your\s+)?(?:secrets|prompt|instructions)", re.IGNORECASE),
}

# (b) Hidden markers
HIDDEN_MARKER_PATTERNS = {
    "admin_override": re.compile(r"\[\s*(?:(?:ADMIN|OVERRIDE|ROOT|SUDO|DEBUG)[\s_]*)+\]", re.IGNORECASE),
}

# (c) Forged attribution
FORGED_ATTRIBUTION_PATTERN = re.compile(r"did:(?:web|plc):\S+", re.IGNORECASE)

# (d) Charter §2 violation keywords (sketch)
CHARTER_VIOLATION_KEYWORDS = {
    "weapon": re.compile(r"\b(weapon|兵器|munition)\b", re.IGNORECASE),
    "surveillance": re.compile(r"\b(surveillance|監視|monitor|track)\b", re.IGNORECASE),
    "identification": re.compile(r"\b(identification|識別|identify)\b", re.IGNORECASE),
    "analysis_for_control": re.compile(r"\b(analyze|解析)\s+for\s+(control|domination)\b", re.IGNORECASE),
}


def scan_semantic(text: str, actor_did: str | None = None) -> SemanticScanResult:
    """
    Performs an L2 semantic scan on the input text for adversarial patterns.

    Args:
        text: The input text to scan.
        actor_did: The DID of the actor who created the observation.

    Returns:
        A SemanticScanResult object.
    """
    if not text:
        return SemanticScanResult(suspicious=False)

    flagged_patterns = []
    found_severities = set()

    # (a) Prompt injection
    for name, pattern in PROMPT_INJECTION_PATTERNS.items():
        if pattern.search(text):
            flagged_patterns.append(f"prompt_injection:{name}")
            found_severities.add("medium")

    # (b) Hidden markers
    for name, pattern in HIDDEN_MARKER_PATTERNS.items():
        if pattern.search(text):
            flagged_patterns.append(f"hidden_marker:{name}")
            found_severities.add("medium")

    # (c) Forged attribution
    if actor_did:
        for match in FORGED_ATTRIBUTION_PATTERN.finditer(text):
            found_did = match.group(0)
            if found_did != actor_did:
                flagged_patterns.append(f"forged_attribution:{found_did}")
                found_severities.add("high")

    # (d) Charter §2 keywords — always flag (low severity, low confidence)
    # Per H R0 §3 invariant: any Charter §2 keyword mention is worth flagging
    # for human review, regardless of negation context (negation may be
    # adversarial reframing).
    for name, pattern in CHARTER_VIOLATION_KEYWORDS.items():
        if pattern.search(text):
            flagged_patterns.append(f"charter_violation:{name}")
            found_severities.add("low")


    if not found_severities:
        return SemanticScanResult()

    # Calculate final severity
    final_severity: Literal["none", "low", "medium", "high"] = "none"
    if "high" in found_severities:
        final_severity = "high"
    elif "medium" in found_severities:
        final_severity = "medium"
    elif "low" in found_severities:
        final_severity = "low"

    # Refine severity
    if "medium" in found_severities and "high" in found_severities:
        final_severity = "high"

    if len(flagged_patterns) > 2 and "medium" in found_severities:
        final_severity = "high" if final_severity == "medium" else final_severity # Escalate medium to high if many patterns match


    reason = f"L2 scan flagged patterns: {', '.join(flagged_patterns)}"

    return SemanticScanResult(
        suspicious=True,
        severity=final_severity,
        flagged_patterns=flagged_patterns,
        reason=reason,
    )
