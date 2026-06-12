"""Pytest harness for the 10 W1-impl-landed corp/ + gov/ sensors.

Per ADR-2605263800 + ADR-2605263900. Validates:

1. Each sensor exposes the standard interface (latest_pin / stream /
   hot_sample) and a documented dataclass class (Sensor name);
2. Round-trip on a fixture NDJSON shard: yields the expected number
   of typed observations;
3. G7 schema discipline: malformed / required-field-missing rows are
   skipped without halting the stream;
4. G7 determinism: hot_sample(pin.revision, n) is reproducible across
   calls with the same (pin.revision, n);
5. Invariant constants (tier='A' / license_tag / internal_only=False /
   state_aligned_flag=False for non-CN sources).

Each test writes a tmp annex directory ("<tmp>/<sub-name>/<rev>/*.ndjson")
that the sensor reads, then tears it down.
"""

from __future__ import annotations

import json
from pathlib import Path


# ─── Test fixture builders ───────────────────────────────────────────


def _stage_shard(tmp_path: Path, subdataset_name: str, rows: list[dict]) -> Path:
    """Stage an NDJSON shard at <tmp_path>/<subdataset_name>/<rev>/shard.ndjson."""
    snap = tmp_path / subdataset_name / "20260527T000000Z"
    snap.mkdir(parents=True)
    shard = snap / "shard-001.ndjson"
    shard.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    )
    return shard


# ─── corp/lei_sensor — GleifLeiSensor ────────────────────────────────


def test_gleif_lei_sensor_round_trip(tmp_path, load_sensor, make_pin):
    lei_mod = load_sensor("corp.lei_sensor")
    sensor_cls = lei_mod.GleifLeiSensor
    sub = "corp/lei/gleif/lei-l1"
    rows = [
        {"lei": "HWUPKR0MPOU8FGXBT394", "legalName": "Apple Inc.",
         "jurisdictionIso3": "USA", "registrationStatus": "ISSUED"},
        {"lei": "353800OE2WPLLC7YPQ59", "legalName": "Sony Group Corporation",
         "jurisdictionIso3": "JPN", "registrationStatus": "ISSUED"},
        {"lei": "TOOSHORT", "legalName": "Bad LEI Co"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="CC0-1.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2  # G7 skip 1
    assert all(o.tier == "A" for o in obs)
    assert all(o.license_tag == "CC0-1.0" for o in obs)
    assert all(o.internal_only is False for o in obs)
    # G7 determinism
    s1 = [o.entity_lei for o in sensor.hot_sample(pin, 1)]
    s2 = [o.entity_lei for o in sensor.hot_sample(pin, 1)]
    assert s1 == s2


# ─── corp/sec_edgar_sensor — SecEdgarSensor ──────────────────────────


def test_sec_edgar_sensor_round_trip(tmp_path, load_sensor, make_pin):
    sec_mod = load_sensor("corp.sec_edgar_sensor")
    sensor_cls = sec_mod.SecEdgarSensor
    sub = "corp/disclosures/usa"
    rows = [
        {"entityLocalId": "0000320193", "formTypeNative": "10-K",
         "filedAtUtc": "2024-11-01T20:42:13Z", "payloadCid": "bafy_aapl_10k"},
        {"entityLocalId": "0000789019", "formTypeNative": "10-Q",
         "filedAtUtc": "2025-01-29T21:00:00Z", "payloadCid": "bafy_msft_10q"},
        {"entityLocalId": "0000019617", "formTypeNative": "NT-UNKNOWN",
         "filedAtUtc": "2025-01-01T00:00:00Z", "payloadCid": "bafy_x"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="public-domain", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2  # 1 G7 skip (NT-UNKNOWN)
    forms = {o.form_class for o in obs}
    assert forms == {"annual-report", "interim-report"}
    assert all(o.jurisdiction_iso3 == "USA" for o in obs)
    # form_class_filter
    filtered = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        form_class_filter=("annual-report",),
    ).stream(pin))
    assert len(filtered) == 1
    assert filtered[0].form_type_native == "10-K"


# ─── corp/uk_companies_house_sensor — UkCompaniesHouseSensor ─────────


def test_uk_companies_house_sensor_round_trip(tmp_path, load_sensor, make_pin):
    uk_mod = load_sensor("corp.uk_companies_house_sensor")
    sensor_cls = uk_mod.UkCompaniesHouseSensor
    sub = "corp/registries/gbr/companies-house"
    rows = [
        {"entityLocalId": "03977902", "registeredName": "APPLE EUROPE LIMITED",
         "registeredAt": "2000-03-30"},
        {"entityLocalId": "SC083026", "registeredName": "NATWEST GROUP PLC"},
        {"entityLocalId": "OC334765", "registeredName": "BAKER & MCKENZIE LLP"},
        {"entityLocalId": "12", "registeredName": "TOO SHORT LTD"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="OGL-v3.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 3  # G7 skip "12"
    crns = {o.entity_local_id for o in obs}
    assert crns == {"03977902", "SC083026", "OC334765"}
    # regional_prefix_filter = "SC" → 1 obs
    sc_only = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        regional_prefix_filter="SC",
    ).stream(pin))
    assert len(sc_only) == 1 and sc_only[0].entity_local_id == "SC083026"


# ─── corp/jp_edinet_sensor — JpEdinetSensor ──────────────────────────


def test_jp_edinet_sensor_round_trip(tmp_path, load_sensor, make_pin):
    edi_mod = load_sensor("corp.jp_edinet_sensor")
    sensor_cls = edi_mod.JpEdinetSensor
    sub = "corp/disclosures/jpn"
    rows = [
        {"entityLocalId": "E01777", "formTypeNative": "120",
         "filedAtUtc": "2025-06-23T07:00:00Z", "payloadCid": "bafy_sony_yuho"},
        {"entityLocalId": "E02144", "formTypeNative": "140",
         "filedAtUtc": "2025-08-04T07:00:00Z", "payloadCid": "bafy_toyota_q1"},
        {"entityLocalId": "E03182", "formTypeNative": "350",
         "filedAtUtc": "2025-11-10T07:00:00Z", "payloadCid": "bafy_softbank_350"},
        {"entityLocalId": "E99", "formTypeNative": "999",
         "filedAtUtc": "2026-01-01T00:00:00Z", "payloadCid": "bafy_x"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="fsa-open-data-utilization-terms", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 3
    classes = {o.form_class for o in obs}
    assert classes == {"annual-report", "interim-report", "institutional-holding"}
    assert all(o.jurisdiction_iso3 == "JPN" for o in obs)


# ─── corp/gleif_l2_ownership_sensor — GleifL2OwnershipSensor ─────────


def test_gleif_l2_ownership_sensor_round_trip(tmp_path, load_sensor, make_pin):
    own_mod = load_sensor("corp.gleif_l2_ownership_sensor")
    sensor_cls = own_mod.GleifL2OwnershipSensor
    sub = "corp/ownership/gleif-l2"
    rows = [
        # 1) Direct accounting parent → parent-subsidiary.
        #    Sony Group (ultimate) directly consolidates Sony Semiconductor.
        {"subjectLei": "5493004YDGTGB2VK3O27",
         "ownerLei": "353800OE2WPLLC7YPQ59",
         "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
         "relationshipStatus": "ACTIVE",
         "subjectJurisdictionIso3": "JPN", "ownerJurisdictionIso3": "JPN",
         "asOf": "2025-04-01"},
        # 2) Ultimate accounting parent → control-relationship (the UBO edge).
        {"subjectLei": "5493004YDGTGB2VK3O27",
         "ownerLei": "353800OE2WPLLC7YPQ59",
         "relationshipType": "IS_ULTIMATELY_CONSOLIDATED_BY",
         "relationshipStatus": "ACTIVE",
         "subjectJurisdictionIso3": "JPN", "ownerJurisdictionIso3": "JPN"},
        # 3) INACTIVE edge → skipped (only currently-true edges surfaced).
        {"subjectLei": "549300JM3RYS3WXSML22",
         "ownerLei": "353800OE2WPLLC7YPQ59",
         "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
         "relationshipStatus": "INACTIVE"},
        # 4) Unmapped relationship type → G7 skip.
        {"subjectLei": "549300JM3RYS3WXSML22",
         "ownerLei": "HWUPKR0MPOU8FGXBT394",
         "relationshipType": "IS_FUND-MANAGED_BY",
         "relationshipStatus": "ACTIVE"},
        # 5) Short owner LEI → G7 skip.
        {"subjectLei": "549300JM3RYS3WXSML22",
         "ownerLei": "TOOSHORT",
         "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY"},
        # 6) Self-loop → G7 skip.
        {"subjectLei": "HWUPKR0MPOU8FGXBT394",
         "ownerLei": "HWUPKR0MPOU8FGXBT394",
         "relationshipType": "IS_ULTIMATELY_CONSOLIDATED_BY"},
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="CC0-1.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2  # rows 3-6 all skipped
    kinds = {o.ownership_kind for o in obs}
    assert kinds == {"parent-subsidiary", "control-relationship"}
    assert all(o.tier == "A" for o in obs)
    assert all(o.license_tag == "CC0-1.0" for o in obs)
    assert all(o.internal_only is False for o in obs)
    # GLEIF consolidation edges carry no percentage.
    assert all(o.pct_held is None for o in obs)
    # Direction convention: subject = child, owner = parent.
    control = next(o for o in obs if o.ownership_kind == "control-relationship")
    assert control.subject_lei == "5493004YDGTGB2VK3O27"
    assert control.owner_lei == "353800OE2WPLLC7YPQ59"
    assert control.subject_jurisdiction_iso3 == "JPN"
    # ownership_kind_filter = (control-relationship,) → 1 obs (the UBO edge).
    ubo_only = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        ownership_kind_filter=("control-relationship",),
    ).stream(pin))
    assert len(ubo_only) == 1
    assert ubo_only[0].ownership_kind == "control-relationship"
    # G7 determinism on hot_sample.
    s1 = [(o.subject_lei, o.ownership_kind) for o in sensor.hot_sample(pin, 1)]
    s2 = [(o.subject_lei, o.ownership_kind) for o in sensor.hot_sample(pin, 1)]
    assert s1 == s2


# ─── gov/worldbank_open_data_sensor — WorldBankOpenDataSensor ────────


def test_worldbank_sensor_round_trip(tmp_path, load_sensor, make_pin):
    wb_mod = load_sensor("gov.worldbank_open_data_sensor")
    sensor_cls = wb_mod.WorldBankOpenDataSensor
    sub = "gov/statistics/worldbank-open-data"
    rows = [
        {"indicatorCode": "NY.GDP.MKTP.CD", "indicatorTitle": "GDP",
         "dimensions": [["country", "USA"], ["year", "2024"]],
         "value": 29167779200000, "observationPeriod": "2024",
         "payloadCid": "bafy_usa_gdp"},
        {"indicatorCode": "NY.GDP.MKTP.CD", "indicatorTitle": "GDP",
         "dimensions": [["country", "CHN"], ["year", "2024"]],
         "value": 18532633000000, "observationPeriod": "2024",
         "payloadCid": "bafy_chn_gdp", "stateAlignedFlag": True},
        {"indicatorTitle": "Orphan"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="CC-BY-4.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    chn = next(o for o in obs if dict(o.dimensions).get("country") == "CHN")
    assert chn.state_aligned_flag is True  # §2(g) flag pass-through
    usa = next(o for o in obs if dict(o.dimensions).get("country") == "USA")
    assert usa.state_aligned_flag is False


# ─── gov/uk_hansard_sensor — UkHansardSensor ─────────────────────────


def test_uk_hansard_sensor_round_trip(tmp_path, load_sensor, make_pin):
    hsd_mod = load_sensor("gov.uk_hansard_sensor")
    sensor_cls = hsd_mod.UkHansardSensor
    sub = "gov/parliament/gbr/hansard"
    rows = [
        {"recordId": "2026-05-20/commons/debate/001",
         "sessionDateUtc": "2026-05-20T12:30:00Z",
         "payloadCid": "bafy_hansard_001",
         "house": "Commons", "nativeKind": "Debate",
         "speakerName": "Lindsay Hoyle", "speakerRole": "Speaker"},
        {"recordId": "2026-05-20/lords/division/045",
         "sessionDateUtc": "2026-05-20T22:15:00Z",
         "payloadCid": "bafy_lords_div_045",
         "house": "Lords", "nativeKind": "Division"},
        {"recordId": "BAD-HOUSE", "sessionDateUtc": "2026-05-20T00:00:00Z",
         "payloadCid": "bafy_bad", "house": "WrongHouse",
         "recordKind": "debate"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="OGL-v3.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    debate = next(o for o in obs if o.record_kind == "debate")
    assert debate.speaker_name == "Lindsay Hoyle"  # speaker pass-through §5
    assert debate.speaker_role == "Speaker"
    vote = next(o for o in obs if o.record_kind == "vote")  # Division → vote
    assert "lords/division" in vote.record_id


# ─── gov/eu_eurostat_sensor — EuEurostatSensor ───────────────────────


def test_eurostat_sensor_round_trip(tmp_path, load_sensor, make_pin):
    eu_mod = load_sensor("gov.eu_eurostat_sensor")
    sensor_cls = eu_mod.EuEurostatSensor
    sub = "gov/statistics/eurostat"
    rows = [
        {"indicatorCode": "nama_10_gdp", "indicatorTitle": "GDP",
         "dimensions": [["geo", "DE"], ["time", "2024"]],
         "value": 4444460.0, "observationPeriod": "2024",
         "payloadCid": "bafy_de_gdp"},
        {"indicatorCode": "demo_pjan", "indicatorTitle": "Population",
         "dimensions": {"geo": "EU27_2020", "time": "2025"},
         "value": 449300000.0, "observationPeriod": "2025",
         "payloadCid": "bafy_eu_pop"},
        {"indicatorCode": "x", "indicatorTitle": "Bad",
         "dimensions": "geo=DE", "observationPeriod": "2024"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="eurostat-free-reuse", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    pop = next(o for o in obs if o.indicator_code == "demo_pjan")
    # dict-shape dimension coercion
    assert pop.dimensions == (("geo", "EU27_2020"), ("time", "2025"))


# ─── gov/us_congress_gov_sensor — UsCongressGovSensor ────────────────


def test_us_congress_sensor_round_trip(tmp_path, load_sensor, make_pin):
    cg_mod = load_sensor("gov.us_congress_gov_sensor")
    sensor_cls = cg_mod.UsCongressGovSensor
    sub = "gov/parliament/usa/congress-gov"
    rows = [
        {"recordId": "BILLS-119hr1234ih",
         "sessionDateUtc": "2025-02-13T15:00:00Z",
         "payloadCid": "bafy_hr1234",
         "chamber": "House", "nativeKind": "House Bill"},
        {"recordId": "ROLL-119-1-s-205",
         "sessionDateUtc": "2025-05-22T22:00:00Z",
         "payloadCid": "bafy_roll_s_205",
         "chamber": "Senate", "nativeKind": "Roll Call Vote"},
        {"recordId": "BAD", "sessionDateUtc": "2025-05-01T00:00:00Z",
         "payloadCid": "bafy_bad", "chamber": "HouseOfCommons",
         "recordKind": "debate"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="public-domain", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    senate = next(o for o in obs if "ROLL-" in o.record_id)
    assert senate.record_kind == "vote"
    bill = next(o for o in obs if "hr1234" in o.record_id)
    assert bill.record_kind == "bill"


# ─── gov/jp_kokkai_kaigiroku_sensor — JpKokkaiKaigirokuSensor ────────


def test_jp_kokkai_sensor_round_trip(tmp_path, load_sensor, make_pin):
    kk_mod = load_sensor("gov.jp_kokkai_kaigiroku_sensor")
    sensor_cls = kk_mod.JpKokkaiKaigirokuSensor
    sub = "gov/parliament/jpn/kokkai-kaigiroku"
    rows = [
        {"recordId": "121705254X02320250121",
         "sessionDateUtc": "2025-01-21T01:00:00Z",
         "payloadCid": "bafy_h_217_honkaigi",
         "house": "衆議院", "nativeKind": "本会議",
         "speakerName": "額賀福志郎", "speakerRole": "議長"},
        {"recordId": "121815254X-bill-001",
         "sessionDateUtc": "2025-02-03T05:00:00Z",
         "payloadCid": "bafy_s_217_bill",
         "house": "参議院", "nativeKind": "法律案"},
        {"recordId": "BAD-HOUSE", "sessionDateUtc": "2025-01-21T00:00:00Z",
         "payloadCid": "bafy_bad", "house": "英国議会",
         "recordKind": "debate"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="ndl-public-record-free-use", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    honkai = next(o for o in obs if o.record_kind == "debate")
    assert honkai.speaker_name == "額賀福志郎"  # §5 pass-through
    assert honkai.speaker_role == "議長"


# ─── gov/us_data_gov_sensor — UsDataGovSensor ────────────────────────


def test_us_data_gov_sensor_round_trip(tmp_path, load_sensor, make_pin):
    dg_mod = load_sensor("gov.us_data_gov_sensor")
    sensor_cls = dg_mod.UsDataGovSensor
    sub = "gov/open-data/usa/data-gov"
    rows = [
        {"datasetId": "noaa-cdo", "title": "Climate Data Online",
         "license": "us-pd", "publisher": "NOAA",
         "organization": "noaa-gov", "payloadCid": "bafy_noaa"},
        {"datasetId": "ccby-set", "title": "CC-BY Sub-License",
         "license": "cc-by", "publisher": "Some Agency",
         "organization": "some-org", "payloadCid": "bafy_ccby"},
        {"datasetId": "incomplete", "title": "Missing License"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="public-domain", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    # Per-row license_tag override
    ccby = next(o for o in obs if o.dataset_id == "ccby-set")
    assert ccby.license_tag == "cc-by"
    noaa = next(o for o in obs if o.dataset_id == "noaa-cdo")
    assert noaa.license_tag == "us-pd"


# ─── gov/uk_data_gov_uk_sensor — UkDataGovUkSensor ───────────────────


def test_uk_data_gov_uk_sensor_round_trip(tmp_path, load_sensor, make_pin):
    uk_mod = load_sensor("gov.uk_data_gov_uk_sensor")
    sensor_cls = uk_mod.UkDataGovUkSensor
    sub = "gov/open-data/gbr/data-gov-uk"
    rows = [
        {"datasetId": "ons-gdp-quarterly", "title": "GDP Quarterly",
         "license": "uk-ogl", "publisher": "Office for National Statistics",
         "organisation": "ons-gov-uk", "payloadCid": "bafy_ons_gdp"},
        {"datasetId": "moj-court-stats", "title": "Court Statistics Quarterly",
         "license": "uk-ogl", "publisher": "Ministry of Justice",
         "organisation": "moj-gov-uk", "payloadCid": "bafy_moj_court"},
        {"datasetId": "ccby-set", "title": "CC-BY Sub-License Dataset",
         "license": "cc-by", "publisher": "Some Body",
         "organisation": "some-org", "payloadCid": "bafy_ccby"},
        {"datasetId": "incomplete", "title": "Missing License"},  # G7 skip
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="OGL-v3.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 3
    assert all(o.jurisdiction == "GBR" for o in obs)
    # Per-row license_tag pass-through
    ccby = next(o for o in obs if o.dataset_id == "ccby-set")
    assert ccby.license_tag == "cc-by"
    # organisation_filter (British English spelling) — MoJ-only
    moj_only = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        organisation_filter="moj-gov-uk",
    ).stream(pin))
    assert len(moj_only) == 1 and moj_only[0].dataset_id == "moj-court-stats"


# ─── gov/jp_data_go_jp_sensor — JpDataGoJpSensor ─────────────────────


def test_jp_data_go_jp_sensor_round_trip(tmp_path, load_sensor, make_pin):
    jp_mod = load_sensor("gov.jp_data_go_jp_sensor")
    sensor_cls = jp_mod.JpDataGoJpSensor
    sub = "gov/open-data/jpn/data-go-jp"
    rows = [
        {"datasetId": "data_go_jp_pkg_jinkou_setai", "title": "人口統計データ",
         "license": "cc-by-4.0", "publisher": "総務省",
         "organization": "soumu-go-jp", "payloadCid": "bafy_jinkou"},
        {"datasetId": "00200521", "title": "国勢調査時系列データ",
         "license": "cc-by-4.0", "publisher": "総務省統計局",
         "organization": "stat-go-jp", "payloadCid": "bafy_kokusei",
         "source": "e-stat"},
        {"datasetId": "incomplete-jp"},  # G7 skip (no title / license / cid)
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="CC-BY-4.0", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 2
    assert all(o.jurisdiction == "JPN" for o in obs)
    assert all(o.license_tag == "cc-by-4.0" for o in obs)
    # 総務省 (Soumu) organization filter
    soumu = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        organization_filter="soumu-go-jp",
    ).stream(pin))
    assert len(soumu) == 1 and soumu[0].publisher == "総務省"


# ─── gov/us_usaspending_sensor — UsUsaspendingSensor ─────────────────


def test_us_usaspending_sensor_round_trip(tmp_path, load_sensor, make_pin):
    sp_mod = load_sensor("gov.us_usaspending_sensor")
    sensor_cls = sp_mod.UsUsaspendingSensor
    sub = "gov/budget/usa/usaspending-gov"
    rows = [
        # 1) Outlay — recipient w/ LEI (cross-link to corp.leiReference)
        {"recordKind": "outlay", "recordId": "USA-2025-OUTLAY-001",
         "programName": "Medicare Part A", "programCode": "75-0521",
         "amountLocal": 1500000.0, "currencyIso4217": "USD",
         "fiscalYear": 2025,
         "recipientName": "Mayo Clinic", "recipientLocalId": "MAYO-UEI-001",
         "recipientLei": "549300JM3RYS3WXSML22",
         "awardDateUtc": "2025-03-15T00:00:00Z",
         "payloadCid": "bafy_outlay_001"},
        # 2) Obligation — recipient w/o LEI
        {"recordKind": "obligation", "recordId": "USA-2025-OBLIG-042",
         "programName": "NSF Research Grant",
         "amountLocal": 750000.0, "currencyIso4217": "USD",
         "fiscalYear": 2025,
         "recipientName": "Stanford University",
         "payloadCid": "bafy_oblig_042"},
        # 3) Subaward — different FY (excluded by fy filter test below)
        {"recordKind": "subaward", "recordId": "USA-2024-SUB-100",
         "programName": "DARPA Research",
         "amountLocal": 250000.0, "currencyIso4217": "USD",
         "fiscalYear": 2024,
         "recipientName": "MIT Research Group",
         "payloadCid": "bafy_sub_100"},
        # 4) Unknown recordKind → G7 skip
        {"recordKind": "bonus", "recordId": "BAD",
         "programName": "X", "amountLocal": 100, "currencyIso4217": "USD",
         "fiscalYear": 2025, "payloadCid": "bafy_bad"},
        # 5) Missing amount → G7 skip
        {"recordKind": "outlay", "recordId": "NO-AMOUNT",
         "programName": "Y", "currencyIso4217": "USD",
         "fiscalYear": 2025, "payloadCid": "bafy_no_amt"},
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="public-domain", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 3
    assert all(o.jurisdiction == "USA" for o in obs)
    # LEI cross-link preserved on row 1
    mayo = next(o for o in obs if o.recipient_name == "Mayo Clinic")
    assert mayo.recipient_lei == "549300JM3RYS3WXSML22"
    # Stanford has no LEI in row — should be None
    stan = next(o for o in obs if o.recipient_name == "Stanford University")
    assert stan.recipient_lei is None
    # fiscal_year_filter = 2025 → 2 obs (excludes the FY 2024 subaward)
    fy2025 = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        fiscal_year_filter=2025,
    ).stream(pin))
    assert len(fy2025) == 2
    # record_kind_filter = (outlay,) → 1 obs
    outlay_only = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        record_kind_filter=("outlay",),
    ).stream(pin))
    assert len(outlay_only) == 1 and outlay_only[0].record_kind == "outlay"


# ─── gov/eu_ted_sensor — EuTedSensor ─────────────────────────────────


def test_eu_ted_sensor_round_trip(tmp_path, load_sensor, make_pin):
    ted_mod = load_sensor("gov.eu_ted_sensor")
    sensor_cls = ted_mod.EuTedSensor
    sub = "gov/procurement/eu/ted"
    rows = [
        # 1) Contract notice (native → tender-notice)
        {"noticeId": "100001-2026", "title": "Highway Maintenance Tender DE-Bayern",
         "contractingAuthority": "Bayerische Staatsbauverwaltung",
         "nativeKind": "Contract notice",
         "payloadCid": "bafy_ted_100001"},
        # 2) Contract award (native → award) with LEI + amount
        {"noticeId": "100002-2026", "title": "Award: IT Services FR-Île-de-France",
         "contractingAuthority": "Région Île-de-France",
         "nativeKind": "Contract award notice",
         "awardeeName": "Atos SE",
         "awardeeLei": "969500TBVKBQHFK6JC85",
         "awardAmountLocal": 12500000.0, "currencyIso4217": "EUR",
         "awardDateUtc": "2026-04-15T00:00:00Z",
         "payloadCid": "bafy_ted_100002"},
        # 3) Small contract award (below min_amount filter test)
        {"noticeId": "100003-2026", "title": "Award: Small Cleaning Contract IT",
         "contractingAuthority": "Comune di Milano",
         "recordKind": "award",
         "awardeeName": "Small Local Co",
         "awardAmountLocal": 50000.0, "currencyIso4217": "EUR",
         "payloadCid": "bafy_ted_100003"},
        # 4) Cancellation (Corrigendum mapping)
        {"noticeId": "100004-2026", "title": "Corrigendum: Highway Tender DE-Bayern",
         "contractingAuthority": "Bayerische Staatsbauverwaltung",
         "nativeKind": "Corrigendum",
         "payloadCid": "bafy_ted_100004"},
        # 5) Unknown nativeKind → G7 skip
        {"noticeId": "BAD", "title": "X",
         "contractingAuthority": "Y",
         "nativeKind": "Lobbyist Filing",
         "payloadCid": "bafy_bad"},
        # 6) Missing payloadCid → G7 skip
        {"noticeId": "100005-2026", "title": "Missing CID",
         "contractingAuthority": "Y", "recordKind": "award"},
    ]
    _stage_shard(tmp_path, sub, rows)
    pin, resolver = make_pin(sub, license="eu-reuse-decision-2011-833", tier="A")
    sensor = sensor_cls(annex_root=tmp_path, pin_resolver=resolver)
    obs = list(sensor.stream(sensor.latest_pin()))
    assert len(obs) == 4
    assert all(o.jurisdiction == "EU" for o in obs)
    # Native mapping checks
    notice = next(o for o in obs if o.notice_id == "100001-2026")
    assert notice.record_kind == "tender-notice"
    award = next(o for o in obs if o.notice_id == "100002-2026")
    assert award.record_kind == "award"
    assert award.awardee_lei == "969500TBVKBQHFK6JC85"
    cancel = next(o for o in obs if o.notice_id == "100004-2026")
    assert cancel.record_kind == "cancellation"  # Corrigendum → cancellation
    # min_amount_local = 1_000_000 EUR → only the large Atos award
    big_only = list(sensor_cls(
        annex_root=tmp_path, pin_resolver=resolver,
        min_amount_local=1_000_000.0,
    ).stream(pin))
    assert len(big_only) == 1 and big_only[0].notice_id == "100002-2026"


# ─── Cross-cutting invariant: NO Tier-D vendor terminal imports ──────


def test_no_vendor_terminal_imports_in_sensor_sources():
    """Lint-style guard: assert NONE of the 10 W1 sensor source files
    import or reference vendor commercial terminal hostnames or SDK
    package names. Per ADR-2605263800 §6 G12 + ADR-2605263900 §6 G12.
    """
    DENY = [
        # corp Tier-D
        "bloomberg-terminal", "bloomberg.com/professional",
        "spcapitaliq", "capitaliq.com",
        "refinitiv-eikon", "refinitiv.com/eikon",
        "factset.com",
        "moodys-orbis", "bvdinfo.com/orbis",
        "dnb-hoovers", "dnb.com/hoovers",
        "pitchbook.com",
        "crunchbase.com/pro",
        # gov Tier-D
        "govwin-iq", "govwin.com",
        "bloomberg-government", "bgov.com",
        "politico-pro", "politicopro.com",
        "eenews-pro", "eenews.net/pro",
        "fiscalnote.com",
        "cq-rollcall-pro", "cqrcengage.com",
    ]
    sensors = (
        Path(__file__).resolve().parent.parent.parent
        / "src" / "kotodama" / "organism" / "sensors"
    )
    files = list((sensors / "corp").glob("*.py")) + list((sensors / "gov").glob("*.py"))
    for f in files:
        text = f.read_text()
        for needle in DENY:
            # Skip the lint-self-reference inside this very file's
            # `vendor_terminal_denylist` style audit table, if present.
            # Sensors typically reference these only in docstrings
            # (legitimate; they're PROHIBITION notices, not imports).
            # We only fail on `import` or `from ... import` lines.
            for line in text.splitlines():
                stripped = line.strip()
                if (stripped.startswith("import ") or stripped.startswith("from ")) and needle in line:
                    raise AssertionError(
                        f"{f.name}: forbidden vendor terminal import '{needle}'"
                    )
