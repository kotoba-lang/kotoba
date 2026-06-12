"""Open-government-data sensors for the artificial-organism ecosystem.

Per ADR-2605263900. Five sensor families extend the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``GovOpenDataSensor`` (per-jurisdiction open-data portal)
- ``GovParliamentSensor`` (per-legislature transcripts / votes)
- ``GovBudgetSensor`` (per-jurisdiction budget + spending)
- ``GovProcurementSensor`` (per-jurisdiction tender + award)
- ``GovStatisticsSensor`` (per-IGO statistics)

Wave-1 anchor sensors (path-reserved; impl lands in W1 deliverable):

- ``us_data_gov_sensor`` (US data.gov CKAN; public domain)
- ``uk_data_gov_uk_sensor`` (UK data.gov.uk CKAN; OGL v3.0)
- ``jp_data_go_jp_sensor`` (JP data.go.jp + e-Stat; CC-BY 4.0)
- ``us_congress_gov_sensor`` (US Congress.gov bulk; public domain)
- ``uk_hansard_sensor`` (UK Hansard; OGL v3.0)
- ``jp_kokkai_kaigiroku_sensor`` (JP 国会会議録検索 bulk; free use)
- ``eu_eurostat_sensor`` (Eurostat SDMX; free re-use)
- ``worldbank_open_data_sensor`` (World Bank Open Data; CC-BY 4.0)

W2+ adds EU + FR + DE open-data + OECD + IMF + USAspending + EU TED +
SAM.gov. W3+ adds OEIL + Bundestag + Assemblée + EU FTS + 政府調達 +
UK Contracts Finder + UN Data. W4+ adds CN data with §2(g) flag.

Per-jurisdiction publication-rule honoring (parliament transcripts +
procurement awards + budget recipients are public by design across
W1-W3 jurisdictions; GDPR right-to-be-forgotten DSARs route through
chigiri.data_privacy to upstream publisher; religious-corp NEVER
performs unilateral removal).

CN data carries ``state_aligned_flag=True`` per §2(g) (parallel to
ADR-2605262800 CN NPC handling). Downstream consumers (ossekai +
manabi) MUST display the flag in any derived publication.

Passive-only invariant: sensors MUST NOT perform live portal /
parliament / budget / procurement / statistics API hits at organism-
tick time; only pre-published bulk archives via ``e7m-dataset add``.
GovWin IQ / Bloomberg Government / Politico Pro / E&E News Pro /
FiscalNote / CQ Roll Call Pro are CONSTITUTIONALLY PROHIBITED per
Charter Rider §2(e) + §2(c) (ADR-2605263900 §2 Source ladder).

Downstream consumers: ossekai (ADR-2605264000) state-function-routing-
around aggregate publication / toritate (ADR-2605262900) recipient-
vendor cross-reference via budget + procurement / chigiri
(ADR-2605262700) Charter §1.12 state-function-routing-around evidence
base / manabi civic-literacy curriculum / baien-distill civic-reasoning
specialist.
"""

from __future__ import annotations

from .base import (
    BudgetRecordKind,
    GovBudgetObservation,
    GovBudgetSensor,
    GovFacet,
    GovOpenDataObservation,
    GovOpenDataSensor,
    GovParliamentObservation,
    GovParliamentSensor,
    GovProcurementObservation,
    GovProcurementSensor,
    GovStatisticsObservation,
    GovStatisticsSensor,
    ParliamentRecordKind,
    ProcurementRecordKind,
)
from .eu_eurostat_sensor import EuEurostatSensor
from .eu_ted_sensor import EuTedSensor
from .jp_data_go_jp_sensor import JpDataGoJpSensor
from .jp_kokkai_kaigiroku_sensor import JpKokkaiKaigirokuSensor
from .uk_data_gov_uk_sensor import UkDataGovUkSensor
from .uk_hansard_sensor import UkHansardSensor
from .us_congress_gov_sensor import UsCongressGovSensor
from .us_data_gov_sensor import UsDataGovSensor
from .us_usaspending_sensor import UsUsaspendingSensor
from .worldbank_open_data_sensor import WorldBankOpenDataSensor

__all__ = [
    "BudgetRecordKind",
    "EuEurostatSensor",
    "EuTedSensor",
    "GovBudgetObservation",
    "GovBudgetSensor",
    "GovFacet",
    "GovOpenDataObservation",
    "GovOpenDataSensor",
    "GovParliamentObservation",
    "GovParliamentSensor",
    "GovProcurementObservation",
    "GovProcurementSensor",
    "GovStatisticsObservation",
    "GovStatisticsSensor",
    "JpDataGoJpSensor",
    "JpKokkaiKaigirokuSensor",
    "ParliamentRecordKind",
    "ProcurementRecordKind",
    "UkDataGovUkSensor",
    "UkHansardSensor",
    "UsCongressGovSensor",
    "UsDataGovSensor",
    "UsUsaspendingSensor",
    "WorldBankOpenDataSensor",
]
