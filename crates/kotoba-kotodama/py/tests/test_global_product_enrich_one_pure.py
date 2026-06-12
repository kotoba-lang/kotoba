from __future__ import annotations


def test_extract_facts_prefers_jsonld_gtin_and_brand():
    from kotodama.langgraph_graphs.global_product_enrich_one import _extract_facts

    html = """
    <html><head>
      <script type="application/ld+json">
      {"@type":"Product","name":"Acme Standing Desk Pro","brand":{"name":"Acme"},
       "model":"SD-PRO","mpn":"SD-PRO-120","gtin13":"4901234567894",
       "image":"https://example.com/product.jpg"}
      </script>
    </head><body></body></html>
    """
    facts = _extract_facts(
        [{"sourceKind": "official", "url": "https://example.com/products/sd-pro", "html": html}],
        {"query": "", "brand": "", "model": "", "gtin": "", "category": "office.desk"},
    )

    assert facts["name"] == "Acme Standing Desk Pro"
    assert facts["brand"] == "Acme"
    assert facts["model"] == "SD-PRO"
    assert facts["gtin"] == "4901234567894"
    assert facts["productKey"] == "gtin_4901234567894"
    assert facts["officialUrl"] == "https://example.com/products/sd-pro"


def test_seed_requires_scope():
    from kotodama.langgraph_graphs.global_product_enrich_one import seed

    result = seed({})
    assert result["ok"] is False
    assert "required" in result["error"]


def test_quality_gate_accepts_official_brand_model_without_gtin():
    from kotodama.langgraph_graphs.global_product_enrich_one import quality_gate

    result = quality_gate(
        {
            "productFacts": {
                "brand": "Acme",
                "model": "SD-PRO",
                "officialUrl": "https://example.com/products/sd-pro",
            },
            "canonicalProduct": {"confidence": 0.72},
        }
    )
    assert result["ok"] is True


def test_build_graph_compiles():
    from kotodama.langgraph_graphs.global_product_enrich_one import build_graph

    assert build_graph() is not None
