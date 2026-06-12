from kotodama.primitives import chat


def test_domain_knowledge_terms_expand_pokopia_chigo_variants():
    terms = chat._domain_knowledge_terms("ココアポケモンでチーゴの実の入手方法は？")

    assert "ココアポケモン" in terms
    assert "ぽこあポケモン" in terms
    assert "pokemon-pokopia" in terms
    assert "チーゴのみ" in terms
    assert "チーゴの実" in terms
    assert "rawst berry" in terms


def test_infer_domain_knowledge_game_slug_handles_common_variants():
    assert chat._infer_domain_knowledge_game_slug("ぽこあポケモン チーゴのみ") == "pokemon-pokopia"
    assert chat._infer_domain_knowledge_game_slug("Pokemon Pokopia Rawst Berry") == "pokemon-pokopia"
    assert chat._infer_domain_knowledge_game_slug("unrelated") == ""


def test_tool_domain_knowledge_search_uses_mv_query(monkeypatch):
    captured = {}

    def fake_query(sql, params=()):
        captured["sql"] = sql
        captured["params"] = params
        return [
            (
                "chunk-1",
                "doc-1",
                "pokemon-pokopia",
                "ぽこあポケモン チーゴのみ / Rawst Berry 入手方法・活用方法",
                1,
                "チーゴのみは、チーゴの木にずつきして拾う。",
                "pokemon-pokopia,チーゴのみ,Rawst Berry",
                "high",
                "2026-05-09T00:00:00+09:00",
            )
        ]

    monkeypatch.setattr(chat, "_rw_query", fake_query)

    out = chat.tool_domain_knowledge_search({"query": "チーゴの実", "topK": 3})

    assert out["ok"] is True
    assert out["gameSlug"] == ""
    assert out["hits"][0]["gameSlug"] == "pokemon-pokopia"
    assert out["hits"][0]["chunkText"].startswith("チーゴのみ")
    assert "mv_domain_knowledge_search" in captured["sql"]
    assert captured["params"][0] == "ja"
    assert any("チーゴ" in str(p) for p in captured["params"])


def test_tool_web_search_uses_internal_vector_fallback(monkeypatch):
    monkeypatch.setattr(chat, "search_domain_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        chat,
        "_search_internal_vector_index",
        lambda query, top_k=6: [
            {
                "title": "bluesky_post: at://example/post/1",
                "url": "at://example/post/1",
                "snippet": "internal vector hit",
                "score": 0.77,
            }
        ],
    )

    out = chat.tool_web_search({"query": "internal query", "topK": 3})

    assert out["ok"] is True
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
    assert out["provider"] == "risingwave-vector-ann"
    assert out["method"] == "pod-embedding-rw-vector-index"
    assert out["hits"][0]["snippet"] == "internal vector hit"


def test_tool_web_search_does_not_call_external_provider_when_internal_empty(monkeypatch):
    monkeypatch.setattr(chat, "search_domain_knowledge", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat, "_search_internal_vector_index", lambda query, top_k=6: [])

    out = chat.tool_web_search({"query": "no internal hit"})

    assert out["ok"] is False
    assert out["provider"] == "risingwave-only"
    assert "external web search is not used" in out["error"]


def test_format_domain_knowledge_context_mentions_risingwave_snippets():
    text = chat._format_domain_knowledge_context(
        [
            {
                "title": "ぽこあポケモン チーゴのみ",
                "gameSlug": "pokemon-pokopia",
                "chunkIndex": 1,
                "chunkText": "チーゴのみはPPを1回復する。",
            }
        ]
    )

    assert "RisingWave domain-knowledge" in text
    assert "[KG1]" in text
    assert "チーゴのみはPPを1回復" in text


def test_direct_answer_count_question_does_not_use_random_entity(monkeypatch):
    def fake_query(sql, params=()):
        assert "vertex_game_item" in sql
        return [(300,)]

    monkeypatch.setattr(chat, "_rw_query", fake_query)

    answer = chat._domain_knowledge_direct_answer(
        "ぽこあポケモンにはポケモンはどれぐらいいる?",
        [
            {
                "title": "ぽこあポケモン ラプラス / Lapras 生息地",
                "chunkText": "ラプラスの生息地は Tropical Seaside。",
                "keywords": "pokemon-pokopia,Lapras",
            }
        ],
    )

    assert "300 種" in answer
    assert "308 フォーム" in answer
    assert "ラプラス" not in answer


def test_direct_answer_ignores_generic_pokopia_match_only(monkeypatch):
    monkeypatch.setattr(chat, "_rw_query", lambda sql, params=(): [(300,)])

    answer = chat._domain_knowledge_direct_answer(
        "ぽこあポケモンのことを教えて",
        [
            {
                "title": "ぽこあポケモン ラプラス / Lapras 生息地",
                "chunkText": "ラプラスの生息地は Tropical Seaside。",
                "keywords": "pokemon-pokopia,Lapras",
            }
        ],
    )

    assert answer == ""
