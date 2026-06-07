"""Judicial-party redaction policy (jurisdiction-dependent).

Per ADR-2605262800 §6. chigiri does NOT re-identify or de-anonymize.
This module honors per-jurisdiction publication-redaction practice:

- Some jurisdictions publish parties named (US / UK / IN / BR / CA / AU)
- Some pseudonymize at publication (DE / FR / JP / CN)
- Some honor on-request anonymization (ECHR HUDOC)
- Some are strict-anonymized (JP 家庭裁判所 / 少年裁判所)

Right-to-be-forgotten DSARs (GDPR Art. 17, CCPA) route through chigiri's
``data_privacy`` cell (R2+) to upstream publishers; this module does NOT
unilaterally remove already-published opinions.

Non-party PII (random emails / phone / postal addresses in court
exhibits) is handled by the general ``../pii_filter.py`` which runs in
the same ingestion pass.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Mapping


class PartyRedactionAction(enum.Enum):
    """How to handle party names in a case observation."""

    PASS_THROUGH = "pass-through"
    """Parties named in upstream publication; preserve as-is (US / UK / etc.)."""

    PASS_THROUGH_PSEUDONYMIZED = "pass-through-pseudonymized"
    """Upstream publication is pseudonymized; preserve pseudonymized form (DE / FR / JP / CN)."""

    HONOR_UPSTREAM_ANONYMIZATION = "honor-upstream-anonymization"
    """Anonymization is on-request upstream; if upstream marks anonymized, preserve; otherwise pass-through (ECHR)."""

    REJECT_IF_NON_ANONYMIZED = "reject-if-non-anonymized"
    """Strict anonymization required; reject observation if upstream record is non-anonymized (JP family/juvenile court)."""


# Per-jurisdiction policy table. ISO-3 jurisdiction code → action.
# Special supra-jurisdictional entries: "EU", "COE", "ICJ", "ICC", "IHL", "UN".
PARTY_REDACTION_POLICY_BY_ISO3: Mapping[str, PartyRedactionAction] = {
    "USA": PartyRedactionAction.PASS_THROUGH,
    "GBR": PartyRedactionAction.PASS_THROUGH,
    "IND": PartyRedactionAction.PASS_THROUGH,
    "BRA": PartyRedactionAction.PASS_THROUGH,
    "CAN": PartyRedactionAction.PASS_THROUGH,
    "AUS": PartyRedactionAction.PASS_THROUGH,
    "EU": PartyRedactionAction.PASS_THROUGH,
    "ICJ": PartyRedactionAction.PASS_THROUGH,
    "ICC": PartyRedactionAction.PASS_THROUGH,
    "DEU": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "FRA": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "JPN": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "CHN": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "ITA": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "KOR": PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED,
    "COE": PartyRedactionAction.HONOR_UPSTREAM_ANONYMIZATION,
    "ECHR": PartyRedactionAction.HONOR_UPSTREAM_ANONYMIZATION,
    "UN": PartyRedactionAction.PASS_THROUGH,
    "IHL": PartyRedactionAction.PASS_THROUGH,
}

# Court-system specific overrides (more specific than jurisdiction default).
PARTY_REDACTION_POLICY_BY_COURT_SYSTEM: Mapping[str, PartyRedactionAction] = {
    "jp-family-court": PartyRedactionAction.REJECT_IF_NON_ANONYMIZED,
    "jp-juvenile-court": PartyRedactionAction.REJECT_IF_NON_ANONYMIZED,
    "us-juvenile-court-state": PartyRedactionAction.REJECT_IF_NON_ANONYMIZED,
    "gb-family-division": PartyRedactionAction.HONOR_UPSTREAM_ANONYMIZATION,
}


@dataclass
class JudicialPartyRedactor:
    """Apply jurisdiction-dependent party redaction to a case observation.

    Wave-1 contract: the redactor takes raw ``(parties_tuple, jurisdiction_iso3,
    court_system, upstream_anonymized_flag)`` and returns
    ``(parties_tuple_after_policy, dropped)`` where ``dropped=True`` means
    the observation should be skipped (REJECT_IF_NON_ANONYMIZED + non-
    anonymized upstream).

    The redactor does NOT itself do entity detection — it trusts the
    upstream publication. If a future use case demands entity-level NER
    on case bodies, a separate ADR with Council Lv6+ approval is required
    (that path opens new privacy concerns beyond this ADR's scope).
    """

    default_action: PartyRedactionAction = PartyRedactionAction.PASS_THROUGH

    def lookup(
        self, *, jurisdiction_iso3: str, court_system: str | None = None
    ) -> PartyRedactionAction:
        """Resolve the applicable action for a (jurisdiction, court_system) pair."""
        if court_system is not None and court_system in PARTY_REDACTION_POLICY_BY_COURT_SYSTEM:
            return PARTY_REDACTION_POLICY_BY_COURT_SYSTEM[court_system]
        return PARTY_REDACTION_POLICY_BY_ISO3.get(jurisdiction_iso3, self.default_action)

    def apply(
        self,
        *,
        parties: tuple[str, ...],
        jurisdiction_iso3: str,
        court_system: str | None,
        upstream_anonymized: bool,
    ) -> tuple[tuple[str, ...], bool]:
        """Return ``(parties_after_policy, dropped)``.

        ``dropped=True`` means: caller should NOT yield this observation
        (REJECT_IF_NON_ANONYMIZED + upstream_anonymized=False).
        """
        action = self.lookup(jurisdiction_iso3=jurisdiction_iso3, court_system=court_system)
        if action == PartyRedactionAction.PASS_THROUGH:
            return parties, False
        if action == PartyRedactionAction.PASS_THROUGH_PSEUDONYMIZED:
            # Upstream pseudonymized; we trust it. If it isn't, that's an
            # upstream data-quality issue not addressable by this layer.
            return parties, False
        if action == PartyRedactionAction.HONOR_UPSTREAM_ANONYMIZATION:
            if upstream_anonymized:
                # Replace each party name with the upstream-provided
                # anonymization marker (the upstream fetcher should
                # already have done this; we re-affirm).
                return tuple("[anonymized]" for _ in parties), False
            return parties, False
        if action == PartyRedactionAction.REJECT_IF_NON_ANONYMIZED:
            if upstream_anonymized:
                return tuple("[anonymized]" for _ in parties), False
            # Strict-anonymized jurisdiction; reject if upstream did not
            # anonymize (caller-side: do not yield observation).
            return parties, True
        return parties, False


__all__ = [
    "JudicialPartyRedactor",
    "PARTY_REDACTION_POLICY_BY_COURT_SYSTEM",
    "PARTY_REDACTION_POLICY_BY_ISO3",
    "PartyRedactionAction",
]
