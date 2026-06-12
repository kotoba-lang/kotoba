from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import apqc, open_isic, open_isco  # noqa: E402


def test_open_isic_classify_entity_dry_run():
    out = asyncio.run(open_isic.task_open_isic_classify_entity(
        entityDid="did:web:example.com",
        isicClassCode="2520",
        entityName="Example Arms",
        confidence=0.95,
        classifiedAt="2026-04-30T00:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["verification"] == "authoritative"
    assert out["status"] == "confirmed"
    assert out["classDid"] == "did:web:open-isic.etzhayyim.com:class:2520"


def test_open_isic_record_concordance_rejects_bad_relation():
    out = asyncio.run(open_isic.task_open_isic_record_concordance(
        isicClassCode="2520",
        otherTaxonomy="NAICS",
        otherCode="332992",
        relation="sameAs",
        dryRun=True,
    ))
    assert out["ok"] is False
    assert "invalid relation" in out["error"]


def test_apqc_materializes_all_l2_for_l1():
    out = asyncio.run(apqc.task_apqc_materialize_subprocesses(
        apqcCode="12.0",
        dryRun=True,
    ))
    print("FULL OUT:", out)
    assert out["ok"] is True
    assert out["materialized"] == 49
    assert out["subprocesses"][0]["did"].startswith(
        "did:web:kyber-projector.etzhayyim.com:apqc:12-external-relations:subprocess:"
    )


def test_apqc_coverage_snapshot_marks_runtime_migrated():
    out = asyncio.run(apqc.task_apqc_coverage_snapshot())
    assert out["registeredL1"] == 13
    assert out["registeredSubProcesses"] == 183
    assert out["standaloneWasm"] == "retired"


def test_apqc_did_normalizes_l2_to_l1_actor():
    assert apqc.apqc_did("9.4.1").startswith(
        "did:web:kyber-projector.etzhayyim.com:apqc:9-financial-resources:subprocess:"
    )


def test_open_isco_classify_worker_dry_run():
    out = asyncio.run(open_isco.task_open_isco_classify_worker(
        workerDid="did:web:worker.example",
        iscoCode="2512",
        employerDid="did:web:employer.example",
        confidence=0.91,
        classifiedAt="2026-04-30T00:00:00Z",
        dryRun=True,
    ))
    assert out["ok"] is True
    assert out["codeLevel"] == "unit"
    assert out["verification"] == "authoritative"
    assert out["occupationDid"] == "did:web:isco.etzhayyim.com:occupation:2512"


def test_open_isco_record_concordance_rejects_bad_relation():
    out = asyncio.run(open_isco.task_open_isco_record_concordance(
        iscoCode="2512",
        otherTaxonomy="SOC",
        otherCode="15-1252",
        relation="sameAs",
        dryRun=True,
    ))
    assert out["ok"] is False
    assert "invalid relation" in out["error"]
