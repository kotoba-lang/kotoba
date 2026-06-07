"""ShareMouse v7.0.15 Pro config + screenshot writer.

Captures the structured data visible in the two Preferences screens (Network
+ Clients) as `vertex_app_setting` rows + `vertex_app_accepted_peer` rows +
`vertex_app_port_binding` rows, joins them to the running scan, and records
the two preference-pane screenshots as `vertex_app_screenshot` referencing an
`vertex_blob_ipfs` row.

Bundle ID
---------
ShareMouse's bundle id is `com.bartelsmedia.sharemouse` (confirmed via
Info.plist inspection). If the host scan hasn't captured it yet, this
module upserts the `vertex_app_installed` row directly.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Iterable

from kotodama import db_sync
from kotodama.host_inventory.blob import (
    BlobMeta,
    blob_from_path,
    placeholder_blob_for,
    upsert_blob,
)


SHAREMOUSE_BUNDLE_ID = "com.bartelsmedia.sharemouse"
SHAREMOUSE_APP_NAME = "ShareMouse"


# ── Settings captured from the screenshots (2026-05-12 19:30 JST). ─────────
SHAREMOUSE_SETTINGS_v7_0_15: dict[str, dict[str, Any]] = {
    "network.mode": {
        "value": "unprotected",
        "value_type": "enum",
        "notes": "Unprotected mode — client visible from other clients. No password set.",
    },
    "network.password_protection": {"value": "false", "value_type": "bool"},
    "network.adapter": {"value": "All", "value_type": "string"},
    "network.tcp_port": {"value": "6555", "value_type": "int"},
    "network.udp_port": {"value": "1046", "value_type": "int"},
    "network.use_ipv6": {"value": "false", "value_type": "bool"},
    "clients.broadcast_udp": {"value": "true", "value_type": "bool"},
    "updates.check_kind": {"value": "important-only", "value_type": "enum"},
    "updates.install_automatically": {"value": "true", "value_type": "bool"},
}

# Accepted peer rows visible in the Clients tab.
SHAREMOUSE_ACCEPTED_PEERS_v7_0_15: list[dict[str, Any]] = [
    {"peer_address": "192.168.1.10", "peer_port": 6555},
    {"peer_address": "192.168.1.66", "peer_port": 6555},
    {"peer_address": "192.168.1.16", "peer_port": 6555},
    {"peer_address": "192.168.1.5",  "peer_port": 6555},
]

# Port bindings declared by the app config.
SHAREMOUSE_PORT_BINDINGS_v7_0_15: list[dict[str, Any]] = [
    {"protocol": "tcp", "port": 6555, "bind_address": "0.0.0.0", "is_listening": True},
    {"protocol": "udp", "port": 1046, "bind_address": "0.0.0.0", "is_listening": True},
]


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today() -> date:
    return datetime.utcnow().date()


def _ensure_app(bundle_id: str, app_name: str, version: str, owner_did: str | None) -> str:
    app_vid = f"app:{bundle_id}"
    now = _now_iso()
    today = _today()
    db_sync.execute("DELETE FROM vertex_app_installed WHERE vertex_id = %s", (app_vid,))
    db_sync.execute(
        """
        INSERT INTO vertex_app_installed (
          vertex_id, created_date, sensitivity_ord, owner_did,
          bundle_id, app_name, vendor, category, install_kind,
          first_seen_at, last_seen_at, latest_version, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            app_vid, today, 100, owner_did,
            bundle_id, app_name, "Bartels Media GmbH",
            "public.app-category.productivity", "direct",
            now, now, version, now,
        ),
    )
    return app_vid


def persist_sharemouse_config(
    *,
    scan_id: str,
    device_vid: str,
    app_version: str = "7.0.15",
    owner_did: str | None = None,
    config_source: str = "preferences-pane-screenshot",
) -> dict[str, str]:
    """Write the ShareMouse config snapshot + settings + peers + ports."""
    app_vid = _ensure_app(SHAREMOUSE_BUNDLE_ID, SHAREMOUSE_APP_NAME, app_version, owner_did)
    now = _now_iso()
    today = _today()

    snapshot_vid = f"app_config:{scan_id}:{SHAREMOUSE_BUNDLE_ID}"
    db_sync.execute(
        """
        INSERT INTO vertex_app_config_snapshot (
          vertex_id, created_date, sensitivity_ord, owner_did,
          scan_id, device_vid, app_vid, bundle_id,
          config_kind, config_source, source_path, config_version,
          captured_at, setting_count, notes, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            snapshot_vid, today, 100, owner_did,
            scan_id, device_vid, app_vid, SHAREMOUSE_BUNDLE_ID,
            "preferences", config_source, "ui:Preferences", app_version,
            now, len(SHAREMOUSE_SETTINGS_v7_0_15),
            "Captured from ShareMouse Preferences > Network + Clients tabs.",
            now,
        ),
    )

    db_sync.execute(
        """
        INSERT INTO edge_app_has_config_snapshot (
          edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
          owner_did, scan_id, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            f"edge:app-cfg:{scan_id}:{SHAREMOUSE_BUNDLE_ID}",
            app_vid, snapshot_vid, today, 100, owner_did, scan_id, now,
        ),
    )

    # Settings
    for key, meta in SHAREMOUSE_SETTINGS_v7_0_15.items():
        setting_vid = f"app_setting:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:{key}"
        db_sync.execute(
            """
            INSERT INTO vertex_app_setting (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, snapshot_vid, app_vid, bundle_id,
              setting_key, setting_value, value_type,
              is_secret, is_default, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                setting_vid, today, 100, owner_did,
                scan_id, snapshot_vid, app_vid, SHAREMOUSE_BUNDLE_ID,
                key, str(meta["value"]), meta["value_type"],
                bool(meta.get("is_secret", False)),
                bool(meta.get("is_default", False)),
                now,
            ),
        )
        db_sync.execute(
            """
            INSERT INTO edge_config_snapshot_has_setting (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, setting_key, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                f"edge:snap-setting:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:{key}",
                snapshot_vid, setting_vid, today, 100, owner_did,
                scan_id, key, now,
            ),
        )

    # Accepted peers
    for peer in SHAREMOUSE_ACCEPTED_PEERS_v7_0_15:
        peer_vid = (
            f"app_peer:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:"
            f"{peer['peer_address']}:{peer['peer_port']}"
        )
        db_sync.execute(
            """
            INSERT INTO vertex_app_accepted_peer (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, app_vid, bundle_id,
              peer_address, peer_port, peer_label, peer_kind,
              is_active, last_seen_at, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                peer_vid, today, 100, owner_did,
                scan_id, device_vid, app_vid, SHAREMOUSE_BUNDLE_ID,
                peer["peer_address"], peer["peer_port"],
                peer.get("peer_label"), "sharemouse-client",
                True, now, now,
            ),
        )
        db_sync.execute(
            """
            INSERT INTO edge_app_accepts_peer (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, peer_address, peer_port, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                f"edge:app-peer:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:{peer['peer_address']}",
                app_vid, peer_vid, today, 100, owner_did,
                scan_id, peer["peer_address"], peer["peer_port"], now,
            ),
        )

        # Optional join: if this IP was observed in vertex_network_host
        # for the same scan, write a peer→host edge so reachability MV
        # can compute is_reachable directly without re-joining.
        rows = db_sync.fetch_all(
            "SELECT vertex_id FROM vertex_network_host WHERE scan_id = %s AND ip = %s LIMIT 5",
            (scan_id, peer["peer_address"]),
        )
        for (host_vid,) in rows:
            db_sync.execute(
                """
                INSERT INTO edge_peer_resolves_host (
                  edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
                  owner_did, scan_id, ip, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    f"edge:peer-host:{scan_id}:{peer['peer_address']}:{host_vid[-12:]}",
                    peer_vid, host_vid, today, 100, owner_did,
                    scan_id, peer["peer_address"], now,
                ),
            )

    # Port bindings
    for binding in SHAREMOUSE_PORT_BINDINGS_v7_0_15:
        binding_vid = (
            f"app_port:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:"
            f"{binding['protocol']}:{binding['port']}"
        )
        db_sync.execute(
            """
            INSERT INTO vertex_app_port_binding (
              vertex_id, created_date, sensitivity_ord, owner_did,
              scan_id, device_vid, app_vid, bundle_id,
              protocol, port, bind_address, state, is_listening,
              pid, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                binding_vid, today, 100, owner_did,
                scan_id, device_vid, app_vid, SHAREMOUSE_BUNDLE_ID,
                binding["protocol"], binding["port"],
                binding["bind_address"], "declared", binding["is_listening"],
                None, now,
            ),
        )
        db_sync.execute(
            """
            INSERT INTO edge_app_binds_port (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, protocol, port, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                f"edge:app-port:{scan_id}:{SHAREMOUSE_BUNDLE_ID}:{binding['protocol']}:{binding['port']}",
                app_vid, binding_vid, today, 100, owner_did,
                scan_id, binding["protocol"], binding["port"], now,
            ),
        )

    return {
        "app_vid": app_vid,
        "snapshot_vid": snapshot_vid,
    }


@dataclass
class ScreenshotSpec:
    label: str
    description: str
    blob: BlobMeta | None = None
    width_px: int | None = None
    height_px: int | None = None


def persist_screenshot(
    spec: ScreenshotSpec,
    *,
    scan_id: str,
    device_vid: str,
    app_vid: str | None = None,
    bundle_id: str | None = None,
    owner_did: str | None = None,
    source: str = "user-upload",
) -> dict[str, str]:
    """Insert a screenshot row + blob + edges."""
    blob = spec.blob or placeholder_blob_for(spec.label or spec.description)
    blob_vid = upsert_blob(blob, owner_did=owner_did)
    now = _now_iso()
    today = _today()

    screenshot_vid = f"screenshot:{scan_id}:{uuid.uuid4().hex[:12]}"
    db_sync.execute(
        """
        INSERT INTO vertex_app_screenshot (
          vertex_id, created_date, sensitivity_ord, owner_did,
          scan_id, device_vid, app_vid, bundle_id, display_vid,
          blob_cid, blob_vid, label, description, source,
          width_px, height_px, captured_at, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            screenshot_vid, today, 100, owner_did,
            scan_id, device_vid, app_vid, bundle_id, None,
            blob.cid, blob_vid, spec.label, spec.description, source,
            spec.width_px, spec.height_px, now, now,
        ),
    )
    db_sync.execute(
        """
        INSERT INTO edge_screenshot_blob (
          edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
          owner_did, scan_id, cid, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            f"edge:scr-blob:{screenshot_vid[-12:]}",
            screenshot_vid, blob_vid, today, 100, owner_did,
            scan_id, blob.cid, now,
        ),
    )
    if app_vid:
        db_sync.execute(
            """
            INSERT INTO edge_screenshot_depicts_app (
              edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
              owner_did, scan_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                f"edge:scr-app:{screenshot_vid[-12:]}",
                screenshot_vid, app_vid, today, 100, owner_did, scan_id, now,
            ),
        )
    db_sync.execute(
        """
        INSERT INTO edge_device_has_screenshot (
          edge_id, src_vid, dst_vid, created_date, sensitivity_ord,
          owner_did, scan_id, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            f"edge:dev-scr:{screenshot_vid[-12:]}",
            device_vid, screenshot_vid, today, 100, owner_did, scan_id, now,
        ),
    )
    return {"screenshot_vid": screenshot_vid, "blob_vid": blob_vid, "cid": blob.cid}


def persist_sharemouse_screenshots(
    *,
    scan_id: str,
    device_vid: str,
    app_vid: str,
    network_image_path: str | None = None,
    clients_image_path: str | None = None,
    owner_did: str | None = None,
) -> list[dict[str, str]]:
    """Persist the two ShareMouse preference-pane screenshots.

    Pass real file paths to compute real content-addressed CIDs. If a
    path is None, a deterministic placeholder CID is written instead.
    """
    results: list[dict[str, str]] = []

    def _spec_for(image_path: str | None, label: str, descr: str) -> ScreenshotSpec:
        blob = blob_from_path(image_path) if image_path and os.path.isfile(image_path) else None
        return ScreenshotSpec(label=label, description=descr, blob=blob)

    network_spec = _spec_for(
        network_image_path,
        "ShareMouse Preferences — Network tab",
        "v7.0.15 Pro / Unprotected mode / TCP 6555 / UDP 1046 / IPv6 off / "
        "Network adapter=All / Auto-update on (important only)",
    )
    clients_spec = _spec_for(
        clients_image_path,
        "ShareMouse Preferences — Clients tab",
        "v7.0.15 Pro / Accepted clients: 192.168.1.{10,66,16,5}:6555 / "
        "Broadcast own connection info via UDP=on",
    )
    for spec in (network_spec, clients_spec):
        r = persist_screenshot(
            spec,
            scan_id=scan_id,
            device_vid=device_vid,
            app_vid=app_vid,
            bundle_id=SHAREMOUSE_BUNDLE_ID,
            owner_did=owner_did,
            source="user-upload" if spec.blob else "placeholder",
        )
        results.append(r)
    return results
