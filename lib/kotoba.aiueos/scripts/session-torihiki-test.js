// Checks resources/aiueos/session/assets/torihiki.js against vectors the torihiki engine produced.
// Run: node scripts/session-torihiki-test.js   (Node with WebCrypto Ed25519; no network)
"use strict";
const path = require("path"), fs = require("fs"), assert = require("assert");
const root = path.resolve(__dirname, "..");
const api = require(path.join(root, "resources/aiueos/session/assets/torihiki.js"));
const vec = JSON.parse(fs.readFileSync(path.join(root, "test/session/torihiki-vectors.json"), "utf8"));

(async () => {
  let n = 0;
  for (const d of vec.derive) { assert.strictEqual(await api.deriveAccount(d.pubkey), d.account, "derive " + d.pubkey); n++; }
  for (const p of vec.payloads) { assert.strictEqual(api.signingPayload(p.chain, p.account, p.nonce, p.tx), p.payload, JSON.stringify(p.tx)); n++; }
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
  console.log("AIUEOS_SESSION_TORIHIKI_OK checks=" + (n + 12));
})().catch((e) => { console.error("AIUEOS_SESSION_TORIHIKI_FAIL " + e.message); process.exit(1); });
