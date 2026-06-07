"""APQC UDF helpers for RisingWave.

These are deterministic companions to the LangServer APQC tasks. They make APQC
coverage and DID materialization available inside SQL without the retired WASM
runtime.
"""

from __future__ import annotations

import json

from kotodama import udf
from kotodama.primitives.apqc import APQC_L1, L1_BY_CODE, apqc_did


@udf(
    nsid="com.etzhayyim.apps.apqc.materializeSubprocessDid",
    io_threads=32,
    input_types=["VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("apqc", "subprocess", "udf"),
    agent_tool="Return the path-based APQC subprocess DID for an APQC L1/L2 code pair.",
)
def materialize_subprocess_did(apqc_code: str, subprocess_code: str) -> str:
    if apqc_code not in L1_BY_CODE:
        return json.dumps({"ok": False, "error": f"unknown apqcCode: {apqc_code}"})
    return json.dumps({
        "ok": True,
        "apqcCode": apqc_code,
        "subprocessCode": subprocess_code,
        "did": apqc_did(apqc_code, subprocess_code),
    })


@udf(
    nsid="com.etzhayyim.apps.apqc.coverageSnapshot",
    io_threads=32,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("apqc", "coverage", "udf"),
    agent_tool="Return the APQC runtime coverage snapshot for SQL pipelines.",
)
def coverage_snapshot(_scope: str = "all") -> str:
    return json.dumps({
        "registeredL1": len(APQC_L1),
        "totalL1": len(APQC_L1),
        "registeredSubProcesses": sum(int(x[3]) for x in APQC_L1),
        "totalSubProcesses": sum(int(x[3]) for x in APQC_L1),
        "runtime": "langserver-langgraph-udf",
        "standaloneWasm": "retired",
    })
