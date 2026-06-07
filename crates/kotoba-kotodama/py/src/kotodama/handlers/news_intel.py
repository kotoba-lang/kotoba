"""
news.etzhayyim.com intel scoring UDFs.

These functions are deliberately deterministic and side-effect free. The
Worker can call the same scoring model through RisingWave when available,
while keeping a TypeScript fallback for degraded operation.
"""

from __future__ import annotations

from kotodama import udf


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@udf(
    nsid="news_source_credibility",
    io_threads=16,
    input_types=["VARCHAR", "BOOLEAN", "BOOLEAN"],
    result_type="FLOAT64",
    capability_tags=("news", "intel", "source-scoring"),
    agent_tool="Score news source credibility from type and primary/official flags.",
)
def source_credibility(source_type: str, primary_source: bool, official_source: bool) -> float:
    normalized_type = (source_type or "").strip().lower()
    base_by_type = {
        "regulator": 0.88,
        "government": 0.86,
        "multilateral": 0.84,
        "company_ir": 0.80,
        "exchange": 0.78,
        "standards_body": 0.76,
        "research": 0.72,
        "wire": 0.62,
        "media": 0.55,
        "social": 0.35,
    }
    score = base_by_type.get(normalized_type, 0.50)
    if official_source:
        score += 0.10
    if primary_source:
        score += 0.08
    return round(_clamp01(score), 4)


@udf(
    nsid="news_intel_priority",
    io_threads=16,
    input_types=["INT", "INT", "INT", "FLOAT64", "FLOAT64"],
    result_type="FLOAT64",
    capability_tags=("news", "intel", "priority-scoring"),
    agent_tool="Score intel priority from evidence, official corroboration, recency, and impact.",
)
def intel_priority(
    evidence_count: int,
    official_count: int,
    corroborated_count: int,
    recency_hours: float,
    impact: float,
) -> float:
    evidence = max(0, int(evidence_count or 0))
    official = max(0, int(official_count or 0))
    corroborated = max(0, int(corroborated_count or 0))

    try:
        recency = max(0.0, float(recency_hours or 0.0))
    except (TypeError, ValueError):
        recency = 0.0
    try:
        impact_score = _clamp01(float(impact or 0.0))
    except (TypeError, ValueError):
        impact_score = 0.0

    evidence_score = min(0.24, evidence * 0.06)
    official_score = min(0.24, official * 0.12)
    corroboration_score = min(0.20, corroborated * 0.10)
    recency_score = max(0.0, 0.16 - min(recency, 72.0) / 72.0 * 0.16)

    score = 0.16 + evidence_score + official_score + corroboration_score + recency_score
    score += impact_score * 0.20
    return round(_clamp01(score), 4)
