"""kotodama.organism.sensors — content / boundary scanners + dataset sensors.

Two distinct kinds of sensor live in this package:

  1. **Scanners** (read-only content gates) — ``charter_rider.scan(...)``
     etc. Return a verdict dict; callers decide what to do.

  2. **Dataset sensors** (per ADR-2605262400) — implementations of the
     ``DatasetSensor`` Protocol that resolve IPFS-pinned subdatasets and
     yield ``SensorObservation`` records into the organism heartbeat
     tick. Sensors are PASSIVE-ONLY — they MUST NOT perform active
     network probes (G8; enforced by
     ``70-tools/scripts/lint/sensor-no-active-probe.mjs``).

Both surfaces are read-only — they never mutate inputs and never write
to PDS. The corpus assembler (cold path) and the organism tick (hot
path) are the persistence boundaries.
"""

from kotodama.organism.sensors.base import (
    DatasetPin,
    DatasetSensor,
    PiiFilterPolicy,
    SensorObservation,
    StaticPinResolver,
    Tier,
    hot_sample_bounded,
    make_observation,
    now_ms,
    stream_bounded,
)
from kotodama.organism.sensors.caida_sensor import CaidaSensor
from kotodama.organism.sensors.commoncrawl_cdx_sensor import CommonCrawlCdxSensor
from kotodama.organism.sensors.czds_sensor import CzdsSensor
from kotodama.organism.sensors.geolite2_sensor import Geolite2Sensor
from kotodama.organism.sensors.iana_root_sensor import IanaRootSensor
from kotodama.organism.sensors.openintel_sensor import OpenIntelSensor
from kotodama.organism.sensors.osm_region_sensor import OsmRegionSensor
from kotodama.organism.sensors.pii_filter import (
    RedactionStats,
    redact_emails,
    redact_payload,
    redact_phones,
    redact_postal,
    redact_text,
    redact_whois_values,
)
from kotodama.organism.sensors.rapid7_sonar_sensor import Rapid7SonarSensor
from kotodama.organism.sensors.ris_routing_sensor import RisRoutingSensor
from kotodama.organism.sensors.rir_delegated_sensor import RirDelegatedSensor
from kotodama.organism.sensors.tier_gate import SinkClassification, TierGate

__all__ = [
    "CaidaSensor",
    "CommonCrawlCdxSensor",
    "CzdsSensor",
    "DatasetPin",
    "DatasetSensor",
    "Geolite2Sensor",
    "IanaRootSensor",
    "OpenIntelSensor",
    "OsmRegionSensor",
    "PiiFilterPolicy",
    "Rapid7SonarSensor",
    "RedactionStats",
    "RirDelegatedSensor",
    "RisRoutingSensor",
    "SensorObservation",
    "SinkClassification",
    "StaticPinResolver",
    "Tier",
    "TierGate",
    "hot_sample_bounded",
    "stream_bounded",
    "make_observation",
    "now_ms",
    "redact_emails",
    "redact_payload",
    "redact_phones",
    "redact_postal",
    "redact_text",
    "redact_whois_values",
]
