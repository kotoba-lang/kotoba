// Checks resources/aiueos/session/assets/torihiki.js against vectors the torihiki engine produced.
// Run: node scripts/session-torihiki-test.js   (Node with WebCrypto Ed25519; no network)
"use strict";
const path = require("path"), fs = require("fs"), realAssert = require("assert");
let checks = 0;
const assert = Object.assign((...a) => { checks++; return realAssert(...a); }, Object.fromEntries(["ok", "strictEqual", "notStrictEqual", "deepStrictEqual"].map((k) => [k, (...a) => { checks++; return realAssert[k](...a); }])));
const root = path.resolve(__dirname, "..");
const api = require(path.join(root, "resources/aiueos/session/assets/torihiki.js"));
const vec = JSON.parse(fs.readFileSync(path.join(root, "test/session/torihiki-vectors.json"), "utf8"));

(async () => {
  for (const d of vec.derive) { assert.strictEqual(await api.deriveAccount(d.pubkey), d.account, "derive " + d.pubkey); }
  for (const p of vec.payloads) { assert.strictEqual(api.signingPayload(p.chain, p.account, p.nonce, p.tx), p.payload, JSON.stringify(p.tx)); }
  // negative controls: a wrong field position or a missing colon must NOT match
  const p0 = vec.payloads[0];
  assert.notStrictEqual(api.signingPayload(p0.chain, p0.account, p0.nonce, { ...p0.tx, side: "sell" }), p0.payload);
  assert.notStrictEqual(api.signingPayload(p0.chain, p0.account, p0.nonce + 1, p0.tx), p0.payload);
  assert.notStrictEqual(await api.deriveAccount(vec.derive[0].pubkey + "A"), vec.derive[0].account);
  // signature: sign with a fresh key, verify against the payload with the exported public key
  const kp = await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]);
  const raw = Buffer.from(await crypto.subtle.exportKey("raw", kp.publicKey)).toString("base64");
  const env = await api.signEnvelope(kp.privateKey, raw, p0.chain, p0.account, p0.nonce, p0.tx);
  assert.deepStrictEqual(Object.keys(env).sort(), ["account", "nonce", "pubkey", "sig", "tx"]);
  const ok = await crypto.subtle.verify({ name: "Ed25519" }, kp.publicKey, Buffer.from(env.sig, "base64"), Buffer.from(p0.payload));
  assert.ok(ok, "signature verifies");
  const bad = await crypto.subtle.verify({ name: "Ed25519" }, kp.publicKey, Buffer.from(env.sig, "base64"), Buffer.from(p0.payload + "x"));
  assert.ok(!bad, "tampered payload must not verify");
  // endpoint and chain guards
  assert.strictEqual(api.endpointOrigin("https://node.example/path?q=1"), "https://node.example");
  assert.strictEqual(api.endpointOrigin("http://localhost:8787"), "http://localhost:8787");
  for (const x of ["http://node.example", "ftp://x", "javascript:alert(1)", "", "node.example"]) assert.strictEqual(api.endpointOrigin(x), null, x);
  assert.ok(api.isDevnet("torihiki-devnet-1")); assert.ok(!api.isDevnet("torihiki-mainnet-1")); assert.ok(!api.isDevnet(undefined));
  // view models: rebucket, chart geometry, book rows
  const cs = [{ h: 10, open: 100, high: 110, low: 95, close: 105, volume: 3 }, { h: 11, open: 105, high: 108, low: 90, close: 92, volume: 5 },
              { h: 17, open: 92, high: 99, low: 91, close: 98, volume: 2 }, { h: 20, open: 98, high: 120, low: 97, close: 119, volume: 7 }];
  const r5 = api.rebucket(5, cs);
  assert.deepStrictEqual(r5.map((c) => c.h), [10, 15, 20]);
  assert.deepStrictEqual(r5[0], { h: 10, open: 100, high: 110, low: 90, close: 92, volume: 8 }, "first bucket merges h10 and h11");
  assert.strictEqual(api.rebucket(1, cs).length, 4);
  assert.deepStrictEqual(api.rebucket(5, []), []);
  const cm = api.chartModel(r5);
  assert.ok(!cm.empty && cm.candles.length === 3);
  assert.ok(cm.candles[0].yHigh < cm.candles[0].yLow, "high is above low on screen");
  assert.ok(cm.candles[2].up && !cm.candles[0].down && cm.candles[0].up === false, "up/down from close vs open");
  assert.ok(cm.candles.every((c) => c.x > 0 && c.x < cm.plotRight && c.bodyH >= 1));
  assert.ok(cm.candles.every((c) => c.volY >= cm.volTop - 0.001 && c.volY + c.volH <= cm.volBottom + 0.001), "volume stays in its band");
  assert.strictEqual(api.chartModel([]).empty, true);
  assert.strictEqual(api.chartModel(null).empty, true);
  const flat = api.chartModel([{ h: 1, open: 50, high: 50, low: 50, close: 50, volume: 0 }]);
  assert.ok(!flat.empty && Number.isFinite(flat.candles[0].yTop) && flat.candles[0].volH === 0, "one flat candle does not divide by zero");
  assert.strictEqual(api.chartModel(Array.from({ length: 500 }, (_, i) => ({ h: i, open: 1, high: 2, low: 0, close: 1, volume: 1 }))).candles.length, 120, "at most 120 candles");
  const bm = api.bookModel({ bids: [{ level: 99, qty: 2, cum: 2 }, { level: 98, qty: 3, cum: 5 }], asks: [{ level: 101, qty: 1, cum: 1 }, { level: 102, qty: 4, cum: 5 }] });
  assert.strictEqual(bm.spread, 2); assert.strictEqual(bm.mid, 100); assert.deepStrictEqual(bm.asks.map((r) => r.level), [102, 101], "asks are shown far to near");
  assert.strictEqual(bm.bids[1].pct, 100); assert.strictEqual(bm.bids[0].pct, 40);
  const eb = api.bookModel(null); assert.strictEqual(eb.spread, null); assert.strictEqual(eb.mid, null);
  assert.notStrictEqual(api.rebucket(5, cs)[0].volume, 7, "negative control: bucket volume is a sum, not the first candle");
  console.log("AIUEOS_SESSION_TORIHIKI_OK checks=" + checks);
})().catch((e) => { console.error("AIUEOS_SESSION_TORIHIKI_FAIL " + e.message); process.exit(1); });
