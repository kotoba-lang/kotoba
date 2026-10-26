// Tests for git-base-auth (Base smart-contract auth + x402 payment gate).
// Pure parts run without a chain; verifyTxPayment is exercised with a stubbed
// globalThis.fetch (keyless RPC endpoints are never contacted).
import { test } from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { secp256k1 } from "@noble/curves/secp256k1.js";
import { keccak_256 } from "@noble/hashes/sha3.js";
import {
  eip191Digest, siweMessage, recoverAddress, parsePkh, verifyPkhCacao,
  quotedUsd, requirement, challenge, decodePayment, payloadErrors,
  verifyTxPayment, spendReserve, rpcUrls, erc1271Valid,
  USDC_BASE, USDC_BASE_SEPOLIA, TRANSFER_TOPIC, ERC1271_MAGIC, X402_VERSION,
} from "../worker/git-base-auth.mjs";

// The USDC contracts are MEASURED constants (pay.x402 called name()/version()
// on-chain 2026-09-01; the live gateway 402 bodies publish the same values).
// Pin them: a wrong asset address makes every payment "wrong-recipient" or
// names a worthless token.
test("USDC contract addresses match the measured on-chain constants", () => {
  assert.equal(USDC_BASE, "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913");
  assert.equal(USDC_BASE_SEPOLIA, "0x036CbD53842c5426634e7929541eC2318f3dCF7e");
});

const hex = (b) => Buffer.from(b).toString("hex");

test("eip191Digest matches the personal_sign prefix rule", () => {
  const d = eip191Digest("hello");
  const expected = keccak_256(Buffer.concat([
    Buffer.from("\x19Ethereum Signed Message:\n5"), Buffer.from("hello")]));
  assert.equal(hex(d), hex(expected));
});

test("recoverAddress round-trips a personal_sign signature", () => {
  const priv = randomBytes(32);
  const pub = secp256k1.getPublicKey(priv, false);
  const address = "0x" + hex(keccak_256(pub.slice(1)).slice(-20));
  const message = "sign in";
  const rec = secp256k1.sign(eip191Digest(message), priv, { prehash: false, lowS: true, format: "recovered" });
  const sig = new Uint8Array(65);
  sig.set(rec.slice(1), 0);
  sig[64] = 27 + rec[0];
  assert.equal(recoverAddress(message, "0x" + hex(sig)), address);
});

test("recoverAddress rejects a non-65-byte or wrong-v signature", () => {
  assert.equal(recoverAddress("m", "0x" + "00".repeat(64)), null);
  const priv = randomBytes(32);
  const rec = secp256k1.sign(eip191Digest("m"), priv, { prehash: false, lowS: true, format: "recovered" });
  const sig = new Uint8Array(65);
  sig.set(rec.slice(1), 0);
  sig[64] = 30; // invalid v
  assert.equal(recoverAddress("m", "0x" + hex(sig)), null);
});

test("parsePkh accepts eip155 chains and rejects others", () => {
  assert.deepEqual(parsePkh("did:pkh:eip155:8453:0xAbCdEf0123456789AbCdEf0123456789AbCdEf01"),
    { chainId: 8453, address: "0xabcdef0123456789abcdef0123456789abcdef01" });
  assert.deepEqual(parsePkh("did:pkh:eip155:84532:0xAbCdEf0123456789AbCdEf0123456789AbCdEf01")?.chainId, 84532);
  // chain 1 parses as a pkh (parsing is not acceptance) but verifyPkhCacao refuses it
  assert.equal(parsePkh("did:pkh:eip155:1:0xAbCdEf0123456789AbCdEf0123456789AbCdEf01").chainId, 1);
  assert.equal(parsePkh("did:key:zabcd"), null);
  assert.equal(parsePkh(undefined), null);
});

test("siweMessage carries the pkh chain id and resources", () => {
  const msg = siweMessage({ domain: "git.kotobase.net", iss: "did:pkh:eip155:8453:0xabc", aud: "https://git.kotobase.net",
    version: "1", chainId: 8453, nonce: "n1", iat: "2026-09-08T00:00:00Z",
    resources: ["urn:kotobase:git:org/repo"] });
  assert.match(msg, /Chain ID: 8453/);
  assert.match(msg, /urn:kotobase:git:org\/repo/);
});

// ---- x402 wire shapes ----

const TREASURY = "0x" + "11".repeat(20);
const REQ = requirement({ payTo: TREASURY, usd: 0.001, resource: "https://git.kotobase.net/org/repo/objects/aa/bb", net: "base", scheme: "transaction" });

test("requirement: transaction scheme, micros price, USDC asset, base network", () => {
  assert.equal(REQ.scheme, "transaction");
  assert.equal(REQ.network, "base");
  assert.equal(REQ.maxAmountRequired, "1000"); // $0.001 = 1000 micro-USDC
  assert.equal(REQ.asset, USDC_BASE);
  assert.equal(REQ.payTo, TREASURY);
  assert.equal(REQ.extra, undefined);
});

test("requirement: exact scheme carries the USDC EIP-712 domain", () => {
  const r = requirement({ payTo: TREASURY, usd: 0.001, resource: "r", net: "base", scheme: "exact", facilitator: "https://x402.nexus" });
  assert.deepEqual(r.extra, { name: "USD Coin", version: "2" });
});

test("challenge body shape", () => {
  const c = challenge([REQ], "no payment");
  assert.equal(c.x402Version, X402VersionConst());
  function X402VersionConst() { return 1; }
  assert.deepEqual(c.accepts, [REQ]);
  assert.equal(c.error, "no payment");
});

test("quotedUsd: ?usd= may raise, never lower", () => {
  assert.equal(quotedUsd(undefined, 0.001), 0.001);
  assert.equal(quotedUsd("0.0000001", 0.001), 0.001);
  assert.equal(quotedUsd("5", 0.001), 5);
  assert.equal(quotedUsd("garbage", 0.001), 0.001);
  assert.equal(quotedUsd("-3", 0.001), 0.001);
});

test("decodePayment canonicalizes CAIP-2 network echoes", () => {
  const p = { x402Version: 1, scheme: "transaction", network: "eip155:8453", payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } };
  const d = decodePayment(Buffer.from(JSON.stringify(p)).toString("base64"));
  assert.equal(d.network, "base");
  assert.equal(decodePayment("!!!not base64!!!"), null);
  assert.equal(decodePayment(Buffer.from(JSON.stringify({ scheme: 42 })).toString("base64")), null);
});

test("payloadErrors: transaction scheme", () => {
  const now = 1000;
  const good = { scheme: "transaction", network: "base", payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } };
  assert.deepEqual(payloadErrors(good, REQ, now), []);
  assert.ok(payloadErrors({ ...good, scheme: "exact" }, REQ, now).includes("scheme-mismatch"));
  assert.ok(payloadErrors({ ...good, network: "base-sepolia" }, REQ, now).includes("network-mismatch"));
  assert.ok(payloadErrors({ ...good, payload: {} }, REQ, now).includes("missing-tx-hash"));
  assert.ok(payloadErrors({ ...good, payload: { txHash: "0x1234", from: good.payload.from } }, REQ, now).includes("missing-tx-hash"));
  assert.ok(payloadErrors({ ...good, payload: { txHash: good.payload.txHash, from: "0xzz" } }, REQ, now).includes("missing-payer"));
});

test("payloadErrors: exact scheme underpaid/expired/recipient", () => {
  const now = 1000;
  const exactReq = requirement({ payTo: TREASURY, usd: 0.001, resource: "r", net: "base", scheme: "exact" });
  const auth = { to: TREASURY, value: "1000", validBefore: String(now + 60), validAfter: String(now - 60) };
  const pay = { scheme: "exact", network: "base", payload: { authorization: auth, signature: "0x" + "99".repeat(65) } };
  assert.deepEqual(payloadErrors(pay, exactReq, now), []);
  const under = structuredClone(pay); under.payload.authorization.value = "999";
  assert.ok(payloadErrors(under, exactReq, now).includes("underpaid"));
  const wrong = structuredClone(pay); wrong.payload.authorization.to = "0x" + "33".repeat(20);
  assert.ok(payloadErrors(wrong, exactReq, now).includes("wrong-recipient"));
  const late = structuredClone(pay); late.payload.authorization.validBefore = String(now);
  assert.ok(payloadErrors(late, exactReq, now).includes("authorization-expired"));
  const noSig = structuredClone(pay); delete noSig.payload.signature;
  assert.ok(payloadErrors(noSig, exactReq, now).includes("missing-signature"));
});

// ---- on-chain verification with a stubbed RPC ----

// Fetch stub: routes eth_* calls to a scenario object.
function stubRpc(scenario) {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    const body = JSON.parse(init.body);
    let result;
    if (body.method === "eth_getTransactionReceipt") result = scenario.receipt ?? null;
    else if (body.method === "eth_blockNumber") result = scenario.head ?? "0x0";
    else if (body.method === "eth_getCode") result = scenario.code ?? "0x";
    else if (body.method === "eth_call") result = scenario.call ?? null;
    else result = null;
    if (scenario.throw) return realFetch.call(globalThis, "http://127.0.0.1:1", init).catch(() => { throw new Error("down"); });
    return { ok: true, json: async () => ({ jsonrpc: "2.0", id: 1, result }) };
  };
  return () => { globalThis.fetch = realFetch; };
}

const usdcTransferLog = (to, micros) => ({
  address: USDC_BASE,
  topics: [TRANSFER_TOPIC, "0x" + "22".repeat(32).slice(0, 64), "0x" + "0".repeat(24) + to.slice(2)],
  data: "0x" + micros.toString(16),
});

test("verifyTxPayment: accepts a confirmed, sufficient USDC transfer to the treasury", async () => {
  const restore = stubRpc({ receipt: { status: "0x1", blockNumber: "0x64", logs: [usdcTransferLog(TREASURY, 5000)] }, head: "0x6a" });
  try {
    const v = await verifyTxPayment({ KOTOBASE_TREASURY_ADDR: TREASURY }, REQ,
      { payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } });
    assert.equal(v.ok, true);
    assert.equal(v.paidMicros, "5000");
  } finally { restore(); }
});

test("verifyTxPayment: rejects unconfirmed / reverted / underpaid / wrong-recipient / no-transfer", async () => {
  const base = { KOTOBASE_TREASURY_ADDR: TREASURY };
  const pay = { payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } };
  const cases = [
    [{ receipt: null, head: "0x6a" }, "tx-not-found"],
    [{ receipt: { status: "0x0", blockNumber: "0x64", logs: [usdcTransferLog(TREASURY, 5000)] }, head: "0x6a" }, "tx-reverted"],
    [{ receipt: { status: "0x1", blockNumber: "0x69", logs: [usdcTransferLog(TREASURY, 5000)] }, head: "0x6a" }, "insufficient-confirmations"], // 2 confs
    [{ receipt: { status: "0x1", blockNumber: "0x64", logs: [usdcTransferLog(TREASURY, 999)] }, head: "0x6a" }, "underpaid"],
    [{ receipt: { status: "0x1", blockNumber: "0x64", logs: [usdcTransferLog("0x" + "33".repeat(20), 5000)] }, head: "0x6a" }, "wrong-recipient"],
    [{ receipt: { status: "0x1", blockNumber: "0x64", logs: [] }, head: "0x6a" }, "no-usdc-transfer"],
  ];
  for (const [scenario, reason] of cases) {
    const restore = stubRpc(scenario);
    try {
      const v = await verifyTxPayment(base, REQ, pay);
      assert.equal(v.ok, false, reason);
      assert.equal(v.reason, reason);
    } finally { restore(); }
  }
});

test("verifyTxPayment: NaN head block cannot fold into a pass", async () => {
  const restore = stubRpc({ receipt: { status: "0x1", blockNumber: "0x64", logs: [usdcTransferLog(TREASURY, 5000)] }, head: "0xzz" });
  try {
    const v = await verifyTxPayment({ KOTOBASE_TREASURY_ADDR: TREASURY }, REQ,
      { payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } });
    assert.equal(v.ok, false);
    assert.equal(v.reason, "bad-block-number");
  } finally { restore(); }
});

test("verifyTxPayment: no treasury configured refuses (503-class), never passes", async () => {
  const v = await verifyTxPayment({}, REQ, { payload: { txHash: "0x" + "ab".repeat(32), from: "0x" + "22".repeat(20) } });
  assert.equal(v.ok, false);
  assert.equal(v.reason, "treasury-not-configured");
});

test("spendReserve: one tx pays once; missing store refuses", async () => {
  const seen = new Map();
  const store = { get: (k) => Promise.resolve(seen.get(k) ?? null), put: (k, v) => { seen.set(k, v); return Promise.resolve(); } };
  const verification = { payer: "0xpayer", paidMicros: "1000", txHash: "0xtx1" };
  const r1 = await spendReserve({ GIT_STORE: store }, REQ, verification);
  assert.equal(r1.allow, true);
  const r2 = await spendReserve({ GIT_STORE: store }, REQ, verification);
  assert.equal(r2.allow, false);
  assert.equal(r2.reason, "tx-already-spent");
  const r3 = await spendReserve({}, REQ, verification);
  assert.equal(r3.allow, false); // no KV = refuse, one tx must never pay twice
});

// ---- ERC-1271 ----

test("erc1271Valid: magic value passes, anything else refuses", async () => {
  const contract = "0x" + "44".repeat(20);
  const digest = new Uint8Array(32).fill(7);
  let restore = stubRpc({ code: "0x1234", call: ERC1271_MAGIC + "0000...".slice(0, 0) });
  try {
    const ok = await erc1271Valid({ KOTOBASE_EVM_RPC: "http://stub" }, "base", contract, digest, "0x" + "99".repeat(65));
    assert.equal(ok, true);
  } finally { restore(); }
  restore = stubRpc({ code: "0x1234", call: "0xdeadbeef" });
  try {
    const bad = await erc1271Valid({ KOTOBASE_EVM_RPC: "http://stub" }, "base", contract, digest, "0x" + "99".repeat(65));
    assert.equal(bad, false);
  } finally { restore(); }
});

// ---- verifyPkhCacao (EOA path, no chain needed; contract path via stub) ----

function makePkhPayload(address, chainId = 8453) {
  return {
    domain: "git.kotobase.net",
    iss: `did:pkh:eip155:${chainId}:${address}`,
    aud: "https://git.kotobase.net",
    version: "1",
    nonce: "nonce-1",
    iat: new Date().toISOString(),
    exp: new Date(Date.now() + 300000).toISOString(),
    resources: ["urn:kotobase:git:org/repo"],
  };
}

test("verifyPkhCacao: EOA signature that recovers to the issuer passes", async () => {
  const priv = randomBytes(32);
  const pub = secp256k1.getPublicKey(priv, false);
  const address = "0x" + hex(keccak_256(pub.slice(1)).slice(-20));
  const payload = makePkhPayload(address);
  const message = siweMessage({ ...payload, chainId: 8453 });
  const rec = secp256k1.sign(eip191Digest(message), priv, { prehash: false, lowS: true, format: "recovered" });
  const sig = new Uint8Array(65);
  sig.set(rec.slice(1), 0);
  sig[64] = 27 + rec[0];
  const v = await verifyPkhCacao({}, payload, "0x" + hex(sig));
  assert.deepEqual(v, { ok: true, address, signer: "eoa", net: "base" });
});

test("verifyPkhCacao: an EOA wrong signature is refused WITHOUT an RPC call", async () => {
  const priv = randomBytes(32);
  const other = randomBytes(32);
  const pub = secp256k1.getPublicKey(priv, false);
  const address = "0x" + hex(keccak_256(pub.slice(1)).slice(-20));
  const payload = makePkhPayload(address);
  const message = siweMessage({ ...payload, chainId: 8453 });
  // sign with `other` but name `address` as issuer
  const rec = secp256k1.sign(eip191Digest(message), other, { prehash: false, lowS: true, format: "recovered" });
  const sig = new Uint8Array(65);
  sig.set(rec.slice(1), 0);
  sig[64] = 27 + rec[0];
  let rpcTouched = false;
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => { rpcTouched = true; throw new Error("should not call rpc"); };
  try {
    const v = await verifyPkhCacao({}, payload, "0x" + hex(sig));
    assert.equal(v.ok, false);
    assert.equal(v.reason, "eoa-signature-mismatch");
    assert.equal(rpcTouched, false);
  } finally { globalThis.fetch = realFetch; }
});

test("verifyPkhCacao: expired / bad iat / unsupported chain refuse", async () => {
  const payload = makePkhPayload("0x" + "11".repeat(20));
  payload.exp = new Date(Date.now() - 1000).toISOString();
  let v = await verifyPkhCacao({}, payload, null);
  assert.equal(v.ok, false);
  payload.exp = new Date(Date.now() + 300000).toISOString();
  payload.iat = new Date(Date.now() + 3600000).toISOString();
  v = await verifyPkhCacao({}, payload, null);
  assert.equal(v.ok, false);
  v = await verifyPkhCacao({}, makePkhPayload("0x" + "11".repeat(20), 1), null);
  assert.equal(v.ok, false);
  assert.equal(v.reason, "chain-not-allowed"); // chain 1 is not a verifiable pkh chain here
});

test("rpcUrls: configured endpoint goes first, keyless defaults behind", () => {
  const urls = rpcUrls({ KOTOBASE_EVM_RPC: "https://keyed.example/v3" }, "base");
  assert.equal(urls[0], "https://keyed.example/v3");
  assert.ok(urls.length > 1);
  const sepolia = rpcUrls({}, "base-sepolia");
  assert.ok(sepolia.some((u) => u.includes("sepolia")));
});
