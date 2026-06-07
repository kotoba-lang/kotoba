"""open-isic UDF helpers for RisingWave.

Hot-path SQL uses these for deterministic classification gates; BPMN/LangServer
uses `kotodama.primitives.open_isic` for graph writes.
"""

from __future__ import annotations

import json

from kotodama import udf
from kotodama.primitives.open_isic import verification_for_confidence


@udf(
    nsid="com.etzhayyim.apps.openIsic.verificationForConfidence",
    io_threads=32,
    input_types=["FLOAT64"],
    result_type="VARCHAR",
    capability_tags=("open-isic", "classification", "udf"),
    agent_tool="Classify an ISIC confidence score into authoritative/community/candidate.",
)
def verification_for_confidence_udf(confidence: float) -> str:
    verification = verification_for_confidence(confidence)
    return json.dumps({
        "verification": verification,
        "requireReview": verification == "candidate",
    })


@udf(
    nsid="com.etzhayyim.apps.openIsic.classificationVertexId",
    io_threads=32,
    input_types=["VARCHAR", "VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("open-isic", "classification", "udf"),
    agent_tool="Build a deterministic open-isic classification vertex id from entity, class, and timestamp.",
)
def classification_vertex_id(entity_did: str, isic_class_code: str, classified_at: str) -> str:
    import hashlib

    digest = hashlib.sha256(
        f"{entity_did}|{isic_class_code}|{classified_at}".encode("utf-8")
    ).hexdigest()[:24]
    return f"at://did:web:open-isic.etzhayyim.com/com.etzhayyim.apps.openIsic.classification/{digest}"
