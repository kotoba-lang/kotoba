"""Charter Rider §2(a)-(h) scan hook.

Binds to the canonical scanner at
``etzhayyim_organism.sensors.charter_rider`` when importable; falls back to a
minimal local regex matcher (same intent, narrower coverage) when the
``etzhayyim_organism`` package is not on ``sys.path``.

Severity ladder (kotoba_murakumo-local):

* ``clean``    — no hits
* ``minor``    — single hit only in ``§2(c)`` Surveillance-Capitalism advisory
                 patterns ("ad sense", "promo code", …) — heuristic, often a
                 false positive in scholarly writing
* ``major``    — any hit in §2(a) Weapons, §2(b) Speculative Finance,
                 §2(d) Fossil Fuel, §2(f) Multi-Gen Harm, §2(h) Wellbecoming
                 Subordination, OR multiple hits in any §2 section
* ``critical`` — §2(a) Weapons OR §2(f) Multi-Gen Harm with > 1 hit

When ``KOTOBA_MURAKUMO_CHARTER_ENFORCE`` env var is truthy ("1", "true",
"yes"; case-insensitive), :func:`scan` returning severity ``major`` or
higher triggers :class:`kotoba_murakumo.exceptions.CharterViolation` at the
:func:`enforce` call-site. Default (no env, or "false"/"0"): advisory only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal

from .exceptions import CharterViolation

Side = Literal["input", "output"]
Severity = Literal["clean", "minor", "major", "critical"]


@dataclass(frozen=True, slots=True)
class CharterScanResult:
    side: Side
    severity: Severity
    findings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.severity == "clean"


# ---------- canonical scanner binding -----------------------------------------

try:
    from etzhayyim_organism.sensors.charter_rider import scan as _canonical_scan
    _HAVE_CANONICAL = True
except ImportError:
    _canonical_scan = None  # type: ignore[assignment]
    _HAVE_CANONICAL = False


# ---------- local fallback (used when etzhayyim_organism not installed) -------

_MINOR_ONLY_PATTERN = re.compile(
    r"(ad ?sense|ad ?words|meta pixel|google analytics|"
    r"affiliate link|sponsored post|promo code|discount code|"
    r"limited time offer|click here to (buy|sign up))",
    re.IGNORECASE,
)
_MAJOR_PATTERN = re.compile(
    r"(\bweapon|\bmunition|grenade|warhead|ballistic missile|"
    r"battle tank|combat drone|combat aircraft|biological weapon|"
    r"chemical weapon|nerve agent|cluster munition|landmine|"
    r"prediction market|leverage[d]?\s+derivative|perpetual swap|"
    r"naked option|crypto casino|degen yield farm|memecoin pump|"
    r"new (oil|gas) (well|field|drilling|extraction)|"
    r"greenfield (oil|coal|gas)|tar sands|oil sands|fracking expansion|"
    r"addictive (design|loop)|infinite scroll engagement|"
    r"exploit (children|minor)|groom(ing)? (children|minor)|"
    r"non-consensual|deepfake (porn|sexual)|"
    r"maximi[sz]e (user )?(engagement|retention|screen time))",
    re.IGNORECASE,
)
_CRITICAL_PATTERN = re.compile(
    r"(\bweapon|\bmunition|grenade|warhead|ballistic missile|"
    r"battle tank|combat drone|combat aircraft|biological weapon|"
    r"chemical weapon|nerve agent|cluster munition|landmine|"
    r"CSAM|exploit (children|minor)|groom(ing)? (children|minor)|"
    r"deepfake (porn|sexual)|non-consensual)",
    re.IGNORECASE,
)


def _local_scan(text: str) -> tuple[Severity, list[str]]:
    if not text:
        return "clean", []
    crit = _CRITICAL_PATTERN.findall(text)
    if len(crit) > 1 or (crit and any("weapon" in str(c).lower() for c in crit)):
        return "critical", [str(c) for c in crit[:5]]
    if crit:
        return "major", [str(c) for c in crit[:5]]
    major = _MAJOR_PATTERN.findall(text)
    if major:
        return "major", [str(m) for m in major[:5]]
    minor = _MINOR_ONLY_PATTERN.findall(text)
    if minor:
        return "minor", [str(m) for m in minor[:5]]
    return "clean", []


# ---------- public API --------------------------------------------------------

def scan(text: str, *, side: Side) -> CharterScanResult:
    """Scan text against Charter Rider §2(a)-(h).

    Returns a :class:`CharterScanResult` regardless of severity. Use
    :func:`enforce` (or the env-flag-driven wrapper in
    :mod:`kotoba_murakumo.function`) to actually raise on a violation.
    """
    if _HAVE_CANONICAL and _canonical_scan is not None:
        r = _canonical_scan(text)
        if r.ok:
            return CharterScanResult(side=side, severity="clean")
        # Map canonical hit set → severity.
        sections = [h.section for h in r.hits]
        section_set = set(sections)
        critical_sections = {"§2(a)", "§2(f)"}
        findings = tuple(f"{h.section}:{h.term}" for h in r.hits[:5])
        if section_set & critical_sections and len(r.hits) > 1:
            return CharterScanResult(side=side, severity="critical", findings=findings)
        if section_set - {"§2(c)"}:
            return CharterScanResult(side=side, severity="major", findings=findings)
        return CharterScanResult(side=side, severity="minor", findings=findings)

    severity, findings = _local_scan(text)
    return CharterScanResult(side=side, severity=severity, findings=tuple(findings))


def is_enforce_enabled() -> bool:
    """Read ``KOTOBA_MURAKUMO_CHARTER_ENFORCE`` once per call.

    Truthy values: ``"1"``, ``"true"``, ``"yes"`` (case-insensitive).
    Anything else (including unset) means advisory only.
    """
    val = os.environ.get("KOTOBA_MURAKUMO_CHARTER_ENFORCE", "")
    return val.strip().lower() in {"1", "true", "yes"}


def enforce(result: CharterScanResult) -> None:
    """Raise :class:`CharterViolation` iff enforce flag is on and severity >= major.

    Constitutional invariant (ADR-2605192200 + ADR-2605282000): once enforce
    flips on, .remote() callers MUST NOT receive a result whose input or
    output triggered a major-or-worse Charter scan finding.
    """
    if not is_enforce_enabled():
        return
    if result.severity in {"major", "critical"}:
        raise CharterViolation(
            f"Charter Rider §2 violation on {result.side}: "
            f"severity={result.severity}, findings={list(result.findings)}",
            side=result.side,
            severity=result.severity,
        )
