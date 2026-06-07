import csv
import io

from kotodama import pd_color_process_mining as P


def test_pd_color_process_mining_summary_collapses_localization_variants() -> None:
    rows = [
        {"case_id": "run:1", "activity": "01 Candidate persisted", "timestamp": "2026-04-29T00:00:00Z"},
        {"case_id": "run:1", "activity": "02 Rights approved", "timestamp": "2026-04-29T00:00:01Z"},
        {"case_id": "run:1", "activity": "03 Derivatives ready", "timestamp": "2026-04-29T00:00:02Z"},
        {"case_id": "run:1", "activity": "04 Localization ready: en", "timestamp": "2026-04-29T00:00:03Z"},
        {"case_id": "run:1", "activity": "04 Localization ready: ja", "timestamp": "2026-04-29T00:00:03Z"},
        {"case_id": "run:1", "activity": "05 Published", "timestamp": "2026-04-29T00:00:04Z"},
    ]

    summary = P._summary(rows)

    assert summary["eventCount"] == 6
    assert summary["caseCount"] == 1
    assert summary["publishedCaseCount"] == 1
    assert summary["variants"] == [
        {
            "variant": "01 Candidate persisted > 02 Rights approved > 03 Derivatives ready > 04 Localization ready > 05 Published",
            "count": 1,
        }
    ]
    assert summary["latestPublishedCase"]["case_id"] == "run:1"


def test_pd_color_process_mining_csv_columns_are_stable(monkeypatch) -> None:
    rows = [
        {
            "case_id": "run:1",
            "activity": "01 Candidate persisted",
            "timestamp": "2026-04-29T00:00:00Z",
            "resource": "sys.bpmn.pd-color",
            "lifecycle": "complete",
            "work_id": "work:1",
            "artifact_id": "run:1",
            "detail": "rights_review",
        }
    ]
    out = io.StringIO()
    monkeypatch.setattr(P, "sys", type("Sys", (), {"stdout": out}))

    P._write_csv(rows, None)

    parsed = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert parsed == rows
    assert out.getvalue().splitlines()[0] == ",".join(P.EVENT_COLUMNS)
