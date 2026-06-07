"""open-isco UDF helpers for RisingWave."""

from __future__ import annotations

import json

from kotodama import udf
from kotodama.primitives.open_isco import (
    classification_vertex_id,
    code_level,
    verification_for_confidence,
)


@udf(
    nsid="com.etzhayyim.apps.openIsco.codeLevel",
    io_threads=32,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("open-isco", "occupation", "udf"),
    agent_tool="Classify an ISCO code length into major/submajor/minor/unit.",
)
def code_level_udf(isco_code: str) -> str:
    return json.dumps({"codeLevel": code_level(isco_code)})


@udf(
    nsid="com.etzhayyim.apps.openIsco.verificationForConfidence",
    io_threads=32,
    input_types=["FLOAT64"],
    result_type="VARCHAR",
    capability_tags=("open-isco", "classification", "udf"),
    agent_tool="Classify an ISCO confidence score into authoritative/community/candidate.",
)
def verification_for_confidence_udf(confidence: float) -> str:
    verification = verification_for_confidence(confidence)
    return json.dumps({
        "verification": verification,
        "requireReview": verification == "candidate",
    })


@udf(
    nsid="com.etzhayyim.apps.openIsco.classificationVertexId",
    io_threads=32,
    input_types=["VARCHAR", "VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("open-isco", "classification", "udf"),
    agent_tool="Build a deterministic open-isco classification vertex id from worker, ISCO code, and timestamp.",
)
def classification_vertex_id_udf(worker_did: str, isco_code: str, classified_at: str) -> str:
    return classification_vertex_id(worker_did, isco_code, classified_at)
