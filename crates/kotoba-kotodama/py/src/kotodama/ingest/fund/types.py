from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

MetricKind = Literal["reported", "estimated", "derived", "unknown"]


def drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None and v != ""}


@dataclass(frozen=True)
class FundSourceConfig:
    source_id: str
    source_kind: str
    shard_key: str = "default"
    source_url: str = ""
    source_license: str = "unknown"
    mode: str = "delta"

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class RawArtifact:
    source_id: str
    artifact_kind: str
    uri: str
    sha256: str = ""
    byte_size: int | None = None
    record_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class NormalizedFundManager:
    manager_id: str
    manager_name: str
    manager_type: str = "organization"
    jurisdiction: str = ""
    domicile: str = ""
    regulator: str = ""
    legal_entity_did: str = ""
    aum_amount: float | None = None
    currency: str = "USD"
    website: str = ""
    source_url: str = ""
    source_license: str = "unknown"
    confidence: float = 0.5
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class NormalizedFund:
    fund_id: str
    name: str
    manager_id: str
    manager_name: str = ""
    fund_kind: str = "private_fund"
    strategy: str = ""
    status: str = "unknown"
    jurisdiction: str = ""
    domicile: str = ""
    vintage_year: int | None = None
    currency: str = "USD"
    aum_amount: float | None = None
    committed_capital: float | None = None
    called_capital: float | None = None
    distributed_capital: float | None = None
    dry_powder: float | None = None
    target_size: float | None = None
    source_url: str = ""
    source_license: str = "unknown"
    confidence: float = 0.5
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class NormalizedInvestor:
    investor_id: str
    investor_name: str
    investor_type: str = "lp"
    jurisdiction: str = ""
    domicile: str = ""
    legal_entity_did: str = ""
    source_url: str = ""
    source_license: str = "unknown"
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class NormalizedInvestee:
    investee_id: str
    investee_name: str
    investee_type: str = "company"
    jurisdiction: str = ""
    sector: str = ""
    ticker: str = ""
    legal_entity_did: str = ""
    source_url: str = ""
    source_license: str = "unknown"
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class FundMetric:
    subject_id: str
    metric_name: str
    value: float
    currency: str = ""
    as_of_date: str = ""
    metric_kind: MetricKind = "unknown"
    source_url: str = ""
    source_license: str = "unknown"
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return drop_none(asdict(self))


@dataclass(frozen=True)
class FundIntelBatch:
    source_id: str
    managers: list[NormalizedFundManager] = field(default_factory=list)
    funds: list[NormalizedFund] = field(default_factory=list)
    investors: list[NormalizedInvestor] = field(default_factory=list)
    investees: list[NormalizedInvestee] = field(default_factory=list)
    metrics: list[FundMetric] = field(default_factory=list)
    artifacts: list[RawArtifact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "managers": [x.to_dict() for x in self.managers],
            "funds": [x.to_dict() for x in self.funds],
            "investors": [x.to_dict() for x in self.investors],
            "investees": [x.to_dict() for x in self.investees],
            "metrics": [x.to_dict() for x in self.metrics],
            "artifacts": [x.to_dict() for x in self.artifacts],
        }
