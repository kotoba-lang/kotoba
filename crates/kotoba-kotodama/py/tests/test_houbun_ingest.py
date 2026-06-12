from __future__ import annotations

from kotodama.ingest import houbun as H


def test_extract_law_payload_tag_children_shape() -> None:
    raw = {
        "law_info": {"law_id": "321CONSTITUTION", "law_type": "Constitution", "promulgation_date": "1946-11-03"},
        "revision_info": {"law_title": "日本国憲法", "amendment_enforcement_date": "1947-05-03"},
        "law_full_text": {
            "LawBody": {
                "tag": "LawBody",
                "children": [
                    {
                        "tag": "Chapter",
                        "children": [
                            {"tag": "ChapterTitle", "children": ["第一章 天皇"]},
                            {
                                "tag": "Article",
                                "attr": {"Num": "1"},
                                "children": [
                                    {"tag": "ArticleTitle", "children": ["第一条"]},
                                    {"tag": "Paragraph", "children": ["天皇は、日本国の象徴である。"]},
                                ],
                            },
                        ],
                    }
                ],
            }
        },
    }

    payload = H._extract_law_payload(raw, "321CONSTITUTION", max_articles=10)

    assert payload["law_id"] == "321CONSTITUTION"
    assert payload["title"] == "日本国憲法"
    assert payload["statute_type"] == "Constitution"
    assert payload["articles"][0]["article_no"] == "第一条"
    assert payload["articles"][0]["section"] == "第一章 天皇"
    assert "象徴" in payload["articles"][0]["text"]


def test_extract_law_payload_legacy_article_shape() -> None:
    raw = {
        "law_info": {"law_title": "民法", "law_type": "Act"},
        "law_full_text": {
            "LawBody": {
                "Article": [
                    {
                        "@": {"Num": "1"},
                        "ArticleTitle": "第一条",
                        "ArticleCaption": "（基本原則）",
                        "Paragraph": "私権は、公共の福祉に適合しなければならない。",
                    }
                ]
            }
        },
    }

    payload = H._extract_law_payload(raw, "129AC0000000089", max_articles=1)

    assert len(payload["articles"]) == 1
    assert payload["articles"][0]["article_no"] == "第一条"
    assert payload["articles"][0]["title"] == "（基本原則）"
    assert "公共の福祉" in payload["articles"][0]["text"]


def test_verify_visibility_math_requires_expected_article_count(monkeypatch) -> None:
    class Cursor:
        calls = 0

        def execute(self, *_args):
            return None

        def fetchone(self):
            self.calls += 1
            return [1] if self.calls == 1 else [2]

    class Context:
        def __enter__(self):
            return Cursor()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(H, "sync_cursor", lambda: Context())

    import asyncio

    out = asyncio.run(
        H.task_houbun_verify_visibility(
            lawId="x",
            articleCount=3,
            recordsWritten=0,
        )
    )

    assert out["verified"] is False
    assert out["visibleArticles"] == 2
