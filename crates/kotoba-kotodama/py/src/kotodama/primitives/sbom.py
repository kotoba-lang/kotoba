"""sbom.etzhayyim.com — SBOM artifact registry persistence (LangServer handlers).

CF Worker forwards `com.etzhayyim.apps.sbom.registerArtifact` to
`dispatcher.etzhayyim.com`; the BPMN routes the job here. This handler does
the actual psycopg2 INSERT into `vertex_sbom_artifact` and the
`vertex_sbom_component` fan-out, per ADR-2604282300 (CF Worker stays
edge-facade only).

Tables (created by `30-graph/graph-schema/migrations/20260506100000_vertex_sbom_artifact.ts`):
  vertex_sbom_artifact   — one row per registered SBOM (PK = artifactUri)
  vertex_sbom_component  — one row per CDX components[] entry

Both software SBOMs (`cargo-cyclonedx`) and vehicle BOMs
(`kami-cad-import`, CycloneDX `type: "device"`) flow through the same
handler and land in the same tables — vehicle-only fields
(`vehicle_id` / `total_mass_kg` / `declared_part_count` / `supplier_mpn`)
are nullable and only filled when present.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


_APP_DID = "did:web:sb0m001x.etzhayyim.com"

_INSERT_ARTIFACT = """
    INSERT INTO vertex_sbom_artifact (
        vertex_id, created_date, sensitivity_ord, owner_did,
        artifact_uri, format, spec_version, source_uri, source_sha256,
        license, kind, component_count,
        vehicle_id, vehicle_revision, total_mass_kg, declared_part_count,
        tool_vendor, tool_name, tool_version,
        registered_at, created_at,
        actor_did, org_did, at_did
    ) VALUES (
        %s, CURRENT_DATE, 1, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s,
        %s, %s, NULL
    )
"""

_INSERT_COMPONENT = """
    INSERT INTO vertex_sbom_component (
        vertex_id, created_date, sensitivity_ord, owner_did,
        artifact_uri, bom_ref, component_type, name, version,
        purl, cpe, license, supplier_name, supplier_mpn,
        parent_bom_ref, properties_json,
        created_at, actor_did, org_did, at_did
    ) VALUES (
        %s, CURRENT_DATE, 1, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s, NULL
    )
"""


def _pick_license(c: dict[str, Any]) -> str | None:
    licenses = c.get("licenses") or []
    if not isinstance(licenses, list):
        return None
    for entry in licenses:
        if not isinstance(entry, dict):
            continue
        expr = entry.get("expression")
        if isinstance(expr, str) and expr:
            return expr
        lic = entry.get("license")
        if isinstance(lic, dict):
            for k in ("id", "name"):
                v = lic.get(k)
                if isinstance(v, str) and v:
                    return v
    return None


def _pick_property(c: dict[str, Any], name: str) -> str | None:
    props = c.get("properties") or []
    if not isinstance(props, list):
        return None
    for p in props:
        if isinstance(p, dict) and p.get("name") == name:
            v = p.get("value")
            if isinstance(v, (str, int, float)):
                return str(v)
    return None


async def task_sbom_register_artifact(**job_vars: Any) -> dict[str, Any]:
    """Persist a CDX 1.5 / SPDX 3.0 artifact + its components into RisingWave.

    BPMN job variables (passed through from CF Worker → dispatcher):
        artifactUri          str  — `at://did:web:sb0m001x.etzhayyim.com/...`
        format               str  — "CycloneDX" | "SPDX"
        specVersion          str  — "1.5" / "1.6" / "3.0"
        sourceUri            str
        sourceSha256         str
        license              str
        kind                 str  — "software" | "vehicle"
        cdxJson              str  — full CycloneDX document (JSON string)
        vehicleId            str|None
        vehicleRevision      str|None
        totalMassKg          float|None
        declaredPartCount    int|None
        registeredAt         str  — ISO timestamp from the worker
        actorDid             str|None  — caller DID, defaults to APP_DID
        orgDid               str|None  — caller org, defaults to "anon"

    Returns:
        dict with `ok`, `artifactUri`, `componentCount`, `persistedComponents`,
        `persistence` ("rw" or "skip-no-pk"), and `kind`.
    """
    artifact_uri = (job_vars.get("artifactUri") or "").strip()
    cdx_json = job_vars.get("cdxJson") or ""
    if not artifact_uri:
        return {"ok": False, "error": "MissingProvenance", "detail": "artifactUri required"}
    if not cdx_json:
        return {"ok": False, "error": "InvalidSbom", "detail": "cdxJson required"}

    fmt = (job_vars.get("format") or "").strip()
    spec = (job_vars.get("specVersion") or "").strip()
    src_uri = (job_vars.get("sourceUri") or "").strip()
    src_sha = (job_vars.get("sourceSha256") or "").strip()
    license_expr = (job_vars.get("license") or "").strip()
    kind = (job_vars.get("kind") or "software").strip() or "software"
    registered_at = (job_vars.get("registeredAt") or "").strip()

    vehicle_id = job_vars.get("vehicleId") or None
    vehicle_rev = job_vars.get("vehicleRevision") or None
    total_mass = job_vars.get("totalMassKg")
    declared_parts = job_vars.get("declaredPartCount")

    actor_did = (job_vars.get("actorDid") or _APP_DID).strip() or _APP_DID
    org_did = (job_vars.get("orgDid") or "anon").strip() or "anon"

    try:
        cdx = json.loads(cdx_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": "InvalidSbom", "detail": f"cdxJson parse: {e}"}

    inner_format = str(cdx.get("bomFormat") or "")
    if inner_format and fmt and inner_format != fmt:
        return {
            "ok": False,
            "error": "InvalidSbom",
            "detail": f"wrapper format={fmt} but cdxJson.bomFormat={inner_format}",
        }

    components = cdx.get("components") or []
    if not isinstance(components, list):
        components = []

    tool = (cdx.get("metadata", {}) or {}).get("tools", [])
    tool_first = tool[0] if isinstance(tool, list) and tool else {}

    artifact_row = (
        artifact_uri,                              # vertex_id
        _APP_DID,                                  # owner_did
        artifact_uri,                              # artifact_uri (denorm)
        fmt or "CycloneDX",                        # format
        spec or "unknown",                         # spec_version
        src_uri,                                   # source_uri
        src_sha,                                   # source_sha256
        license_expr or "unknown",                 # license
        kind,                                      # kind
        len(components),                           # component_count
        vehicle_id,                                # vehicle_id (nullable)
        vehicle_rev,                               # vehicle_revision (nullable)
        float(total_mass) if isinstance(total_mass, (int, float)) and total_mass else None,
        int(declared_parts) if isinstance(declared_parts, (int, float)) and declared_parts else None,
        (tool_first.get("vendor") if isinstance(tool_first, dict) else None) or None,
        (tool_first.get("name") if isinstance(tool_first, dict) else None) or None,
        (tool_first.get("version") if isinstance(tool_first, dict) else None) or None,
        registered_at,                             # registered_at
        registered_at,                             # created_at
        actor_did,
        org_did,
    )

    component_rows: list[tuple[Any, ...]] = []
    for c in components:
        if not isinstance(c, dict):
            continue
        bom_ref = c.get("bom-ref")
        if not isinstance(bom_ref, str) or not bom_ref:
            continue
        component_rows.append(
            (
                f"{artifact_uri}#{bom_ref}",  # vertex_id
                _APP_DID,                     # owner_did
                artifact_uri,
                bom_ref,
                str(c.get("type") or "library"),
                str(c.get("name") or "") or None,
                str(c.get("version") or "") or None,
                str(c.get("purl") or "") or None,
                str(c.get("cpe") or "") or None,
                _pick_license(c),
                ((c.get("manufacturer") or {}).get("name") if isinstance(c.get("manufacturer"), dict) else None) or None,
                _pick_property(c, "cdx:etzhayyim:vehicle:supplier_mpn"),
                _pick_property(c, "cdx:etzhayyim:vehicle:parent"),
                json.dumps(c.get("properties")) if isinstance(c.get("properties"), list) else None,
                registered_at,
                actor_did,
                org_did,
            )
        )

    persisted_components = 0
    if True:
        client = get_kotoba_client()
        _res = client.q(_INSERT_ARTIFACT, artifact_row)
        if component_rows:
            _res = client.q(_INSERT_COMPONENT, component_rows)
            persisted_components = len(component_rows)

    return {
        "ok": True,
        "artifactUri": artifact_uri,
        "componentCount": len(components),
        "persistedComponents": persisted_components,
        "persistence": "rw",
        "kind": kind,
        "phase": "B-persist",
    }


_INSERT_VULN_MATCH = """
    INSERT INTO vertex_sbom_vuln_match (
        vertex_id, created_date, sensitivity_ord, owner_did,
        artifact_uri, component_bom_ref, component_purl, component_cpe,
        cve_id, severity, cvss_score, matched_via, matched_at,
        created_at, actor_did, org_did, at_did
    ) VALUES (
        %s, CURRENT_DATE, 1, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, NULL
    )
"""


async def task_sbom_run_vuln_match(**job_vars: Any) -> dict[str, Any]:
    """Match the just-persisted components against vertex_cve_entry.

    Runs immediately after `task_sbom_register_artifact` in the BPMN.
    Joins by SQL pattern: `component.purl LIKE cve.affected_purl_pattern`
    OR `component.cpe LIKE cve.affected_cpe_pattern`. Inserts one
    `vertex_sbom_vuln_match` row per (component, cve) pair. Idempotent:
    re-run on the same artifact overwrites by PK.

    BPMN job variables (taken from prior step output):
        artifactUri          str  — required
        actorDid             str|None
        orgDid               str|None

    Returns:
        { ok, vulnMatchCount, severityCounts: {critical, high, medium, low, unknown} }.
        When `vertex_cve_entry` is empty (typical pre-Phase-D bootstrap)
        returns vulnMatchCount = 0 cleanly without erroring.
    """
    artifact_uri = (job_vars.get("artifactUri") or "").strip()
    if not artifact_uri:
        return {"ok": False, "error": "MissingProvenance", "detail": "artifactUri required"}

    actor_did = (job_vars.get("actorDid") or _APP_DID).strip() or _APP_DID
    org_did = (job_vars.get("orgDid") or "anon").strip() or "anon"

    matched_at = job_vars.get("matchedAt") or job_vars.get("registeredAt") or ""
    if not matched_at:
        # Fall back to a deterministic timestamp the worker can stamp.
        from datetime import datetime, timezone
        matched_at = datetime.now(timezone.utc).isoformat()

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
    rows: list[tuple[Any, ...]] = []

    if True:

        client = get_kotoba_client()
        # Pull this artifact's components.
        _res = client.q(
            """
            SELECT bom_ref, purl, cpe
              FROM vertex_sbom_component
             WHERE artifact_uri = %s
            """,
            (artifact_uri,),
        )
        components = _res
        if not components:
            return {
                "ok": True,
                "artifactUri": artifact_uri,
                "vulnMatchCount": 0,
                "severityCounts": severity_counts,
                "note": "no components for this artifact",
            }

        # For each component, scan the CVE catalog for purl / cpe matches.
        # The CVE patterns are LIKE strings (e.g. `pkg:cargo/serde@%`,
        # `cpe:2.3:a:vendor:product:*:*:*:*:*:*:*:*`). When the catalog
        # is empty (Phase D not yet seeded by yabai) the inner SELECT
        # returns no rows and we exit cleanly with zero matches.
        for c in components:
            bom_ref, purl, cpe = (c[0] or "", c[1] or "", c[2] or "")
            if not (purl or cpe):
                continue
            _res = client.q(
                """
                SELECT cve_id, severity, cvss_score, source
                  FROM vertex_cve_entry
                 WHERE (%s <> '' AND affected_purl_pattern IS NOT NULL
                                  AND %s LIKE affected_purl_pattern)
                    OR (%s <> '' AND affected_cpe_pattern  IS NOT NULL
                                  AND %s LIKE affected_cpe_pattern)
                """,
                (purl, purl, cpe, cpe),
            )
            for cve_row in _res:
                cve_id, sev, score, _src = (cve_row[0], cve_row[1] or "unknown",
                                            cve_row[2], cve_row[3] or "unknown")
                via = "purl" if (purl and purl) else "cpe"
                rows.append((
                    f"{artifact_uri}#{bom_ref}::{cve_id}",  # vertex_id
                    _APP_DID,                                # owner_did
                    artifact_uri, bom_ref, purl or None, cpe or None,
                    cve_id, sev, float(score) if score is not None else None,
                    via, matched_at,
                    matched_at, actor_did, org_did,
                ))
                bucket = sev.lower() if isinstance(sev, str) else "unknown"
                if bucket not in severity_counts:
                    bucket = "unknown"
                severity_counts[bucket] += 1

        if rows:
            _res = client.q(_INSERT_VULN_MATCH, rows)

    return {
        "ok": True,
        "artifactUri": artifact_uri,
        "vulnMatchCount": len(rows),
        "severityCounts": severity_counts,
        "phase": "C-vuln-match",
    }


async def task_sbom_recall(**job_vars: Any) -> dict[str, Any]:
    """Phase D — blast-radius lookup by supplier (and optional MPN).

    Returns every SBOM artifact whose component has the given
    `supplier_name` (and `supplier_mpn` when set). The result row joins
    component → artifact → vuln-match counts so a single response gives
    the caller every datum needed to triage a Takata-style recall.
    """
    supplier = (job_vars.get("supplier") or "").strip()
    if not supplier:
        return {"ok": False, "error": "BadRequest", "detail": "supplier required"}

    mpn = (job_vars.get("mpn") or "").strip() or None
    kind = (job_vars.get("kind") or "").strip() or None
    limit = int(job_vars.get("limit") or 50)
    offset = int(job_vars.get("offset") or 0)
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    if offset < 0:
        offset = 0

    matches: list[dict[str, Any]] = []
    total = 0
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT a.vertex_id, a.kind, a.vehicle_id, a.vehicle_revision,
                   a.source_uri, a.registered_at,
                   c.bom_ref, c.name, c.version, c.supplier_name, c.supplier_mpn,
                   (SELECT COUNT(*) FROM vertex_sbom_vuln_match v
                     WHERE v.artifact_uri = a.artifact_uri
                       AND v.component_bom_ref = c.bom_ref) AS vuln_count
              FROM vertex_sbom_component c
              JOIN vertex_sbom_artifact a ON c.artifact_uri = a.artifact_uri
             WHERE c.supplier_name = %s
               AND (%s IS NULL OR c.supplier_mpn = %s)
               AND (%s IS NULL OR a.kind = %s)
             ORDER BY a.registered_at DESC
             LIMIT %s OFFSET %s
            """,
            (supplier, mpn, mpn, kind, kind, limit, offset),
        )
        for row in _res:
            matches.append(
                {
                    "artifactUri": row[0],
                    "kind": row[1],
                    "vehicleId": row[2] or "",
                    "vehicleRevision": row[3] or "",
                    "sourceUri": row[4] or "",
                    "registeredAt": row[5] or "",
                    "componentBomRef": row[6],
                    "componentName": row[7] or "",
                    "componentVersion": row[8] or "",
                    "supplier": row[9] or "",
                    "supplierMpn": row[10] or "",
                    "vulnCount": int(row[11] or 0),
                }
            )

        _res = client.q(
            """
            SELECT COUNT(*) FROM vertex_sbom_component c
              JOIN vertex_sbom_artifact a ON c.artifact_uri = a.artifact_uri
             WHERE c.supplier_name = %s
               AND (%s IS NULL OR c.supplier_mpn = %s)
               AND (%s IS NULL OR a.kind = %s)
            """,
            (supplier, mpn, mpn, kind, kind),
        )
        row = (_res[0] if _res else None)
        total = int(row[0] if row and row[0] is not None else 0)

    return {
        "ok": True,
        "matches": matches,
        "total": total,
        "limit": limit,
        "offset": offset,
        "supplier": supplier,
        "mpn": mpn or "",
        "kind": kind or "",
    }


# ──────────────────────────────────────────────────────────────────────
# Phase C feeder — OSV ingest into vertex_cve_entry
# ──────────────────────────────────────────────────────────────────────

_OSV_QUERY_URL = "https://api.osv.dev/v1/query"

# OSV ecosystem name → purl type. Source:
#   https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst
_OSV_PURL_TYPE = {
    "npm": "npm",
    "PyPI": "pypi",
    "Maven": "maven",
    "Go": "golang",
    "RubyGems": "gem",
    "Hex": "hex",
    "NuGet": "nuget",
    "Packagist": "composer",
    "Pub": "pub",
    "crates.io": "cargo",
    "Cargo": "cargo",
    "GitHub Actions": "githubactions",
    "Linux": "deb",
    "Debian": "deb",
    "Ubuntu": "deb",
    "Alpine": "apk",
    "Rocky Linux": "rpm",
    "AlmaLinux": "rpm",
    "Red Hat": "rpm",
    "openSUSE": "rpm",
    "SUSE": "rpm",
}

_INSERT_CVE_ENTRY = """
    INSERT INTO vertex_cve_entry (
        vertex_id, created_date, sensitivity_ord, owner_did,
        cve_id, severity, cvss_score, summary, published_at, modified_at,
        affected_purl_pattern, affected_cpe_pattern, source, source_url,
        created_at, actor_did, org_did, at_did
    ) VALUES (
        %s, CURRENT_DATE, 1, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, NULL
    )
"""


def _osv_severity(vuln: dict[str, Any]) -> tuple[str, float | None]:
    sev_list = vuln.get("severity") or []
    if isinstance(sev_list, list):
        for s in sev_list:
            if not isinstance(s, dict):
                continue
            t = s.get("type") or ""
            score = s.get("score")
            if t.startswith("CVSS_") and isinstance(score, str):
                # Score is a CVSS vector string; the numeric score is in the
                # `database_specific.severity` half of the time. Fall back to
                # textual category.
                try:
                    # CVSS vectors have form "CVSS:3.1/AV:N/.../E:H" — no
                    # numeric here. Use the textual severity category.
                    pass
                except ValueError:
                    pass
    db_spec = vuln.get("database_specific") or {}
    if isinstance(db_spec, dict):
        sev = db_spec.get("severity")
        if isinstance(sev, str):
            sev_lower = sev.strip().lower()
            mapping = {
                "critical": ("critical", 9.5),
                "high": ("high", 7.5),
                "moderate": ("medium", 5.0),
                "medium": ("medium", 5.0),
                "low": ("low", 2.5),
            }
            if sev_lower in mapping:
                return mapping[sev_lower]
    return ("unknown", None)


def _purl_pattern(ecosystem: str, package_name: str) -> str | None:
    purl_type = _OSV_PURL_TYPE.get(ecosystem)
    if not purl_type:
        return None
    # Maven coordinates are `groupId:artifactId`. Convert ':' → '/'.
    if purl_type == "maven" and ":" in package_name:
        package_name = package_name.replace(":", "/", 1)
    return f"pkg:{purl_type}/{package_name}@%"


async def task_sbom_cve_ingest_osv(**job_vars: Any) -> dict[str, Any]:
    """Pull recent vulnerabilities from osv.dev into vertex_cve_entry.

    OSV's `POST /v1/query` accepts an empty body to return a paged list
    of all vulnerabilities, or a `{ "package": { "ecosystem": ... } }`
    body to scope by ecosystem. We page via `page_token` until the
    requested `limit` is reached or the catalog is exhausted.
    """
    ecosystem = (job_vars.get("ecosystem") or "").strip() or None
    modified_since = (job_vars.get("modifiedSince") or "").strip() or None
    limit = int(job_vars.get("limit") or 1000)
    if limit < 1:
        limit = 1
    if limit > 10_000:
        limit = 10_000

    body_template: dict[str, Any] = {}
    if ecosystem:
        body_template["package"] = {"ecosystem": ecosystem}

    ingested = 0
    page_token: str | None = None
    rows: list[tuple[Any, ...]] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    while ingested < limit:
        body = dict(body_template)
        if page_token:
            body["page_token"] = page_token
        req = urllib.request.Request(
            _OSV_QUERY_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                doc = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"ok": False, "error": "OsvUnreachable", "detail": str(e), "ingested": ingested}

        vulns = doc.get("vulns") or []
        if not isinstance(vulns, list):
            break

        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            cve_id = vuln.get("id")
            if not isinstance(cve_id, str) or not cve_id:
                continue
            modified = vuln.get("modified") or ""
            if modified_since and isinstance(modified, str) and modified < modified_since:
                continue

            sev_label, sev_score = _osv_severity(vuln)
            summary = vuln.get("summary") or ""
            published = vuln.get("published") or ""

            # Affected packages → one row per (cve, package). The PK is
            # synthesized so the same CVE × package collides on re-ingest.
            affected = vuln.get("affected") or []
            if not isinstance(affected, list) or not affected:
                # Vulnerabilities with no machine-readable affected list —
                # still record the CVE itself with a NULL purl pattern.
                rows.append((
                    f"cve://osv/{cve_id}",
                    _APP_DID,
                    cve_id, sev_label, sev_score, summary[:1024],
                    published, modified,
                    None, None, "osv",
                    f"https://osv.dev/vulnerability/{cve_id}",
                    now_iso, _APP_DID, "anon",
                ))
            else:
                for a in affected:
                    if not isinstance(a, dict):
                        continue
                    pkg = a.get("package") or {}
                    if not isinstance(pkg, dict):
                        continue
                    pkg_eco = pkg.get("ecosystem") or ""
                    pkg_name = pkg.get("name") or ""
                    pattern = _purl_pattern(pkg_eco, pkg_name)
                    if not pattern:
                        continue
                    vid = f"cve://osv/{cve_id}#{pkg_eco}/{pkg_name}"
                    rows.append((
                        vid,
                        _APP_DID,
                        cve_id, sev_label, sev_score, summary[:1024],
                        published, modified,
                        pattern, None, "osv",
                        f"https://osv.dev/vulnerability/{cve_id}",
                        now_iso, _APP_DID, "anon",
                    ))
            ingested += 1
            if ingested >= limit:
                break

        page_token = doc.get("next_page_token") or None
        if not page_token:
            break
        # Light backoff so we don't hammer osv.dev.
        time.sleep(0.05)

    if rows:
        if True:
            client = get_kotoba_client()
            _res = client.q(_INSERT_CVE_ENTRY, rows)

    return {
        "ok": True,
        "ingested": ingested,
        "rows": len(rows),
        "ecosystem": ecosystem or "",
        "modifiedSince": modified_since or "",
    }


def register(worker: Any, *, timeout_ms: int = 600_000) -> None:
    """Wire sbom task types onto the shared LangServer worker."""
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.sbom.registerArtifact",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_sbom_register_artifact)
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.sbom.runVulnMatch",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_sbom_run_vuln_match)
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.sbom.recall",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_sbom_recall)
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.sbom.cveIngestOsv",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_sbom_cve_ingest_osv)


__all__ = [
    "register",
    "task_sbom_register_artifact",
    "task_sbom_run_vuln_match",
    "task_sbom_recall",
    "task_sbom_cve_ingest_osv",
]
