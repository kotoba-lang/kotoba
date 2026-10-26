import base64, json, unittest
from x402_sdk import (
    Policy, Refusal, X402Error, chain_id_for, parse_challenge, select_offer,
    build_authorization, encode_payment_header, fetch_with_payment,
)

POLICY = Policy(networks=["base-sepolia"],
                assets=["0x036CbD53842c5426634e7929541eC2318f3dCF7e"],
                max_amount="5000")

def offer(**over):
    o = {"scheme": "exact", "network": "base-sepolia",
         "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
         "payTo": "0xA00366234D29d4F882088048c0B2fa0dB7302D4E",
         "maxAmountRequired": "1000", "maxTimeoutSeconds": 60,
         "extra": {"name": "USDC", "version": "2"}}
    o.update(over)
    return o


class Select(unittest.TestCase):
    def test_no_policy_pays_nothing(self):
        r = select_offer({"x402Version": 1, "accepts": [offer()]}, None)
        self.assertEqual(r.refused, "no-policy")

    def test_cheapest_not_first(self):
        c = {"x402Version": 1, "accepts": [offer(maxAmountRequired="4000"),
                                           offer(maxAmountRequired="1000")]}
        self.assertEqual(select_offer(c, POLICY)["maxAmountRequired"], "1000")

    def test_every_failing_check_is_named(self):
        c = {"x402Version": 1, "accepts": [offer(network="base",
                                                 asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")]}
        r = select_offer(c, POLICY)
        self.assertIn("network-not-allowed", r.refused)
        self.assertIn("asset-not-allowed", r.refused)

    def test_over_budget(self):
        r = select_offer({"x402Version": 1, "accepts": [offer(maxAmountRequired="9999")]}, POLICY)
        self.assertEqual(r.refused, "over-budget")

    def test_unparseable_amount_is_not_silently_over_budget(self):
        r = select_offer({"x402Version": 1, "accepts": [offer(maxAmountRequired="one dollar")]}, POLICY)
        self.assertEqual(r.refused, "unparseable-amount")

    def test_asset_comparison_ignores_case(self):
        c = {"x402Version": 1, "accepts": [offer(asset="0x036cbd53842c5426634e7929541ec2318f3dcf7e")]}
        self.assertNotIsInstance(select_offer(c, POLICY), Refusal)


class Wire(unittest.TestCase):
    def test_unknown_network_raises(self):
        with self.assertRaises(X402Error):
            chain_id_for("optimism")
        self.assertEqual(chain_id_for("base-sepolia"), 84532)

    def test_non_402_is_not_a_challenge(self):
        self.assertIsNone(parse_challenge(500, b"boom"))

    def test_402_that_is_not_json_is_not_a_challenge(self):
        self.assertIsNone(parse_challenge(402, b"nope"))

    def test_header_round_trips(self):
        p = {"x402Version": 1, "scheme": "exact", "payload": {"signature": "0x01"}}
        self.assertEqual(json.loads(base64.b64decode(encode_payment_header(p))), p)

    def test_authorization_expires_by_the_offers_own_timeout(self):
        a = build_authorization(offer(maxTimeoutSeconds=30), "0xabc", now=1000)
        self.assertEqual(a.valid_before, "1030")
        self.assertEqual(a.valid_after, "0")
        self.assertRegex(a.nonce, r"^0x[0-9a-f]{64}$")


class Loop(unittest.TestCase):
    def test_non_402_returned_untouched(self):
        calls = []
        def fetch(url, method, headers, body):
            calls.append(headers)
            return 500, {}, b"boom"
        status, _, body = fetch_with_payment("https://x/y", policy=POLICY,
                                             sign=lambda d, m: "0x", address="0xa", fetch=fetch)
        self.assertEqual((status, body), (500, b"boom"))
        self.assertEqual(len(calls), 1, "a 500 is the server's answer; do not retry over it")

    def test_missing_domain_is_refused_not_guessed(self):
        def fetch(url, method, headers, body):
            return 402, {}, json.dumps({"x402Version": 1, "accepts": [offer(extra=None)]}).encode()
        with self.assertRaises(X402Error) as e:
            fetch_with_payment("https://x/y", policy=POLICY, sign=lambda d, m: "0x",
                               address="0xa", fetch=fetch)
        self.assertIn("EIP-712", str(e.exception))

    def test_signer_gets_the_offers_own_domain(self):
        seen = {}
        state = {"n": 0}
        def fetch(url, method, headers, body):
            state["n"] += 1
            if state["n"] == 1:
                return 402, {}, json.dumps({"x402Version": 1, "accepts": [offer()]}).encode()
            return 200, {"echo": headers["X-PAYMENT"]}, b"paid"
        def sign(domain, message):
            seen.update(domain=domain, message=message)
            return "0xsig"
        status, headers, _ = fetch_with_payment("https://x/y", policy=POLICY, sign=sign,
                                                address="0xdeadbeef", fetch=fetch)
        self.assertEqual(status, 200)
        self.assertEqual(seen["domain"]["name"], "USDC")
        self.assertEqual(seen["domain"]["chainId"], 84532)
        self.assertEqual(seen["domain"]["verifyingContract"], offer()["asset"])
        self.assertEqual(seen["message"]["from"], "0xdeadbeef")
        sent = json.loads(base64.b64decode(headers["echo"]))
        self.assertEqual(sent["payload"]["signature"], "0xsig")
        self.assertEqual(sent["scheme"], "exact")




class NotAChallenge(unittest.TestCase):
    def test_none_refuses_rather_than_raising(self):
        r = select_offer(None, POLICY)
        self.assertEqual(r.refused, "not-a-challenge")

    def test_default_fetch_sends_a_user_agent(self):
        from x402_sdk import USER_AGENT
        self.assertIn("x402-sdk-python", USER_AGENT)


if __name__ == "__main__":
    unittest.main()
