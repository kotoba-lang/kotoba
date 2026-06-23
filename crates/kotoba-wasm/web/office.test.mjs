// office.test.mjs — JS↔wasm E2E for the org-first office layer + CACAO bridge.
//
//   node web/office.test.mjs
//
// Drives the real `KotobaNode` wasm bindings (pkg-node) through:
//   1. office document write in the kotoba.office wire format ([{e,a,v_edn}])
//      -> commit -> datomicQ read-back (proves the v_edn contract end to end)
//   2. assertEncrypted/decrypt (sovereign field encryption, signal:v1:)
//   3. mintCacao (doc-b grant -> server-verifiable CACAO) at the wasm boundary
// The native test (cargo test -p kotoba-wasm) proves the minted CACAO verifies
// byte-identically under kotoba-auth DelegationChain::verify; this proves the
// same surface runs across the JS boundary.

import { KotobaNode } from "./pkg-node/kotoba_wasm.js";

let failures = 0;
function check(name, cond) {
  if (cond) console.log(`  ok   ${name}`);
  else { failures++; console.error(`  FAIL ${name}`); }
}

// ---- 1. office document write/read in the kotoba.office wire format ----
const node = new KotobaNode();
const did = node.useIdentity("07".repeat(32)); // 32-byte seed hex
check("useIdentity returns a did:key", typeof did === "string" && did.startsWith("did:key:"));

// mirrors kotoba.office/doc->tx output (v_edn: strings JSON-quoted, keywords bare,
// longs bare). doc "doc1" owned by org-alice, one heading block.
const tx = [
  { e: "doc1", a: ":doc/kind",      v_edn: ":doc/document" },
  { e: "doc1", a: ":doc/title",     v_edn: '"Q3 戦略メモ"' },
  { e: "doc1", a: ":doc/owner-org", v_edn: '"org-alice"' },
  { e: "doc1", a: ":doc/created-at",v_edn: "1719000005000" },
  { e: "b0",   a: ":block/kind",    v_edn: ":block/heading" },
  { e: "b0",   a: ":block/parent",  v_edn: '"doc1"' },
  { e: "b0",   a: ":block/order",   v_edn: '"a0"' },
  { e: "b0",   a: ":block/text",    v_edn: '"概要"' },
];
const n = node.transact(JSON.stringify(tx));
check("transact applied all office datoms", n === tx.length);
const root = node.commit();
check("commit yields a content-addressed root CID", typeof root === "string" && root.length > 0);

const titleRes = JSON.parse(
  node.datomicQ('[:find ?t :where [?e :doc/title ?t]]', "[]"),
);
check("datomicQ reads the doc title back", JSON.stringify(titleRes).includes("Q3 戦略メモ"));

const blockRes = JSON.parse(
  node.datomicQ('[:find ?txt :where [?b :block/parent "doc1"] [?b :block/text ?txt]]', "[]"),
);
check("datomicQ reads a block under the doc", JSON.stringify(blockRes).includes("概要"));

// ---- 2. sovereign field encryption ----
node.assertEncrypted("b1", ":block/text", "会員番号 12345");
const env = JSON.parse(node.datomicQ('[:find ?v :where [?e :block/text ?v]]', "[]"));
const envStr = JSON.stringify(env);
check("encrypted block stored as signal:v1: ciphertext", envStr.includes("signal:v1:"));
check("plaintext never appears in the store", !envStr.includes("12345"));
// recover one envelope and decrypt it
const envValue = (envStr.match(/signal:v1:[0-9a-f]+/) || [])[0];
check("decrypt round-trips the ciphertext", node.decrypt(envValue) === "会員番号 12345");

// ---- 3. sovereign identity: canonical did:key + deterministic private graph CID ----
const accountDid = node.accountDid();
check("accountDid is a canonical did:key:z6Mk", accountDid.startsWith("did:key:z6Mk"));
const graphId = node.privateGraphId();
check("privateGraphId returns a graph CID", typeof graphId === "string" && graphId.length > 0);
// same identity -> same graph CID (the server auto-registers Private{owner=account} on it)
const node2 = new KotobaNode();
node2.useIdentity("07".repeat(32));
check("privateGraphId is deterministic for an identity", node2.privateGraphId() === graphId);
const node3 = new KotobaNode();
node3.useIdentity("09".repeat(32));
check("different identity -> different private graph CID", node3.privateGraphId() !== graphId);

// ---- 4. CACAO mint at the wasm boundary (doc-b grant -> capability) ----
// A WRITE grants BOTH datom:transact AND tx:create, scoped to the account's graph CID.
const W = ["datom:transact", "tx:create"];
const OP = "did:key:zOperatorNodeDid"; // aud = server operator DID
const cacaoB64 = node.mintCacao(OP, graphId, W, "office-nonce-1", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z");
check("mintCacao returns a non-empty base64 cacao_b64", typeof cacaoB64 === "string" && cacaoB64.length > 0);
const cacaoBytes = Buffer.from(cacaoB64, "base64");
check("cacao_b64 decodes to a non-empty CBOR blob", cacaoBytes.length > 0);
// deterministic: same identity + same args -> identical signed CACAO (Ed25519 det.)
const cacaoB64b = node.mintCacao(OP, graphId, W, "office-nonce-1", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z");
check("mintCacao is deterministic for identical inputs", cacaoB64 === cacaoB64b);
// different nonce -> different signed bytes
const cacaoB64c = node.mintCacao(OP, graphId, W, "office-nonce-2", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z");
check("different nonce yields a different CACAO", cacaoB64 !== cacaoB64c);
// read CACAO: single datom:read cap, scoped to the graph CID (datomic.datoms uses
// require_datomic_read → graph.to_multibase(), same scope as the write).
const readCacao = node.mintCacao(OP, graphId, ["datom:read"], "office-read-1", "2026-01-01T00:00:00Z", "2099-01-01T00:00:00Z");
check("read CACAO mints distinctly from write CACAO", typeof readCacao === "string" && readCacao !== cacaoB64);

console.log(failures === 0 ? "\nALL OK" : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
