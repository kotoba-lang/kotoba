"""Corporate-disclosure sensors for the artificial-organism ecosystem.

Per ADR-2605263800. Five sensor families extend the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``CorpRegistrySensor`` (per-jurisdiction legal-entity registry)
- ``CorpDisclosureSensor`` (per-jurisdiction periodic financial filings)
- ``LeiSensor`` (GLEIF LEI canonical + relationship, global cross-juris)
- ``CorpOwnershipSensor`` (UBO / parent-subsidiary / control graph)
- ``CorpFilingEventSensor`` (material-event filings; low-latency hot-path)

Wave-1 anchor sensors (path-reserved; impl lands in W1 deliverable):

- ``sec_edgar_sensor`` (US SEC EDGAR companyfacts + Submissions; PD)
- ``jp_edinet_sensor`` (JP 金融庁 EDINET XBRL bulk; 金融庁 open ToU)
- ``uk_companies_house_sensor`` (UK Companies House FCD bulk; OGL v3.0)
- ``gleif_lei_sensor`` (GLEIF Concatenated Files L1+L2; CC0 1.0)

W2+ adds SEDAR+ / ASIC / Unternehmensregister / INFOGREFFE.
W3+ adds SEC EDGAR RSS + EDINET API filing-event sensors +
OpenCorporates Tier-B open-data fork.
W4+ adds EU per-member-state OAM + US FinCEN BOI (deferred).

Per-jurisdiction publication-redaction policy honors upstream rules
(SEC pass-through / Companies House pass-through / EDINET pass-through /
EU member-state per-state honor / GDPR right-to-be-forgotten DSARs route
through chigiri.data_privacy to upstream publisher).

Passive-only invariant: sensors MUST NOT perform live registry scraping
at organism-tick time; only pre-published bulk archives via
``e7m-dataset add``. Bloomberg Terminal / S&P Capital IQ / Refinitiv
Eikon / FactSet / Moody's Orbis / D&B Hoovers / Pitchbook / Crunchbase
Pro are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e) + §2(c)
(ADR-2605263800 §2 Source ladder).

Downstream consumers: ossekai (ADR-2605264000) aggregate-anonymized
publication / toritate (ADR-2605262900) recipient-vendor cross-reference /
chigiri (ADR-2605262700) external-counsel routing / manabi financial-
literacy curriculum / baien-distill financial-literacy specialist.
"""

from __future__ import annotations

from .base import (
    CorpDisclosureObservation,
    CorpDisclosureSensor,
    CorpFilingEventObservation,
    CorpFilingEventSensor,
    CorpOwnershipObservation,
    CorpOwnershipSensor,
    CorpRegistryObservation,
    CorpRegistrySensor,
    FormClass,
    LeiObservation,
    LeiSensor,
    OwnershipKind,
)
from .gleif_l2_ownership_sensor import GleifL2OwnershipSensor
from .jp_edinet_sensor import JpEdinetSensor
from .lei_sensor import GleifLeiSensor
from .sec_edgar_sensor import SecEdgarSensor
from .uk_companies_house_sensor import UkCompaniesHouseSensor

__all__ = [
    "CorpDisclosureObservation",
    "CorpDisclosureSensor",
    "CorpFilingEventObservation",
    "CorpFilingEventSensor",
    "CorpOwnershipObservation",
    "CorpOwnershipSensor",
    "CorpRegistryObservation",
    "CorpRegistrySensor",
    "FormClass",
    "GleifL2OwnershipSensor",
    "GleifLeiSensor",
    "JpEdinetSensor",
    "LeiObservation",
    "LeiSensor",
    "OwnershipKind",
    "SecEdgarSensor",
    "UkCompaniesHouseSensor",
]
