import json
import unittest

from kotobase import KotobaseClient, KotobaseError


class ClientTest(unittest.TestCase):
    def test_cypher_uses_common_envelope(self):
        captured = {}

        def transport(url, headers, body, timeout):
            captured.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
            return 200, json.dumps({
                "ok": True,
                "language": "cypher",
                "data": {"rows": [["Ada"]]},
                "meta": {"requestId": "req-1", "elapsedMs": 2},
            }).encode()

        client = KotobaseClient("https://example.test/", token="secret", transport=transport)
        result = client.cypher("MATCH (n:users) RETURN n.name", parameters={"role": "admin"})

        self.assertEqual(captured["url"], "https://example.test/xrpc/ai.gftd.apps.kotobase.query.execute")
        self.assertEqual(captured["headers"]["authorization"], "Bearer secret")
        self.assertEqual(captured["body"]["language"], "cypher")
        self.assertEqual(result.data, {"rows": [["Ada"]]})

    def test_gremlin_bytecode(self):
        def transport(*_args):
            return 200, b'{"ok":true,"language":"gremlin","data":["Ada"],"meta":{"requestId":"r","elapsedMs":1}}'

        client = KotobaseClient(transport=transport)
        result = client.gremlin([["V"], ["hasLabel", "users"], ["values", "name"]])
        self.assertEqual(result.data, ["Ada"])
        with self.assertRaises(ValueError):
            client.gremlin([])

    def test_structured_error(self):
        def transport(*_args):
            return 503, b'{"error":{"code":"engine_unavailable","message":"disabled","retryable":true}}'

        client = KotobaseClient(transport=transport)
        with self.assertRaises(KotobaseError) as caught:
            client.sparql("SELECT * WHERE { ?s ?p ?o }")
        self.assertEqual(caught.exception.code, "engine_unavailable")
        self.assertTrue(caught.exception.retryable)

    def test_graphdb_repository(self):
        captured = {}

        def transport(_url, _headers, body, _timeout):
            captured.update(json.loads(body))
            return 200, b'{"ok":true,"language":"graphdb","data":{"results":{"bindings":[]}},"meta":{"requestId":"r","elapsedMs":1}}'

        client = KotobaseClient(transport=transport)
        client.graphdb("SELECT ?s WHERE { ?s ?p ?o }", database="default")
        self.assertEqual(captured["language"], "graphdb")
        self.assertEqual(captured["database"], "default")


if __name__ == "__main__":
    unittest.main()
