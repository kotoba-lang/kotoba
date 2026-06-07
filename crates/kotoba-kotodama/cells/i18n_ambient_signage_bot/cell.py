"""
i18n_ambient_signage_bot — Robotics orchestration.

Pregel graph: receive_translation_stream → dispatch_led_display (recipe = lang_pair + brightness_lux) → i18n_telemetry → emit_display_updated.
"""

from __future__ import annotations

COUNCIL_FLEET_ATTESTATION_TX_HASH: str | None = None

if COUNCIL_FLEET_ATTESTATION_TX_HASH is None:
    raise RuntimeError(
        f"i18n_ambient_signage_bot cell scaffold-only — LOW risk category. "
        f"Council fleet.toml addition of joseph not attested."
    )
