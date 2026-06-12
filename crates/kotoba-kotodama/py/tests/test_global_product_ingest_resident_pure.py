from __future__ import annotations


def test_frontier_id_prefers_normalized_url():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _frontier_id

    first = _frontier_id({"officialUrl": "HTTPS://Example.COM/products/a#frag"})
    second = _frontier_id({"productUrl": "https://example.com/products/a"})

    assert first == second
    assert len(first) == 24


def test_frontier_row_normalizes_urls_and_defaults():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _frontier_row

    row = _frontier_row(
        {
            "query": "standing desk",
            "productUrl": "https://brand.example/products/desk",
            "merchantUrl": "ftp://bad.example/item",
            "priority": 2000,
            "gtin": "49-01234567894",
        },
        "2026-05-09T23:30:00+00:00",
    )

    assert row["official_url"] == "https://brand.example/products/desk"
    assert row["merchant_url"] == ""
    assert row["priority"] == 1000
    assert row["gtin"] == "4901234567894"
    assert row["status"] == "pending"


def test_enrich_input_maps_frontier_to_enrich_one_shape():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _enrich_input

    payload = _enrich_input(
        {
            "frontier_id": "abc123",
            "query": "Acme Desk",
            "official_url": "https://acme.example/desk",
            "merchant_url": "https://shop.example/desk",
            "brand": "Acme",
            "model": "D-1",
            "gtin": "4901234567894",
            "category": "office.desk",
        }
    )

    assert payload["officialUrls"] == ["https://acme.example/desk"]
    assert payload["merchantUrls"] == ["https://shop.example/desk"]
    assert payload["jobId"] == "product-frontier-abc123"
    assert payload["useInference"] is True


def test_run_status_decision_maps_terminal_statuses():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _run_status_decision

    assert _run_status_decision("success") == "completed"
    assert _run_status_decision("failed") == "retry"
    assert _run_status_decision("running") == "active"


def test_sanitize_seed_item_normalizes_and_rejects_empty():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _sanitize_seed_item

    item = _sanitize_seed_item(
        {
            "brand": "Sony",
            "model": "WH-1000XM5",
            "officialUrl": "HTTPS://Electronics.Sony.COM/audio#fragment",
            "merchantUrl": "not-a-url",
            "gtin": "bad-123",
            "priority": 2000,
        }
    )

    assert item is not None
    assert item["query"] == "Sony WH-1000XM5"
    assert item["officialUrl"] == "https://electronics.sony.com/audio"
    assert item["merchantUrl"] == ""
    assert item["gtin"] == ""
    assert item["priority"] == 1000
    assert _sanitize_seed_item({}) is None


def test_fallback_seed_items_are_usable():
    from kotodama.langgraph_graphs.global_product_ingest_resident import _fallback_seed_items, _sanitize_seed_item

    seeds = _fallback_seed_items(3)
    assert len(seeds) == 3
    assert all(_sanitize_seed_item(seed) for seed in seeds)


def test_build_graph_compiles():
    from kotodama.langgraph_graphs.global_product_ingest_resident import build_graph

    assert build_graph() is not None
