"""Celestial catalog ingest — HYG (stars) + Messier (deep-sky) + NGC (deep-sky).

3 LangServer task types, all R/P30D BPMN-driven:

  celestial.hyg.refresh        — HYG database (Hipparcos+Yale+Gliese, 119K stars,
                                   we filter to mag ≤ 6.5 = ~9K naked-eye stars)
  celestial.messier.refresh    — Messier 110 catalog (galaxies + nebulae + clusters)
  celestial.ngc.refresh        — NGC/IC top brightest 1000 deep-sky objects

Sources (all CC-public):
  HYG v3.5 (CC0):  https://github.com/astronexus/HYG-Database/raw/master/hyg/CURRENT/hygdata_v41.csv
  Messier (PD):     https://en.wikipedia.org/wiki/List_of_Messier_objects (data table mirror)
  NGC (CC-BY 4.0):  https://github.com/mattiaverga/OpenNGC

Coordinates stored as right ascension (ra_deg, 0..360) + declination (dec_deg, -90..90)
in ICRS J2000 frame. Distance in light-years (distance_ly) when known.

Schema target: vertex_celestial_catalog (3 rows: hyg-v41 / messier / openngc)
              vertex_celestial_object (~10K rows total)
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
import io as _io
import json
import sys as _sys
import time
import urllib.request
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:maps.etzhayyim.com:tentai"
DEFAULT_REPO = "did:web:maps.etzhayyim.com"

HYG_URL = "https://github.com/astronexus/HYG-Database/raw/main/hyg/CURRENT/hygdata_v41.csv"
MESSIER_URL = "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv"
NGC_URL = "https://raw.githubusercontent.com/mattiaverga/OpenNGC/master/database_files/NGC.csv"


def _now_iso() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _today_date() -> str:
    return _now_iso()[:10]


def _new_run_id(prefix: str) -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _http_get_text(url: str, *, timeout: float = 120.0) -> tuple[int, str]:
    """Buffered fetch — used by NGC (~3 MB) where holding the body in RAM
    is fine. HYG (~30 MB) uses _http_iter_lines below to avoid OOM in the
    pod (peak RSS for `read().decode()` of 30 MB ~ 90 MB after copies)."""
    req = Request(url, headers={"user-agent": "etzhayyim-maps-tentai/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return getattr(resp, "status", 200), resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, ""
    except (URLError, OSError):
        return 0, ""


def _http_iter_lines(url: str, *, timeout: float = 180.0):
    """Stream a remote CSV line-by-line (yields decoded str). Caller wraps
    the iterator in csv.DictReader to avoid materializing the whole body."""
    req = Request(url, headers={"user-agent": "etzhayyim-maps-tentai/1.0"}, method="GET")
    resp = urllib.request.urlopen(req, timeout=timeout)
    try:
        for raw in resp:  # urlopen returns an iterable of byte chunks (lines).
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass





def _ensure_catalog(catalog_id: str, authority: str, version: str,
                    name: str, display_name: str, description: str) -> None:
    """Idempotent catalog row upsert (kotoba Datom log overwrite)."""
    client = get_kotoba_client()
    vid = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.celestialCatalog/{catalog_id}"
    did = f"did:web:maps.etzhayyim.com:tentai:catalog:{catalog_id}"
    today = _today_date()
    catalog_row = {
        "vertex_id": vid,
        "label": "CelestialCatalog",
        "did": did,
        "rkey": catalog_id,
        "repo": did,
        "name": name,
        "display_name": display_name,
        "description": description,
        "catalog_id": catalog_id,
        "authority": authority,
        "version": version,
        "frame": "ICRS J2000",
        "coverage_kind": "all-sky",
        "metadata_json": "{}",
        "actor_did": ACTOR_DID,
        "org_did": "anon",
        "sensitivity_ord": 1,
        "owner_did": DEFAULT_REPO,
        "created_at": today,
    }
    client.insert_row("vertex_celestial_catalog", catalog_row)


def _to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ──────────────────────────────────────────────────────────────────────
# HYG — naked-eye stars
# ──────────────────────────────────────────────────────────────────────

def task_celestial_hyg_refresh(mag_max: float = 6.5, max_rows: int = 12_000) -> dict[str, Any]:
    """Fetch HYG v3.5 CSV, INSERT vertex_celestial_object for stars with mag ≤ mag_max.

    HYG schema (v41): id,hip,hd,hr,gl,bf,proper,ra,dec,dist,pmra,pmdec,rv,mag,
                      absmag,spect,ci,x,y,z,vx,vy,vz,rarad,decrad,...
    ra in HOURS (0..24), dec in DEGREES (-90..90), dist in PARSECS, mag = vmag.
    """
    run_id = _new_run_id("hyg")
    _csv.field_size_limit(_sys.maxsize)

    catalog_id = "hyg-v41"
    written = 0
    skipped = 0
    today = _today_date()

    # Streaming iter avoids holding the 30 MB CSV body in RAM all at once
    # (previously OOM-killed the pod).
    try:
        line_iter = _http_iter_lines(HYG_URL, timeout=180.0)
    except (HTTPError, URLError, OSError) as e:
        return {"runId": run_id, "ingested": 0, "error": f"fetch: {e}"}
    reader = _csv.DictReader(line_iter)

    client = get_kotoba_client()
    _ensure_catalog(
        catalog_id, "Astronexus / HYG Database", "v41",
        "HYG v3.5", "HYG Database (Hipparcos + Yale + Gliese)",
        "119,614 stars combining Hipparcos, Yale Bright Star, and Gliese catalogs (CC0).",
    )
    for row in reader:
        if written >= max_rows:
            break
        mag = _to_float(row.get("mag"))
        if mag is None or mag > mag_max:
            skipped += 1
            continue
        ra_hours = _to_float(row.get("ra"))
        dec_deg = _to_float(row.get("dec"))
        if ra_hours is None or dec_deg is None:
            skipped += 1
            continue
        ra_deg = (ra_hours * 15.0) % 360.0
        dist_pc = _to_float(row.get("dist"))
        dist_ly = dist_pc * 3.26156 if dist_pc and dist_pc > 0 else None
        spect = (row.get("spect") or "").strip() or None
        proper = (row.get("proper") or "").strip()
        hip = (row.get("hip") or "").strip()
        hd = (row.get("hd") or "").strip()
        hr = (row.get("hr") or "").strip()
        ident = proper or (f"HR {hr}" if hr else None) or (f"HIP {hip}" if hip else None) or (f"HD {hd}" if hd else None) or f"HYG-{row.get('id') or written}"
        object_id = f"hyg-{row.get('id') or hip or hd or hr or written}"
        vid = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.celestialObject/{object_id}"
        did = f"did:web:maps.etzhayyim.com:tentai:object:{object_id}"
        # Render priority: brighter star = higher priority. Inverse mag.
        render_priority = max(1, int((mag_max - mag) * 10))
        object_row = {
            "vertex_id": vid,
            "label": "CelestialObject",
            "did": did,
            "rkey": object_id,
            "repo": did,
            "name": ident,
            "display_name": ident,
            "description": f"V mag {mag:.2f}, spectral class {spect or '?'}",
            "category": "star",
            "object_id": object_id,
            "catalog_id": catalog_id,
            "object_kind": "star",
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "distance_ly": dist_ly,
            "spectral_class": spect,
            "render_priority": render_priority,
            "source_ref": HYG_URL,
            "status": "active",
            "metadata_json": json.dumps({"mag": mag, "hip": hip, "hd": hd, "hr": hr}),
            "actor_did": ACTOR_DID,
            "org_did": "anon",
            "sensitivity_ord": 1,
            "owner_did": DEFAULT_REPO,
            "created_at": today,
        }
        try:
            client.insert_row("vertex_celestial_object", object_row)
            written += 1
        except Exception:  # noqa: BLE001
            skipped += 1
            continue

    return {"runId": run_id, "ingested": written, "skipped": skipped, "magMax": mag_max}


# ──────────────────────────────────────────────────────────────────────
# OpenNGC — deep-sky (galaxies, nebulae, clusters). Includes Messier
# ──────────────────────────────────────────────────────────────────────

def task_celestial_ngc_refresh(max_rows: int = 5_000) -> dict[str, Any]:
    """Fetch OpenNGC catalog CSV, INSERT galaxy/nebula/cluster objects.

    OpenNGC schema (semi-colon delimited): Name;Type;RA;Dec;Const;MajAx;MinAx;
    PosAng;B-Mag;V-Mag;J-Mag;H-Mag;K-Mag;SurfBr;Hubble;Pax;Pm-RA;Pm-Dec;...

    Type codes:
      G   = galaxy
      OCl = open cluster
      GCl = globular cluster
      PN  = planetary nebula
      EmN = emission nebula
      DN  = dark nebula
      RfN = reflection nebula
      Neb = nebula (generic)
      *   = single star
      **  = double star
      Ast = asterism
      ... etc.

    RA in 'HH:MM:SS.ss' format, Dec in 'sDD:MM:SS.s'.
    """
    run_id = _new_run_id("ngc")
    _csv.field_size_limit(_sys.maxsize)
    status, raw = _http_get_text(NGC_URL, timeout=180.0)
    if status != 200 or not raw:
        return {"runId": run_id, "ingested": 0, "error": f"http {status}"}

    catalog_id = "openngc"
    written = 0
    skipped = 0
    messier_count = 0
    today = _today_date()
    # OpenNGC is ;-delimited.
    reader = _csv.DictReader(_io.StringIO(raw), delimiter=";")

    def parse_ra(s: str) -> float | None:
        try:
            parts = s.strip().split(":")
            if len(parts) != 3:
                return None
            h, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
            return ((h + m / 60.0 + sec / 3600.0) * 15.0) % 360.0
        except (ValueError, AttributeError):
            return None

    def parse_dec(s: str) -> float | None:
        try:
            s = s.strip()
            sign = -1.0 if s.startswith("-") else 1.0
            s = s.lstrip("+-")
            parts = s.split(":")
            if len(parts) != 3:
                return None
            d, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
            return sign * (d + m / 60.0 + sec / 3600.0)
        except (ValueError, AttributeError):
            return None

    _kind_map = {
        "G": "galaxy", "OCl": "open_cluster", "GCl": "globular_cluster",
        "PN": "planetary_nebula", "EmN": "emission_nebula", "DN": "dark_nebula",
        "RfN": "reflection_nebula", "Neb": "nebula", "SNR": "supernova_remnant",
        "Cl+N": "cluster_with_nebula", "*": "star", "**": "double_star",
        "Ast": "asterism", "HII": "hii_region", "GPair": "galaxy_pair",
        "GTrpl": "galaxy_triple", "GGroup": "galaxy_group",
    }

    client = get_kotoba_client()
    _ensure_catalog(
        catalog_id, "OpenNGC project (Mattia Verga)", "2024-12",
        "OpenNGC", "Open New General Catalogue",
        "13,957 NGC + IC deep-sky objects (galaxies / nebulae / clusters), CC-BY-SA 4.0.",
    )
    for row in reader:
        if written >= max_rows:
            break
        name = (row.get("Name") or "").strip()
        kind_raw = (row.get("Type") or "").strip()
        if not name or not kind_raw:
            skipped += 1
            continue
        obj_kind = _kind_map.get(kind_raw, "deep_sky")
        ra_deg = parse_ra(row.get("RA") or "")
        dec_deg = parse_dec(row.get("Dec") or "")
        if ra_deg is None or dec_deg is None:
            skipped += 1
            continue
        v_mag = _to_float(row.get("V-Mag"))
        b_mag = _to_float(row.get("B-Mag"))
        const = (row.get("Const") or "").strip() or None
        major_ax = _to_float(row.get("MajAx"))
        messier = (row.get("M") or row.get("Messier") or "").strip()
        is_messier = bool(messier and messier != "0")
        if is_messier:
            messier_count += 1
        ident = name if not is_messier else f"M{messier} ({name})"
        object_id = f"ngc-{name.lower().replace(' ', '-')}"
        vid = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.celestialObject/{object_id}"
        did = f"did:web:maps.etzhayyim.com:tentai:object:{object_id}"
        mag_for_priority = v_mag if v_mag is not None else (b_mag if b_mag is not None else 12.0)
        render_priority = max(1, int((15.0 - mag_for_priority) * 5))
        metadata = {
            "vmag": v_mag, "bmag": b_mag, "constellation": const,
            "majorAxisArcmin": major_ax,
        }
        if is_messier:
            metadata["messier"] = int(messier) if messier.isdigit() else messier
        object_row = {
            "vertex_id": vid,
            "label": "CelestialObject",
            "did": did,
            "rkey": object_id,
            "repo": did,
            "name": ident,
            "display_name": ident,
            "description": f"{obj_kind} in {const}, V mag {v_mag if v_mag is not None else '?'}",
            "category": "deep_sky" if obj_kind != "star" else "star",
            "object_id": object_id,
            "catalog_id": catalog_id,
            "object_kind": obj_kind,
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "distance_ly": None,
            "spectral_class": None,
            "render_priority": render_priority,
            "source_ref": NGC_URL,
            "status": "active",
            "metadata_json": json.dumps(metadata),
            "actor_did": ACTOR_DID,
            "org_did": "anon",
            "sensitivity_ord": 1,
            "owner_did": DEFAULT_REPO,
            "created_at": today,
        }
        try:
            client.insert_row("vertex_celestial_object", object_row)
            written += 1
        except Exception:  # noqa: BLE001
            skipped += 1
            continue

    return {
        "runId": run_id,
        "ingested": written,
        "skipped": skipped,
        "messierCount": messier_count,
    }


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("celestial.hyg.refresh", task_celestial_hyg_refresh, timeout=1_800_000)
    t("celestial.ngc.refresh", task_celestial_ngc_refresh, timeout=1_800_000)


__all__ = [
    "register",
    "task_celestial_hyg_refresh",
    "task_celestial_ngc_refresh",
]
