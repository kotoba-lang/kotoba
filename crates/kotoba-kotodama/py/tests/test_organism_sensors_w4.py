"""W4 sensor tests (ADR-2605262400) — CzdsSensor + CommonCrawlCdxSensor."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from kotodama.organism.sensors import (
    CommonCrawlCdxSensor,
    CzdsSensor,
    DatasetPin,
    StaticPinResolver,
)


# ── CzdsSensor ─────────────────────────────────────────────────────────


_SAMPLE_COM_ZONE = """\
; Sample mini-zone for tests.
$TTL 86400
com.                    86400   IN      NS      a.gtld-servers.net.
example.com.            300     IN      A       203.0.113.1
example.com.            300     IN      AAAA    2001:db8::1
example.com.            300     IN      TXT     "v=spf1 mx ~all contact ops@example.com"
example.com.            86400   IN      SOA     ns.example.com. hostmaster@example.com. 2026052600 1800 900 604800 86400
test.com.               300     IN      A       198.51.100.1
"""


def _make_czds_snapshot(tmp_path: Path, tld: str, zone_text: str) -> Path:
    subdir = tmp_path / "dns" / f"czds-{tld}" / "snap-260526"
    subdir.mkdir(parents=True, exist_ok=True)
    (subdir / f"{tld}.zone").write_text(zone_text, encoding="utf-8")
    return tmp_path


def test_czds_sensor_yields_per_record_observations(tmp_path):
    annex_root = _make_czds_snapshot(tmp_path, "com", _SAMPLE_COM_ZONE)
    pins = StaticPinResolver(
        pins={
            "dns/czds-com": DatasetPin(
                name="dns/czds-com",
                revision="sha256:czds-com",
                cid_map_cid="bafy...",
                license="czds-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CzdsSensor(
        name="dns/czds-com",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    # 6 explicit RRs in the zone (NS / A / AAAA / TXT / SOA / A).
    assert len(observations) == 6
    assert all(o.tier == "C" for o in observations)
    assert all(o.internal_only is True for o in observations)
    assert all(o.payload["tld"] == "com" for o in observations)
    types = {o.payload["type"] for o in observations}
    assert {"NS", "A", "AAAA", "TXT", "SOA"} <= types


def test_czds_sensor_redacts_txt_with_email(tmp_path):
    annex_root = _make_czds_snapshot(tmp_path, "com", _SAMPLE_COM_ZONE)
    pins = StaticPinResolver(
        pins={
            "dns/czds-com": DatasetPin(
                name="dns/czds-com",
                revision="sha256:czds-com",
                cid_map_cid="bafy...",
                license="czds-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CzdsSensor(
        name="dns/czds-com",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    txt_rows = [
        o for o in sensor.stream(pin) if o.payload["type"] == "TXT"
    ]
    assert len(txt_rows) == 1
    assert "ops@example.com" not in txt_rows[0].payload["value"]
    assert "[redacted-pii]" in txt_rows[0].payload["value"]


def test_czds_sensor_hot_sample_deterministic(tmp_path):
    big_zone = _SAMPLE_COM_ZONE + "\n".join(
        f"x{i}.com.    300  IN  A  192.0.2.{i % 254 + 1}" for i in range(50)
    )
    annex_root = _make_czds_snapshot(tmp_path, "com", big_zone)
    pins = StaticPinResolver(
        pins={
            "dns/czds-com": DatasetPin(
                name="dns/czds-com",
                revision="sha256:czds-com-big",
                cid_map_cid="bafy...",
                license="czds-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CzdsSensor(
        name="dns/czds-com",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    a = [o.payload["name"] for o in sensor.hot_sample(pin, 5)]
    b = [o.payload["name"] for o in sensor.hot_sample(pin, 5)]
    assert a == b
    assert len(a) == 5


# ── CommonCrawlCdxSensor ───────────────────────────────────────────────


def _make_cdx_snapshot(
    tmp_path: Path,
    rows_canonical: list[str],
    *,
    compress: bool = True,
) -> Path:
    subdir = tmp_path / "web" / "commoncrawl-cdx" / "snap-cc-main-2026-22"
    subdir.mkdir(parents=True, exist_ok=True)
    blob = "\n".join(rows_canonical).encode("utf-8") + b"\n"
    if compress:
        (subdir / "cdx-00000.gz").write_bytes(gzip.compress(blob))
    else:
        (subdir / "cdx-00000.cdx").write_bytes(blob)
    return tmp_path


def test_commoncrawl_cdx_sensor_canonical_form(tmp_path):
    rows = [
        'com,example)/path 20260526123456 '
        '{"url":"https://example.com/path?q=secret","mime":"text/html",'
        '"status":"200","digest":"sha1:AAAA","length":"12345",'
        '"offset":"6789","filename":"warc/x.warc.gz"}',
        'org,example)/contact 20260526123500 '
        '{"url":"https://example.org/contact?email=alice@example.com",'
        '"mime":"text/html","status":"200","digest":"sha1:BBBB",'
        '"length":"500","offset":"100","filename":"warc/x.warc.gz"}',
    ]
    annex_root = _make_cdx_snapshot(tmp_path, rows)
    pins = StaticPinResolver(
        pins={
            "web/commoncrawl-cdx": DatasetPin(
                name="web/commoncrawl-cdx",
                revision="sha256:cdx",
                cid_map_cid="bafy...",
                license="commoncrawl-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CommonCrawlCdxSensor(annex_root=annex_root, pin_resolver=pins)
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    assert all(o.tier == "C" for o in observations)
    assert all(o.internal_only is True for o in observations)
    assert observations[0].payload["url"] == "https://example.com/path?q=secret"
    # Row 2's URL contains an email — should be redacted.
    assert "alice@example.com" not in observations[1].payload["url"]


def test_commoncrawl_cdx_sensor_pure_json_form(tmp_path):
    rows = [
        '{"url":"https://example.com/","mime":"text/html","status":"200"}',
        '{"url":"https://example.org/about","mime":"text/html","status":"200"}',
    ]
    annex_root = _make_cdx_snapshot(tmp_path, rows, compress=False)
    pins = StaticPinResolver(
        pins={
            "web/commoncrawl-cdx": DatasetPin(
                name="web/commoncrawl-cdx",
                revision="sha256:cdx-uncomp",
                cid_map_cid="bafy...",
                license="commoncrawl-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CommonCrawlCdxSensor(annex_root=annex_root, pin_resolver=pins)
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    assert observations[0].payload["url"] == "https://example.com/"


def test_commoncrawl_cdx_sensor_hot_sample_deterministic(tmp_path):
    rows = [
        f'com,example)/p{i} 2026052612345{i % 10} '
        f'{{"url":"https://example.com/p{i}","mime":"text/html",'
        f'"status":"200","digest":"sha1:X{i}","length":"1",'
        f'"offset":"{i}","filename":"warc/x.warc.gz"}}'
        for i in range(40)
    ]
    annex_root = _make_cdx_snapshot(tmp_path, rows)
    pins = StaticPinResolver(
        pins={
            "web/commoncrawl-cdx": DatasetPin(
                name="web/commoncrawl-cdx",
                revision="sha256:cdx-many",
                cid_map_cid="bafy...",
                license="commoncrawl-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CommonCrawlCdxSensor(annex_root=annex_root, pin_resolver=pins)
    pin = sensor.latest_pin()
    a = [o.payload["url"] for o in sensor.hot_sample(pin, 5)]
    b = [o.payload["url"] for o in sensor.hot_sample(pin, 5)]
    assert a == b
    assert len(a) == 5
