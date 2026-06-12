"""iryo.etzhayyim.com (医療 / hospital operations) primitives — Phase 1.

T2 actor (ADR-2604282300): kotodama module + BPMN + Zeebe, no CF Worker.
All domain writes hit RisingWave directly via Hyperdrive (ADR-0036). Social
posts (if any) go through `generic.pds.dispatch` from BPMN, never from this
module.

Pipeline coverage (ADR-0056 BPMN-as-actor + ADR-2605080800):
  admissionDischargeCycle.bpmn  XRPC      → iryo.encounter.upsert
                                           → iryo.bed.assign / iryo.bed.release
  drgClaimCycle.bpmn            XRPC      → iryo.claim.finalize
  bedOccupancyAndShift.bpmn     R/PT1H    → iryo.bed.recompute_occupancy
                                           → iryo.shift.coverage_gap
  agentLoop.bpmn                XRPC      → iryo.agent.chat
  syntheticEventTick.bpmn       R/PT15M   → iryo.synthetic.advance_clock
  fhirSync.bpmn (Phase 1c)      R/P1D     → iryo.fhir.sync_*
  healthKpiRefresh.bpmn (1c)    R/P30D    → iryo.kpi.refresh_*

Output target tables (created by 20260508800000_vertex_iryo_schema.ts):
  vertex_iryo_hospital
  vertex_iryo_dept
  vertex_iryo_ward
  vertex_iryo_bed
  vertex_iryo_staff
  vertex_iryo_encounter
  vertex_iryo_drg_claim
  vertex_iryo_staff_shift
  vertex_iryo_health_kpi

Content-addressed PKs (ADR-0041) — re-runs idempotent.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_IRYO_ROOT = "did:web:iryo.etzhayyim.com"
_IRYO_HOSPITAL = f"{_IRYO_ROOT}:hospital"

# Phase 1 seed hospital — single 300-bed acute-care hospital. Multi-hospital
# becomes meaningful in Phase 2+ when FHIR syncs real Organization rows.
_SEED_HOSPITAL_SLUG = "general-300"
_SEED_BED_CAPACITY = 300

_SEED_DEPTS = [
    ("cardiology",        "Cardiology",            "I00-I99",  "I"),
    ("oncology",          "Oncology",              "C00-D49",  "C"),
    ("orthopedics",       "Orthopedics",           "M00-M99",  "M"),
    ("pediatrics",        "Pediatrics",            "P00-P96",  "P"),
    ("internal-medicine", "Internal Medicine",     "E00-E89",  "E"),
    ("surgery",           "General Surgery",       "K00-K95",  "K"),
    ("obgyn",             "Obstetrics & Gyn",      "O00-O9A",  "O"),
    ("emergency",         "Emergency Medicine",    "S00-T88",  "S"),
    ("icu",               "Intensive Care Unit",   "R00-R99",  "R"),
    ("psychiatry",        "Psychiatry",            "F01-F99",  "F"),
]

# (slug, dept, kind, beds, required_rn, required_md)
_SEED_WARDS = [
    ("icu-3f",       "icu",               "icu",     20, 8, 3),
    ("ccu-3f",       "cardiology",        "ccu",     12, 5, 2),
    ("card-4f",      "cardiology",        "general", 32, 6, 2),
    ("onc-4f",       "oncology",          "general", 28, 5, 2),
    ("ortho-5f",     "orthopedics",       "general", 36, 5, 2),
    ("ped-5f",       "pediatrics",        "general", 24, 6, 2),
    ("im-6f",        "internal-medicine", "general", 40, 6, 2),
    ("sur-6f",       "surgery",           "post-op", 30, 6, 2),
    ("obgyn-7f",     "obgyn",             "general", 24, 5, 2),
    ("er-1f",        "emergency",         "er",      18, 8, 3),
    ("psy-2f",       "psychiatry",        "general", 20, 4, 1),
    ("step-down-2f", "internal-medicine", "step-down", 16, 5, 2),
]

# (admission_type, weight) — used by synthetic advance_clock
_ADMISSION_MIX = [
    ("emergency", 0.55),
    ("elective",  0.35),
    ("transfer",  0.08),
    ("newborn",   0.02),
]

# (icd10_code, drg_code, base_los_days, base_points)
_DRG_TABLE = [
    ("I21.4", "DRG-280", 4, 18000.0),  # AMI
    ("I50.9", "DRG-291", 5, 14000.0),  # Heart failure
    ("J18.9", "DRG-193", 5, 11000.0),  # Pneumonia
    ("E11.9", "DRG-637", 4,  9000.0),  # Type 2 DM
    ("M17.0", "DRG-470", 3, 21000.0),  # Knee replacement
    ("S72.0", "DRG-481", 6, 24000.0),  # Hip fracture
    ("C50.9", "DRG-583", 5, 19000.0),  # Breast cancer
    ("O80.9", "DRG-795", 2,  6500.0),  # Normal delivery
    ("K35.8", "DRG-343", 3,  8500.0),  # Acute appendicitis
    ("F32.9", "DRG-885", 7,  7800.0),  # Major depression
    ("R55",   "DRG-313", 2,  4200.0),  # Syncope
    ("J44.9", "DRG-191", 5, 10500.0),  # COPD exacerbation
]

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_blocks(text: str) -> str:
    if not text:
        return text
    return _THINK_BLOCK_RE.sub("", text).strip()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_iso() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _hash12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _hash16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _slug(s: str, *, max_len: int = 80) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    return s[:max_len] or "x"


def _rw_execute(sql: str, params: tuple[Any, ...]) -> None:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)


def _rw_query(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return list(_res or [])


def _vertex_id(collection: str, rkey: str) -> str:
    return f"at://{_IRYO_HOSPITAL}/com.etzhayyim.apps.iryo.{collection}/{rkey}"


# ──────────────────────────────────────────────────────────────────────
# Seed bootstrap — runs lazily on first encounter/synthetic tick if
# vertex_iryo_hospital is empty. Keeps the cluster deterministic across
# fresh deploys.
# ──────────────────────────────────────────────────────────────────────

_SEED_DONE = False


def _ensure_seed() -> None:
    global _SEED_DONE
    if _SEED_DONE:
        return
    rows = _rw_query("SELECT count(*) FROM vertex_iryo_hospital")
    if rows and rows[0][0] and int(rows[0][0]) > 0:
        _SEED_DONE = True
        return

    now = _now_iso()
    today = _today_iso()
    hospital_slug = _SEED_HOSPITAL_SLUG
    hospital_did = f"{_IRYO_HOSPITAL}:facility:{hospital_slug}"
    hospital_vid = _vertex_id("hospital", hospital_slug)

    _rw_execute(
        "INSERT INTO vertex_iryo_hospital ("
        "vertex_id, owner_did, sensitivity_ord, created_date, "
        "hospital_did, slug, name, country, iso3166_code, bed_capacity, "
        "level, tariff_system, status, "
        "created_at, org_id, user_id, actor_id) "
        "VALUES (%s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)",
        (
            hospital_vid, _IRYO_HOSPITAL, today, hospital_did, hospital_slug,
            "etzhayyim General Hospital (300-bed)", "Generic", "ZZ",
            _SEED_BED_CAPACITY, "tertiary", "GENERIC",
            now, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bootstrap",
        ),
    )

    for slug, name, icd_chap, code in _SEED_DEPTS:
        dept_did = f"{hospital_did}:dept:{slug}"
        dept_vid = _vertex_id("dept", f"{hospital_slug}-{slug}")
        _rw_execute(
            "INSERT INTO vertex_iryo_dept ("
            "vertex_id, owner_did, sensitivity_ord, created_date, "
            "dept_did, slug, hospital_slug, name, specialty_code, icd10_chapter, "
            "head_staff_did, status, created_at, org_id, user_id, actor_id) "
            "VALUES (%s, %s, 0, %s, %s, %s, %s, %s, %s, %s, NULL, 'active', %s, %s, %s, %s)",
            (
                dept_vid, _IRYO_HOSPITAL, today, dept_did, slug, hospital_slug,
                name, code, icd_chap,
                now, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bootstrap",
            ),
        )
        edge_id = f"{dept_vid}::in::{hospital_vid}"
        _rw_execute(
            "INSERT INTO edge_iryo_dept_in_hospital ("
            "edge_id, owner_did, sensitivity_ord, created_date, src_vid, dst_vid, role, "
            "created_at, org_id, user_id, actor_id) "
            "VALUES (%s, %s, 0, %s, %s, %s, 'belongs-to', %s, %s, %s, %s)",
            (edge_id, _IRYO_HOSPITAL, today, dept_vid, hospital_vid,
             now, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bootstrap"),
        )

    bed_total = 0
    for ward_slug, dept_slug, kind, beds, req_rn, req_md in _SEED_WARDS:
        ward_vid = _vertex_id("ward", f"{hospital_slug}-{ward_slug}")
        _rw_execute(
            "INSERT INTO vertex_iryo_ward ("
            "vertex_id, owner_did, sensitivity_ord, created_date, "
            "slug, hospital_slug, dept_slug, name, ward_kind, bed_count, "
            "required_rn_per_shift, required_md_per_shift, status, "
            "created_at, org_id, user_id, actor_id) "
            "VALUES (%s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)",
            (
                ward_vid, _IRYO_HOSPITAL, today, ward_slug, hospital_slug, dept_slug,
                ward_slug.replace("-", " ").title(), kind, beds, req_rn, req_md,
                now, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bootstrap",
            ),
        )

        for i in range(beds):
            bed_slug = f"{ward_slug}-{i+1:03d}"
            bed_vid = _vertex_id("bed", f"{hospital_slug}-{bed_slug}")
            _rw_execute(
                "INSERT INTO vertex_iryo_bed ("
                "vertex_id, owner_did, sensitivity_ord, created_date, "
                "slug, hospital_slug, ward_slug, bed_kind, monitor_class, "
                "occupied, current_encounter_id, last_changed_at_ms, status, "
                "created_at, org_id, user_id, actor_id) "
                "VALUES (%s, %s, 0, %s, %s, %s, %s, %s, %s, FALSE, NULL, %s, 'active', %s, %s, %s, %s)",
                (
                    bed_vid, _IRYO_HOSPITAL, today, bed_slug, hospital_slug, ward_slug,
                    kind, "tier-2" if kind in ("icu", "ccu") else "tier-1",
                    _now_ms(),
                    now, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bootstrap",
                ),
            )
            bed_total += 1

    _SEED_DONE = True


# ──────────────────────────────────────────────────────────────────────
# encounter.upsert — admit or discharge in one primitive (action-routed)
# ──────────────────────────────────────────────────────────────────────

async def task_iryo_encounter_upsert(**kwargs: Any) -> dict[str, Any]:
    _ensure_seed()
    action = (str(kwargs.get("action") or "")).lower()
    encounter_id = str(kwargs.get("encounterId") or "").strip()

    # Auto-resolve action if omitted
    if action not in ("admit", "discharge"):
        if kwargs.get("dischargeDisposition"):
            action = "discharge"
        else:
            action = "admit"

    now_ms = _now_ms()
    now_iso = _now_iso()
    today = _today_iso()

    if action == "admit":
        patient_did = str(kwargs.get("patientDid") or "").strip()
        dept_slug = str(kwargs.get("deptSlug") or "").strip()
        ward_slug = str(kwargs.get("wardSlug") or "").strip()
        admission_type = str(kwargs.get("admissionType") or "elective").lower()
        if not patient_did or not dept_slug or not ward_slug:
            return {"ok": False, "error": "missing patientDid / deptSlug / wardSlug"}

        if not encounter_id:
            seed = f"admit|{patient_did}|{dept_slug}|{ward_slug}|{now_ms}"
            encounter_id = f"enc-{_hash12(seed)}"
        vertex_id = _vertex_id("encounter", encounter_id)

        _rw_execute(
            "INSERT INTO vertex_iryo_encounter ("
            "vertex_id, owner_did, sensitivity_ord, created_date, "
            "encounter_id, patient_did, hospital_slug, dept_slug, ward_slug, "
            "bed_slug, admission_type, age_band, sex, severity_tier, "
            "principal_diagnosis_code, secondary_diagnosis_codes_json, drg_code, "
            "length_of_stay_days, discharge_disposition, "
            "admitted_at_ms, discharged_at_ms, status, data_source, "
            "created_at, org_id, user_id, actor_id) "
            "VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, "
            "NULL, %s, %s, %s, %s, %s, NULL, %s, NULL, NULL, "
            "%s, NULL, 'open', %s, %s, %s, %s, %s)",
            (
                vertex_id, _IRYO_HOSPITAL, today,
                encounter_id, patient_did, _SEED_HOSPITAL_SLUG, dept_slug, ward_slug,
                admission_type,
                str(kwargs.get("ageBand") or "") or None,
                str(kwargs.get("sex") or "") or None,
                int(kwargs.get("severityTier") or 2),
                str(kwargs.get("principalDiagnosisCode") or "") or None,
                str(kwargs.get("drgCode") or "") or None,
                now_ms,
                str(kwargs.get("dataSource") or "xrpc"),
                now_iso, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.encounter.upsert",
            ),
        )
        return {
            "ok": True, "encounterId": encounter_id, "admittedAtMs": now_ms,
            "dischargedAtMs": None, "lengthOfStayDays": None,
            "resolvedAction": "admit",
        }

    # discharge
    if not encounter_id:
        return {"ok": False, "error": "encounterId required for discharge"}

    rows = _rw_query(
        "SELECT admitted_at_ms, hospital_slug, dept_slug, ward_slug, bed_slug, "
        "principal_diagnosis_code, drg_code, status "
        "FROM vertex_iryo_encounter WHERE encounter_id = %s LIMIT 1",
        (encounter_id,),
    )
    if not rows:
        return {"ok": False, "error": f"encounter {encounter_id} not found"}
    admitted_at_ms = int(rows[0][0] or now_ms)
    los_days = max(0, int((now_ms - admitted_at_ms) / 86_400_000))

    pdx = str(kwargs.get("principalDiagnosisCode") or rows[0][5] or "").strip()
    drg = str(kwargs.get("drgCode") or rows[0][6] or "").strip()
    if pdx and not drg:
        drg = _suggest_drg_for_icd10(pdx)
    sec_codes = kwargs.get("secondaryDiagnosisCodes") or []
    if isinstance(sec_codes, str):
        sec_codes = [sec_codes]
    sec_json = json.dumps([str(c) for c in sec_codes][:20]) if sec_codes else None

    # Re-insert encounter row with closed status (RisingWave PK = vertex_id;
    # same vertex_id overwrites per RW upsert semantics).
    vertex_id = _vertex_id("encounter", encounter_id)
    _rw_execute(
        "INSERT INTO vertex_iryo_encounter ("
        "vertex_id, owner_did, sensitivity_ord, created_date, "
        "encounter_id, patient_did, hospital_slug, dept_slug, ward_slug, "
        "bed_slug, admission_type, age_band, sex, severity_tier, "
        "principal_diagnosis_code, secondary_diagnosis_codes_json, drg_code, "
        "length_of_stay_days, discharge_disposition, "
        "admitted_at_ms, discharged_at_ms, status, data_source, "
        "created_at, org_id, user_id, actor_id) "
        "SELECT %s, owner_did, sensitivity_ord, created_date, "
        "encounter_id, patient_did, hospital_slug, dept_slug, ward_slug, "
        "bed_slug, admission_type, age_band, sex, severity_tier, "
        "%s, %s, %s, %s, %s, "
        "admitted_at_ms, %s, 'closed', data_source, "
        "%s, org_id, user_id, %s "
        "FROM vertex_iryo_encounter WHERE encounter_id = %s LIMIT 1",
        (
            vertex_id, pdx or None, sec_json, drg or None, los_days,
            str(kwargs.get("dischargeDisposition") or "home"),
            now_ms, now_iso, "iryo.encounter.upsert", encounter_id,
        ),
    )

    return {
        "ok": True, "encounterId": encounter_id,
        "admittedAtMs": admitted_at_ms, "dischargedAtMs": now_ms,
        "lengthOfStayDays": los_days,
        "resolvedAction": "discharge",
    }


def _suggest_drg_for_icd10(icd10: str) -> str:
    code = (icd10 or "").upper()
    for icd, drg, _, _ in _DRG_TABLE:
        if code.startswith(icd[:3]):
            return drg
    return "DRG-999"


# ──────────────────────────────────────────────────────────────────────
# bed.assign / bed.release
# ──────────────────────────────────────────────────────────────────────

async def task_iryo_bed_assign(**kwargs: Any) -> dict[str, Any]:
    encounter_id = str(kwargs.get("encounterId") or "").strip()
    ward_slug = str(kwargs.get("wardSlug") or "").strip()
    if not encounter_id or not ward_slug:
        return {"ok": False, "error": "missing encounterId / wardSlug"}

    rows = _rw_query(
        "SELECT slug FROM vertex_iryo_bed "
        "WHERE ward_slug = %s AND status = 'active' AND occupied = FALSE "
        "LIMIT 1",
        (ward_slug,),
    )
    if not rows:
        return {"ok": False, "error": f"no available bed in ward {ward_slug}"}
    bed_slug = str(rows[0][0])
    bed_vid = _vertex_id("bed", f"{_SEED_HOSPITAL_SLUG}-{bed_slug}")
    enc_vid = _vertex_id("encounter", encounter_id)
    now_ms = _now_ms()
    now_iso = _now_iso()

    _rw_execute(
        "UPDATE vertex_iryo_bed "
        "SET occupied = TRUE, current_encounter_id = %s, last_changed_at_ms = %s "
        "WHERE slug = %s AND ward_slug = %s",
        (encounter_id, now_ms, bed_slug, ward_slug),
    )
    _rw_execute(
        "UPDATE vertex_iryo_encounter SET bed_slug = %s WHERE encounter_id = %s",
        (bed_slug, encounter_id),
    )
    edge_id = f"{enc_vid}::in-bed::{bed_vid}"
    _rw_execute(
        "INSERT INTO edge_iryo_encounter_in_bed ("
        "edge_id, owner_did, sensitivity_ord, created_date, src_vid, dst_vid, role, "
        "created_at, org_id, user_id, actor_id) "
        "VALUES (%s, %s, 1, %s, %s, %s, 'placed-in', %s, %s, %s, %s)",
        (edge_id, _IRYO_HOSPITAL, _today_iso(), enc_vid, bed_vid,
         now_iso, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bed.assign"),
    )
    return {"ok": True, "bedSlug": bed_slug}


async def task_iryo_bed_release(**kwargs: Any) -> dict[str, Any]:
    encounter_id = str(kwargs.get("encounterId") or "").strip()
    if not encounter_id:
        return {"ok": False, "error": "missing encounterId"}

    rows = _rw_query(
        "SELECT bed_slug, ward_slug, dept_slug, principal_diagnosis_code, "
        "secondary_diagnosis_codes_json, drg_code, length_of_stay_days, severity_tier "
        "FROM vertex_iryo_encounter WHERE encounter_id = %s LIMIT 1",
        (encounter_id,),
    )
    if not rows:
        return {"ok": False, "error": f"encounter {encounter_id} not found"}
    bed_slug, ward_slug, dept_slug, pdx, sec_json, drg, los, severity = rows[0]
    bed_slug = str(bed_slug or "")
    drg = str(drg or kwargs.get("drgCode") or _suggest_drg_for_icd10(str(pdx or "")))
    pdx = str(pdx or kwargs.get("principalDiagnosisCode") or "")

    if bed_slug:
        _rw_execute(
            "UPDATE vertex_iryo_bed "
            "SET occupied = FALSE, current_encounter_id = NULL, last_changed_at_ms = %s "
            "WHERE slug = %s",
            (_now_ms(), bed_slug),
        )

    # Draft DRG claim
    claim_id = f"clm-{_hash12(f'{encounter_id}|{drg}|{_now_ms()}')}"
    base_pts = 10000.0
    for icd, dcode, _bd_los, pts in _DRG_TABLE:
        if dcode == drg:
            base_pts = pts
            break
    package_points = base_pts * (1.0 + 0.10 * (int(severity or 2) - 2))

    claim_vid = _vertex_id("drgClaim", claim_id)
    now_iso = _now_iso()
    today = _today_iso()
    _rw_execute(
        "INSERT INTO vertex_iryo_drg_claim ("
        "vertex_id, owner_did, sensitivity_ord, created_date, "
        "claim_id, encounter_id, hospital_slug, dept_slug, "
        "drg_code, principal_diagnosis_code, secondary_diagnosis_codes_json, "
        "specialty_code, length_of_stay_days, severity_tier, "
        "package_points, tariff_system, cost_estimate, "
        "auditor_did, submitted_at_ms, status, denial_reason, "
        "created_at, org_id, user_id, actor_id) "
        "VALUES (%s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, "
        "NULL, %s, %s, %s, 'GENERIC', %s, NULL, NULL, 'draft', NULL, "
        "%s, %s, %s, %s)",
        (
            claim_vid, _IRYO_HOSPITAL, today,
            claim_id, encounter_id, _SEED_HOSPITAL_SLUG, str(dept_slug or ""),
            drg, pdx or None, sec_json,
            int(los or 0), int(severity or 2), package_points,
            package_points * 0.62,
            now_iso, _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.bed.release",
        ),
    )
    return {"ok": True, "bedSlug": bed_slug, "claimId": claim_id, "drgCode": drg}


# ──────────────────────────────────────────────────────────────────────
# claim.finalize  (XRPC submitDrgClaim)
# ──────────────────────────────────────────────────────────────────────

async def task_iryo_claim_finalize(**kwargs: Any) -> dict[str, Any]:
    claim_id = str(kwargs.get("claimId") or "").strip()
    if not claim_id:
        return {"ok": False, "error": "missing claimId"}
    package_points = float(kwargs.get("packagePoints") or 0.0)
    tariff_system = str(kwargs.get("tariffSystem") or "GENERIC").upper()
    auditor_did = str(kwargs.get("auditorDid") or _IRYO_HOSPITAL)
    now_ms = _now_ms()
    _rw_execute(
        "UPDATE vertex_iryo_drg_claim "
        "SET package_points = %s, tariff_system = %s, auditor_did = %s, "
        "    submitted_at_ms = %s, status = 'submitted' "
        "WHERE claim_id = %s AND status = 'draft'",
        (package_points, tariff_system, auditor_did, now_ms, claim_id),
    )
    return {
        "ok": True, "claimId": claim_id,
        "status": "submitted", "submittedAtMs": now_ms,
    }


# ──────────────────────────────────────────────────────────────────────
# bed.recompute_occupancy  (R/PT1H read-only — MV does the work)
# ──────────────────────────────────────────────────────────────────────

async def task_iryo_bed_recompute_occupancy(**kwargs: Any) -> dict[str, Any]:
    rows = _rw_query(
        "SELECT ward_slug, total_beds, occupied_beds, utilization "
        "FROM mv_iryo_bed_occupancy_now"
    )
    if not rows:
        return {"ok": True, "wardsScanned": 0, "occupancyMin": 0.0, "occupancyMax": 0.0}
    utils = [float(r[3] or 0.0) for r in rows]
    return {
        "ok": True,
        "wardsScanned": len(rows),
        "occupancyMin": min(utils),
        "occupancyMax": max(utils),
    }


async def task_iryo_shift_coverage_gap(**kwargs: Any) -> dict[str, Any]:
    rows = _rw_query(
        "SELECT count(*), sum(CASE WHEN gap > 0 THEN 1 ELSE 0 END) "
        "FROM mv_iryo_staff_coverage_gap "
        "WHERE shift_date >= CURRENT_DATE AND shift_date < CURRENT_DATE + 1"
    )
    if not rows:
        return {"ok": True, "shiftsScanned": 0, "gapsDetected": 0}
    scanned = int(rows[0][0] or 0)
    gaps = int(rows[0][1] or 0)
    return {"ok": True, "shiftsScanned": scanned, "gapsDetected": gaps}


# ──────────────────────────────────────────────────────────────────────
# synthetic.advance_clock  (Phase 1 only — keeps cluster lively)
# ──────────────────────────────────────────────────────────────────────

def _pick_admission_type() -> str:
    r = random.random()
    cum = 0.0
    for kind, w in _ADMISSION_MIX:
        cum += w
        if r <= cum:
            return kind
    return "elective"


async def task_iryo_synthetic_advance_clock(**kwargs: Any) -> dict[str, Any]:
    _ensure_seed()
    n_admit = int(kwargs.get("nAdmit") or 8)
    n_discharge = int(kwargs.get("nDischarge") or 6)

    admits = 0
    for _ in range(n_admit):
        ward_slug, dept_slug, _kind, _beds, _rn, _md = random.choice(_SEED_WARDS)
        synthetic_pid = f"did:plc:syn-{_hash16(str(random.random()) + str(_now_ms()))}"
        admit_args = {
            "action": "admit",
            "patientDid": synthetic_pid,
            "deptSlug": dept_slug,
            "wardSlug": ward_slug,
            "admissionType": _pick_admission_type(),
            "ageBand": random.choice(["0-4", "20-24", "45-49", "65-69", "80-84"]),
            "sex": random.choice(["M", "F"]),
            "severityTier": random.choices([1, 2, 3, 4], weights=[20, 50, 25, 5])[0],
            "dataSource": "synthetic",
        }
        result = await task_iryo_encounter_upsert(**admit_args)
        if result.get("ok"):
            await task_iryo_bed_assign(
                encounterId=result["encounterId"], wardSlug=ward_slug,
            )
            admits += 1

    # discharge oldest open encounters
    open_rows = _rw_query(
        "SELECT encounter_id FROM vertex_iryo_encounter "
        "WHERE status='open' AND data_source='synthetic' "
        "ORDER BY admitted_at_ms ASC LIMIT %s",
        (n_discharge,),
    )
    discharges = 0
    for (eid,) in open_rows:
        icd, _drg, _los, _pts = random.choice(_DRG_TABLE)
        result = await task_iryo_encounter_upsert(
            action="discharge",
            encounterId=str(eid),
            principalDiagnosisCode=icd,
            dischargeDisposition=random.choice(["home", "transfer", "rehab"]),
        )
        if result.get("ok"):
            await task_iryo_bed_release(encounterId=str(eid))
            discharges += 1

    return {"ok": True, "admits": admits, "discharges": discharges, "transfers": 0}


# ──────────────────────────────────────────────────────────────────────
# agent.chat — Path F unified loop
# ──────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are the operations strategist for a 300-bed acute-care hospital.
You see live bed occupancy, 30-day admission counts per department, recent DRG package P&L,
and WHO/OECD healthcare benchmark KPIs. Be concise and actionable. Surface bottlenecks
(occupancy >85% in any ward, dept admit volatility, DRGs with margin compression).
Respond in the language of the user prompt. Do not invent patient identifiers."""


async def task_iryo_agent_chat(**kwargs: Any) -> dict[str, Any]:
    prompt = str(kwargs.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "missing prompt"}
    tier = str(kwargs.get("tier") or "reasoning")
    max_tokens = int(kwargs.get("maxTokens") or 1500)
    dept_focus = str(kwargs.get("deptFocus") or "").strip() or None

    occ = _rw_query(
        "SELECT ward_slug, total_beds, occupied_beds, utilization "
        "FROM mv_iryo_bed_occupancy_now ORDER BY utilization DESC LIMIT 12"
    )
    if dept_focus:
        adm = _rw_query(
            "SELECT created_date, dept_slug, admit_count, emergency_count, elective_count "
            "FROM mv_iryo_admission_count_by_dept WHERE dept_slug = %s "
            "ORDER BY created_date DESC LIMIT 30",
            (dept_focus,),
        )
    else:
        adm = _rw_query(
            "SELECT created_date, dept_slug, admit_count, emergency_count, elective_count "
            "FROM mv_iryo_admission_count_by_dept "
            "ORDER BY created_date DESC, admit_count DESC LIMIT 30"
        )
    pnl = _rw_query(
        "SELECT created_date, dept_slug, drg_code, claim_count, gross_points, margin_points "
        "FROM mv_iryo_drg_pnl_daily ORDER BY created_date DESC LIMIT 20"
    )
    kpi = _rw_query(
        "SELECT source, indicator_code, country, year, value, unit "
        "FROM vertex_iryo_health_kpi ORDER BY ingested_at_ms DESC LIMIT 12"
    )

    context = {
        "bedOccupancy": [
            {"ward": r[0], "total": int(r[1] or 0), "occupied": int(r[2] or 0),
             "util": float(r[3] or 0.0)} for r in occ
        ],
        "admissionCount30d": [
            {"date": str(r[0]), "dept": r[1], "admits": int(r[2] or 0),
             "er": int(r[3] or 0), "elective": int(r[4] or 0)} for r in adm
        ],
        "drgPnlRecent": [
            {"date": str(r[0]), "dept": r[1], "drg": r[2],
             "claims": int(r[3] or 0), "gross": float(r[4] or 0),
             "margin": float(r[5] or 0)} for r in pnl
        ],
        "kpi": [
            {"src": r[0], "code": r[1], "country": r[2],
             "year": int(r[3] or 0), "value": float(r[4] or 0), "unit": r[5]}
            for r in kpi
        ],
    }
    user_msg = (
        f"Live context (JSON):\n{json.dumps(context, ensure_ascii=False)[:8000]}\n\n"
        f"User question:\n{prompt}"
    )

    started = _now_ms()
    try:
        from kotodama.llm import call_tier  # type: ignore
    except Exception:
        return {
            "ok": False, "error": "kotodama.llm not available", "model": "",
            "content": "", "latencyMs": 0,
            "occupancyRowsUsed": len(occ), "admissionRowsUsed": len(adm),
            "drgPnlRowsUsed": len(pnl), "kpiRowsUsed": len(kpi),
        }
    try:
        result = await call_tier(
            tier=tier,
            system=_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=max_tokens,
        )
    except Exception as e:
        return {"ok": False, "error": f"llm error: {e}", "model": "",
                "content": "", "latencyMs": _now_ms() - started,
                "occupancyRowsUsed": len(occ), "admissionRowsUsed": len(adm),
                "drgPnlRowsUsed": len(pnl), "kpiRowsUsed": len(kpi)}
    content = _strip_think_blocks(result.get("content", "")) if isinstance(result, dict) else ""
    model = result.get("model", "") if isinstance(result, dict) else ""
    return {
        "ok": True, "content": content, "model": model,
        "latencyMs": _now_ms() - started,
        "occupancyRowsUsed": len(occ),
        "admissionRowsUsed": len(adm),
        "drgPnlRowsUsed": len(pnl),
        "kpiRowsUsed": len(kpi),
    }


# ──────────────────────────────────────────────────────────────────────
# fhir.sync_*  (Phase 1c — HAPI public test server)
# ──────────────────────────────────────────────────────────────────────

_FHIR_BASE = os.environ.get("IRYO_FHIR_BASE", "https://hapi.fhir.org/baseR4")


def _fhir_get(path: str, *, count: int = 50) -> dict[str, Any]:
    url = f"{_FHIR_BASE}{path}"
    sep = "&" if "?" in path else "?"
    url = f"{url}{sep}_count={count}&_format=json"
    req = urllib.request.Request(
        url, headers={"User-Agent": "iryo.etzhayyim.com/1.0", "Accept": "application/fhir+json"},
    )
    with urllib.request.urlopen(req, timeout=20.0) as r:
        return json.loads(r.read().decode("utf-8"))


async def task_iryo_fhir_sync_encounter(**kwargs: Any) -> dict[str, Any]:
    """Pull a small batch of FHIR Encounter from HAPI public R4 server.
    Phase 1c smoke. Real data, no PHI (it's a public test sandbox).
    """
    try:
        bundle = _fhir_get("/Encounter", count=int(kwargs.get("count") or 25))
    except Exception as e:
        return {"ok": False, "error": f"fhir fetch failed: {e}", "imported": 0}
    entries = (bundle or {}).get("entry") or []
    imported = 0
    for entry in entries:
        res = (entry or {}).get("resource") or {}
        if res.get("resourceType") != "Encounter":
            continue
        fhir_id = str(res.get("id") or "")
        if not fhir_id:
            continue
        encounter_id = f"fhir-{_hash12(fhir_id)}"
        patient_ref = ((res.get("subject") or {}).get("reference") or "").split("/")[-1]
        patient_did = f"did:plc:fhir-{_hash16(patient_ref or fhir_id)}"
        period = res.get("period") or {}
        admit_iso = period.get("start") or _now_iso()
        try:
            admit_ms = int(time.mktime(time.strptime(admit_iso[:19], "%Y-%m-%dT%H:%M:%S")) * 1000)
        except Exception:
            admit_ms = _now_ms()
        status = "open" if not period.get("end") else "closed"
        admission_type = "elective"
        cls = (res.get("class") or {}).get("code") or ""
        if cls.upper() == "EMER":
            admission_type = "emergency"

        await task_iryo_encounter_upsert(
            action="admit" if status == "open" else "admit",  # we just write the row; closure separate
            encounterId=encounter_id,
            patientDid=patient_did,
            deptSlug="internal-medicine",
            wardSlug="im-6f",
            admissionType=admission_type,
            severityTier=2,
            dataSource="fhir-hapi-r4",
        )
        imported += 1
    return {"ok": True, "imported": imported, "fhirBase": _FHIR_BASE}


# ──────────────────────────────────────────────────────────────────────
# kpi.refresh_*  (Phase 1c — WHO GHO + OECD)
# ──────────────────────────────────────────────────────────────────────

_WHO_GHO_BASE = "https://ghoapi.azureedge.net/api"


async def task_iryo_kpi_refresh_who_gho(**kwargs: Any) -> dict[str, Any]:
    """Pull a small set of WHO GHO indicators (health expenditure, beds-per-1000,
    nurses-per-1000) and persist as vertex_iryo_health_kpi rows."""
    indicators = [
        "WHS6_102",  # Hospital beds per 10,000
        "HWF_0006",  # Nurses + midwives per 10,000
        "HWF_0001",  # Medical doctors per 10,000
    ]
    imported = 0
    for code in indicators:
        try:
            url = f"{_WHO_GHO_BASE}/{urllib.parse.quote(code)}"
            req = urllib.request.Request(url, headers={"User-Agent": "iryo.etzhayyim.com/1.0"})
            with urllib.request.urlopen(req, timeout=15.0) as r:
                payload = json.loads(r.read().decode("utf-8"))
        except Exception:
            continue
        for row in (payload or {}).get("value", [])[:200]:
            country = str(row.get("SpatialDim") or "")
            year = int(row.get("TimeDim") or 0)
            value = row.get("NumericValue")
            try:
                value = float(value) if value is not None else None
            except (TypeError, ValueError):
                value = None
            vid_seed = f"WHO_GHO|{code}|{country}|{year}"
            vid = _vertex_id("healthKpi", _hash16(vid_seed))
            _rw_execute(
                "INSERT INTO vertex_iryo_health_kpi ("
                "vertex_id, owner_did, sensitivity_ord, created_date, "
                "source, indicator_code, country, iso3166_code, year, "
                "value, unit, raw_json, ingested_at_ms, status, "
                "created_at, org_id, user_id, actor_id) "
                "VALUES (%s, %s, 0, %s, 'WHO_GHO', %s, %s, %s, %s, %s, %s, %s, %s, 'active', "
                "%s, %s, %s, %s)",
                (
                    vid, _IRYO_HOSPITAL, _today_iso(),
                    code, country, country[:2], year, value,
                    str(row.get("Dim1") or ""),
                    json.dumps(row)[:8000],
                    _now_ms(), _now_iso(), _IRYO_HOSPITAL, _IRYO_HOSPITAL, "iryo.kpi.refresh_who_gho",
                ),
            )
            imported += 1
    return {"ok": True, "imported": imported}


# ──────────────────────────────────────────────────────────────────────
# Phase 1.1 — query primitives (read-only, BPMN-bound to 4 query lexicons)
# ──────────────────────────────────────────────────────────────────────

async def task_iryo_coverage_snapshot(**kwargs: Any) -> dict[str, Any]:
    """Read-only counts for com.etzhayyim.apps.iryo.coverage."""
    rows = _rw_query(
        "SELECT "
        " (SELECT count(*) FROM vertex_iryo_hospital), "
        " (SELECT count(*) FROM vertex_iryo_dept), "
        " (SELECT count(*) FROM vertex_iryo_ward), "
        " (SELECT count(*) FROM vertex_iryo_bed), "
        " (SELECT count(*) FROM vertex_iryo_staff), "
        " (SELECT count(*) FROM vertex_iryo_encounter WHERE status='open'), "
        " (SELECT count(*) FROM vertex_iryo_encounter WHERE status='closed'), "
        " (SELECT count(*) FROM vertex_iryo_drg_claim WHERE status IN ('draft','submitted')), "
        " (SELECT count(*) FROM vertex_iryo_drg_claim WHERE status='paid'), "
        " (SELECT COALESCE(MAX(last_changed_at_ms), 0) FROM vertex_iryo_bed)"
    )
    r = rows[0] if rows else (0,) * 10
    return {
        "ok": True,
        "asOf": _now_iso(),
        "hospitals": int(r[0] or 0),
        "depts": int(r[1] or 0),
        "wards": int(r[2] or 0),
        "beds": int(r[3] or 0),
        "staff": int(r[4] or 0),
        "encountersOpen": int(r[5] or 0),
        "encountersClosed": int(r[6] or 0),
        "drgClaimsOpen": int(r[7] or 0),
        "drgClaimsClosed": int(r[8] or 0),
        "lastBedRecomputeMs": int(r[9] or 0),
    }


async def task_iryo_bed_occupancy_snapshot(**kwargs: Any) -> dict[str, Any]:
    """Read-only ward occupancy snapshot for com.etzhayyim.apps.iryo.getBedOccupancy."""
    dept_filter = (str(kwargs.get("deptSlug") or "")).strip()
    if dept_filter:
        # Join via vertex_iryo_ward to get dept_slug for each ward.
        rows = _rw_query(
            "SELECT m.ward_slug, w.dept_slug, m.total_beds, m.occupied_beds, m.utilization "
            "FROM mv_iryo_bed_occupancy_now m "
            "JOIN vertex_iryo_ward w ON w.slug = m.ward_slug "
            "WHERE w.dept_slug = %s "
            "ORDER BY m.utilization DESC",
            (dept_filter,),
        )
    else:
        rows = _rw_query(
            "SELECT m.ward_slug, w.dept_slug, m.total_beds, m.occupied_beds, m.utilization "
            "FROM mv_iryo_bed_occupancy_now m "
            "JOIN vertex_iryo_ward w ON w.slug = m.ward_slug "
            "ORDER BY m.utilization DESC"
        )
    return {
        "ok": True,
        "snapshotMs": _now_ms(),
        "rows": [
            {
                "wardSlug": r[0],
                "deptSlug": r[1],
                "totalBeds": int(r[2] or 0),
                "occupiedBeds": int(r[3] or 0),
                "utilization": float(r[4] or 0.0),
            }
            for r in rows
        ],
    }


async def task_iryo_encounter_list(**kwargs: Any) -> dict[str, Any]:
    """Read-only encounter list for com.etzhayyim.apps.iryo.listEncounters."""
    where: list[str] = []
    params: list[Any] = []
    dept = str(kwargs.get("deptSlug") or "").strip()
    ward = str(kwargs.get("wardSlug") or "").strip()
    status = str(kwargs.get("status") or "any").lower()
    if dept:
        where.append("dept_slug = %s")
        params.append(dept)
    if ward:
        where.append("ward_slug = %s")
        params.append(ward)
    if status in ("open", "closed"):
        where.append("status = %s")
        params.append(status)

    admitted_after = kwargs.get("admittedAfter")
    if admitted_after:
        try:
            ts = int(time.mktime(time.strptime(str(admitted_after)[:19], "%Y-%m-%dT%H:%M:%S")) * 1000)
            where.append("admitted_at_ms >= %s")
            params.append(ts)
        except Exception:
            pass
    admitted_before = kwargs.get("admittedBefore")
    if admitted_before:
        try:
            ts = int(time.mktime(time.strptime(str(admitted_before)[:19], "%Y-%m-%dT%H:%M:%S")) * 1000)
            where.append("admitted_at_ms <= %s")
            params.append(ts)
        except Exception:
            pass

    limit = max(1, min(int(kwargs.get("limit") or 50), 200))
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    # RW rejects parameterized LIMIT in prepared statements ([[conventions]]
    # rw-psycopg3-no-param-limit) — inline the int.
    rows = _rw_query(
        "SELECT encounter_id, patient_did, dept_slug, ward_slug, bed_slug, status, "
        "admission_type, admitted_at_ms, discharged_at_ms, "
        "principal_diagnosis_code, drg_code, length_of_stay_days, severity_tier "
        "FROM vertex_iryo_encounter"
        f"{sql_where} ORDER BY admitted_at_ms DESC LIMIT {limit}",
        tuple(params),
    )
    return {
        "ok": True,
        "encounters": [
            {
                "encounterId": r[0],
                "patientDid": r[1],
                "deptSlug": r[2],
                "wardSlug": r[3],
                "bedSlug": r[4] or "",
                "status": r[5],
                "admissionType": r[6],
                "admittedAtMs": int(r[7] or 0),
                "dischargedAtMs": int(r[8] or 0) if r[8] is not None else None,
                "principalDiagnosisCode": r[9] or "",
                "drgCode": r[10] or "",
                "lengthOfStayDays": int(r[11] or 0) if r[11] is not None else None,
                "severityTier": int(r[12] or 0) if r[12] is not None else None,
            }
            for r in rows
        ],
    }


async def task_iryo_claim_get(**kwargs: Any) -> dict[str, Any]:
    """Read-only single-claim lookup for com.etzhayyim.apps.iryo.getDrgClaim."""
    claim_id = str(kwargs.get("claimId") or "").strip()
    if not claim_id:
        return {"ok": False, "error": "missing claimId"}
    rows = _rw_query(
        "SELECT claim_id, encounter_id, drg_code, principal_diagnosis_code, "
        "secondary_diagnosis_codes_json, specialty_code, length_of_stay_days, "
        "severity_tier, package_points, tariff_system, submitted_at_ms, status, denial_reason "
        "FROM vertex_iryo_drg_claim WHERE claim_id = %s LIMIT 1",
        (claim_id,),
    )
    if not rows:
        return {"ok": False, "error": "not found"}
    r = rows[0]
    return {
        "ok": True,
        "claim": {
            "claimId": r[0],
            "encounterId": r[1],
            "drgCode": r[2],
            "principalDiagnosisCode": r[3] or "",
            "secondaryDiagnosisCodesJson": r[4] or "",
            "specialtyCode": r[5] or "",
            "lengthOfStayDays": int(r[6] or 0) if r[6] is not None else None,
            "severityTier": int(r[7] or 0) if r[7] is not None else None,
            "packagePoints": float(r[8] or 0.0) if r[8] is not None else None,
            "tariffSystem": r[9] or "",
            "submittedAtMs": int(r[10] or 0) if r[10] is not None else None,
            "status": r[11] or "",
            "denialReason": r[12] or "",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Worker registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register all iryo task handlers with a LangServerWorker."""
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("iryo.encounter.upsert",         task_iryo_encounter_upsert)
    t("iryo.bed.assign",               task_iryo_bed_assign)
    t("iryo.bed.release",              task_iryo_bed_release)
    t("iryo.bed.recompute_occupancy",  task_iryo_bed_recompute_occupancy)
    t("iryo.shift.coverage_gap",       task_iryo_shift_coverage_gap)
    t("iryo.claim.finalize",           task_iryo_claim_finalize)
    t("iryo.synthetic.advance_clock",  task_iryo_synthetic_advance_clock, ms=120_000)
    t("iryo.agent.chat",               task_iryo_agent_chat,              ms=60_000)
    t("iryo.fhir.sync_encounter",      task_iryo_fhir_sync_encounter,     ms=120_000)
    t("iryo.kpi.refresh_who_gho",      task_iryo_kpi_refresh_who_gho,     ms=180_000)
    # Phase 1.1 query primitives
    t("iryo.coverage.snapshot",        task_iryo_coverage_snapshot,       ms=15_000)
    t("iryo.bed.occupancySnapshot",    task_iryo_bed_occupancy_snapshot,  ms=15_000)
    t("iryo.encounter.list",           task_iryo_encounter_list,          ms=15_000)
    t("iryo.claim.get",                task_iryo_claim_get,               ms=15_000)


__all__ = [
    "register",
    "task_iryo_encounter_upsert",
    "task_iryo_bed_assign",
    "task_iryo_bed_release",
    "task_iryo_bed_recompute_occupancy",
    "task_iryo_shift_coverage_gap",
    "task_iryo_claim_finalize",
    "task_iryo_synthetic_advance_clock",
    "task_iryo_agent_chat",
    "task_iryo_fhir_sync_encounter",
    "task_iryo_kpi_refresh_who_gho",
    "task_iryo_coverage_snapshot",
    "task_iryo_bed_occupancy_snapshot",
    "task_iryo_encounter_list",
    "task_iryo_claim_get",
]
