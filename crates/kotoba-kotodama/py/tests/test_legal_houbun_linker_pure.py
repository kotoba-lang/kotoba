from __future__ import annotations

import unittest


class TestLegalHoubunLinkerPure(unittest.TestCase):
    def test_json_loader_extracts_object(self):
        from kotodama.langgraph_graphs.legal_houbun_linker import _json_loads_maybe

        parsed = _json_loads_maybe('```json\n{"links":[]}\n```')
        self.assertEqual(parsed, {"links": []})

    def test_fallback_creates_entity_and_contract_links(self):
        from kotodama.langgraph_graphs.legal_houbun_linker import _fallback_hypotheses

        links = _fallback_hypotheses(
            [{"vertexId": "lei:1", "name": "日本法人"}],
            [{"vertexId": "contract:1", "title": "雇用契約"}],
            [{"vertexId": "article:1", "lawId": "companies-act", "title": "会社法330条"}],
        )
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["subjectKind"], "legal_entity")
        self.assertEqual(links[1]["subjectKind"], "contract")

    def test_infer_links_uses_fallback_when_llm_fails(self):
        import kotodama.langgraph_graphs.legal_houbun_linker as mod

        orig = mod.llm.call_tier
        mod.llm.call_tier = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
        try:
            out = mod.infer_links(
                {
                    "_entities": [{"vertexId": "lei:1", "name": "日本法人"}],
                    "_contracts": [],
                    "_articles": [
                        {
                            "vertexId": "article:1",
                            "lawId": "companies-act",
                            "title": "会社法330条",
                            "text": "",
                        }
                    ],
                }
            )
        finally:
            mod.llm.call_tier = orig
        self.assertTrue(out["ok"])
        self.assertEqual(out["hypotheses"][0]["articleVid"], "article:1")
        self.assertTrue(out["model"].startswith("fallback:"))

    def test_build_graph_returns_compiled(self):
        from kotodama.langgraph_graphs.legal_houbun_linker import build_graph

        self.assertIsNotNone(build_graph())


if __name__ == "__main__":
    unittest.main()
