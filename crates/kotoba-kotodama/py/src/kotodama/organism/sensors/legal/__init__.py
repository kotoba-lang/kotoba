"""Legal-corpus sensors for the artificial-organism ecosystem.

Per ADR-2605262800. Five sensor families extend the DatasetSensor Protocol
from ADR-2605262400 §3:

- ``LegalStatuteSensor`` (per jurisdiction)
- ``LegalCaseSensor`` (per court system)
- ``LegalTreatySensor`` (per corpus)
- ``LegalProcedureSensor`` (per regulatory body)
- ``LegalTemplateSensor`` (chigiri-consumable templates)

Wave-1 anchor sensors (the 5 first-class jurisdictions):

- ``us_usc_sensor`` (US Code statutes, public domain)
- ``us_cfr_sensor`` (US CFR regulations, public domain)
- ``jp_egov_sensor`` (JP e-Gov 法令, CC-BY 4.0)
- ``eu_eurlex_sensor`` (EU EUR-Lex statutes + case, free reuse)
- ``uk_legislation_sensor`` (UK legislation.gov.uk, OGL v3.0)

W2+ adds case-law / treaty / procedure / template sensors.

The judicial_party_redactor honors per-jurisdiction publication redaction
practice (German Pseudonymisierung / JP 個人情報保護法 / etc.) — chigiri
does NOT re-identify or de-anonymize.

Passive-only invariant: sensors MUST NOT perform live court-record
scraping at organism-tick time; only pre-published archives via
``e7m-dataset add``. Westlaw / LexisNexis / Bloomberg Law /
Wolters Kluwer are PROHIBITED per Charter Rider §2(e) + §2(c)
(ADR-2605262800 §2 Source ladder).
"""

from __future__ import annotations

from .base import (
    LegalCaseObservation,
    LegalCaseSensor,
    LegalProcedureObservation,
    LegalProcedureSensor,
    LegalStatuteObservation,
    LegalStatuteSensor,
    LegalTemplateObservation,
    LegalTemplateSensor,
    LegalTreatyObservation,
    LegalTreatySensor,
)
from .judicial_party_redactor import (
    JudicialPartyRedactor,
    PARTY_REDACTION_POLICY_BY_ISO3,
    PartyRedactionAction,
)
from .judiciary_corpus_sensor import JudiciaryCorpusSensor
from .procedure_corpus_sensor import ProcedureCorpusSensor
from .template_corpus_sensor import TemplateCorpusSensor
from .treaty_corpus_sensor import TreatyCorpusSensor

__all__ = [
    "JudicialPartyRedactor",
    "JudiciaryCorpusSensor",
    "ProcedureCorpusSensor",
    "TemplateCorpusSensor",
    "TreatyCorpusSensor",
    "LegalCaseObservation",
    "LegalCaseSensor",
    "LegalProcedureObservation",
    "LegalProcedureSensor",
    "LegalStatuteObservation",
    "LegalStatuteSensor",
    "LegalTemplateObservation",
    "LegalTemplateSensor",
    "LegalTreatyObservation",
    "LegalTreatySensor",
    "PARTY_REDACTION_POLICY_BY_ISO3",
    "PartyRedactionAction",
]
