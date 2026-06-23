// office_http_e2e.mjs — LIVE end-to-end against a running `kotoba serve`.
//
//   KOTOBA_URL=http://localhost:8099 node web/office_http_e2e.mjs
//
// Proves the full sovereign office round-trip over real HTTP with the browser
// (pkg-node) WASM doing all the crypto:
//   1. discover the node operator DID (CACAO aud) from public key.custodianInfo
//   2. encrypt a block body client-side (signal:v1:) — server never sees plaintext
//   3. sync to the account's OWN private graph with a transact CACAO (auto-registered)
//   4. read it back with a read CACAO; reconstruct + decrypt client-side
// Mirrors kotoba.office sync-doc!/pull-doc + encrypt-doc, but inlined so it needs no
// shadow-cljs build.

import { KotobaNode } from "./pkg-node/kotoba_wasm.js";

const REMOTE = process.env.KOTOBA_URL || "http://localhost:8099";
let failures = 0;
const check = (n, c) => { if (c) console.log(`  ok   ${n}`); else { failures++; console.error(`  FAIL ${n}`); } };
const IAT = "2026-01-01T00:00:00Z", EXP = "2099-01-01T00:00:00Z";
let nonceN = 0;
const nonce = () => `e2e-${Date.now()}-${nonceN++}`;

async function post(path, body) {
  const r = await fetch(`${REMOTE}/xrpc/${path}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  return { ok: r.ok, status: r.status, json: r.ok ? await r.json() : await r.text() };
}

const node = new KotobaNode();
node.useIdentity("07".repeat(32));            // the account identity
const account = node.accountDid();
const graph = node.privateGraphId();
check("account is did:key:z6Mk", account.startsWith("did:key:z6Mk"));

// 1. discover operator DID (CACAO aud)
const ci = await fetch(`${REMOTE}/xrpc/com.etzhayyim.apps.kotoba.key.custodianInfo`).then((r) => r.json());
const operatorDid = ci.did;
check("discovered operator DID (aud)", typeof operatorDid === "string" && operatorDid.startsWith("did:key:"));

// 2. encrypt the body client-side (server must never see this plaintext)
const SECRET = "会員番号 12345 機密本文";
const envelope = node.encrypt(SECRET);
check("body encrypted to signal:v1: envelope", envelope.startsWith("signal:v1:"));

// 3. sync to the account's own private graph with a transact CACAO
const txEdn =
  `[[:db/add "doc1" :node/lid "doc1"]` +
  `[:db/add "doc1" :doc/kind :doc/document]` +
  `[:db/add "doc1" :doc/title "Q3 戦略メモ"]` +
  `[:db/add "b0" :node/lid "b0"]` +
  `[:db/add "b0" :block/kind :block/paragraph]` +
  `[:db/add "b0" :block/parent "doc1"]` +
  `[:db/add "b0" :block/order "a0"]` +
  `[:db/add "b0" :block/text ${JSON.stringify(envelope)}]]`;
const wcacao = node.mintCacao(operatorDid, graph, ["datom:transact", "tx:create"], nonce(), IAT, EXP);
const w = await post("com.etzhayyim.apps.kotoba.datomic.transact", { graph, tx_edn: txEdn, cacao_b64: wcacao });
check("transact accepted (account owns its auto-registered private graph)", w.ok);
check("transact wrote datoms", w.ok && w.json.datom_count >= 5);

// a non-owner write must be rejected (different identity, same target graph CID)
const intruder = new KotobaNode();
intruder.useIdentity("aa".repeat(32));
const icacao = intruder.mintCacao(operatorDid, graph, ["datom:transact", "tx:create"], nonce(), IAT, EXP);
const bad = await post("com.etzhayyim.apps.kotoba.datomic.transact", { graph, tx_edn: "[[:db/add \"x\" :n 1]]", cacao_b64: icacao });
check("non-owner write to the account's graph is rejected", !bad.ok && bad.status === 401);

// 4. read back with a read CACAO; the server holds only ciphertext
const rcacao = node.mintCacao(operatorDid, graph, ["datom:read"], nonce(), IAT, EXP);
const rd = await post("com.etzhayyim.apps.kotoba.datomic.datoms", {
  graph, index: "eavt", components_edn: [], cacao_b64: rcacao,
});
check("read accepted with read CACAO", rd.ok);
const datoms = rd.ok ? rd.json.datoms : [];
const raw = JSON.stringify(datoms);
check("plaintext body never present on the server", !raw.includes("12345"));
check("title plaintext is readable structure", raw.includes("Q3 戦略メモ"));
const textDatom = datoms.find((d) => d.a === ":block/text");
check("body stored as signal:v1: ciphertext", textDatom && textDatom.v_edn.includes("signal:v1:"));
// decrypt client-side
const back = textDatom ? node.decrypt(JSON.parse(textDatom.v_edn)) : null;
check("client decrypts the synced body back to plaintext", back === SECRET);

// no-CACAO read is denied
const denied = await post("com.etzhayyim.apps.kotoba.datomic.datoms", { graph, index: "eavt", components_edn: [] });
check("private read without a CACAO is denied", !denied.ok && denied.status === 401);

// ---- 5. team sharing: a MEMBER writes to the ORG's graph via depth-2 delegation ----
const org = new KotobaNode(); org.useIdentity("b1".repeat(32));   // the org/owner identity
const member = new KotobaNode(); member.useIdentity("c2".repeat(32)); // a team member
const orgGraph = org.privateGraphId();
const W2 = ["datom:transact", "tx:create"];
// org delegates to member: a root grant (aud = the member's DID)
const rootGrant = org.mintCacao(member.accountDid(), orgGraph, W2, nonce(), IAT, EXP);
// member assembles the [root, leaf] chain (leaf aud = server)
const chain = member.mintDelegated(rootGrant, operatorDid, orgGraph, W2, nonce(), IAT, EXP);
const tw = await post("com.etzhayyim.apps.kotoba.datomic.transact", {
  graph: orgGraph, tx_edn: `[[:db/add "t1" :doc/title "Team doc"]]`, cacao_b64: chain,
});
if (!tw.ok) console.error("    depth-2 transact error:", tw.status, tw.json);
check("delegated member writes to the org graph (depth-2)", tw.ok);
// the org graph is bound to the ORG owner, not the member: a bare member CACAO is rejected
const solo = member.mintCacao(operatorDid, orgGraph, W2, nonce(), IAT, EXP);
const sw = await post("com.etzhayyim.apps.kotoba.datomic.transact", {
  graph: orgGraph, tx_edn: `[[:db/add "x" :n 1]]`, cacao_b64: solo,
});
check("non-delegated member write to the org graph is rejected", !sw.ok && sw.status === 401);

console.log(failures === 0 ? "\nALL OK" : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
