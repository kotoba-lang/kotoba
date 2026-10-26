// git-base-auth — Base smart-contract auth + x402 payment for git.kotobase.net.
//
// Plugged into git-worker.mjs. Two capabilities:
//
// 1. Base auth for private repo reads. A CACAO (SIWE) whose issuer is
//    `did:pkh:eip155:<chain>:0x...` (EOA wallet or smart contract wallet):
//      - EOA: EIP-191 personal_sign ecrecover (@noble/curves). The recovered
//        address MUST equal the did:pkh address.
//      - Contract wallet (eth_getCode non-empty): ERC-1271 — eth_call
//        isValidSignature(bytes32,bytes) MUST return 0x1626ba7e.
//    Fail-closed: any RPC error rejects. The SIWE message's Chain ID must
//    match the did:pkh chain (8453 Base mainnet or 84532 base-sepolia).
//    Policy per root SECURITY.md: wallet auth verifies server-side (single-use
//    nonce, domain/URI, chain, expiry); wallet connection alone authenticates
//    nothing. The nonce replay check lives in git-worker (nonces table).
//
// 2. x402 payment for paid repo reads:
//      - No X-PAYMENT -> 402 challenge. `accepts` offers scheme "exact"
//        (EIP-3009, settled via the x402.nexus facilitator when
//        KOTOBASE_X402_FACILITATOR is set) first, then scheme "transaction"
//        (buyer broadcasts the USDC transfer and presents the tx hash; the
//        worker confirms with its own eth_getTransactionReceipt reads).
//      - X-PAYMENT present -> structural checks -> on-chain verify (USDC
//        Transfer log to the treasury, amount >= price, >= 3 confirmations,
//        successful tx) -> spend-dedupe via GIT_STORE KV (one tx cannot pay
//        twice) -> serve with X-PAYMENT-RESPONSE header.
//
// Priced in USDC micros (6 decimals). `?usd=` may RAISE the quoted price,
// never lower it (same rule as kotobase.x402).
//
// Constants are shared with kotoba-lang/pay (pay.rail.base-l2, pay.x402) and
// kotoba-lang/treasury — keep them in sync when those change.
import { secp256k1 } from "@noble/curves/secp256k1.js";
import { keccak_256 } from "@noble/hashes/sha3.js";

export const USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
export const USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e";
export const TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";
export const ERC1271_MAGIC = "0x1626ba7e";
export const MIN_CONFIRMATIONS = 3;
export const BASE_CHAIN_ID = 8453;
export const BASE_SEPOLIA_CHAIN_ID = 84532;
export const X402_VERSION = 1;

const enc = new TextEncoder();
const lc = (s) => String(s || "").toLowerCase();
const usdcFor = (net) => (net === "base-sepolia" ? USDC_BASE_SEPOLIA : USDC_BASE);
const chainIdFor = (net) => (net === "base-sepolia" ? BASE_SEPOLIA_CHAIN_ID : BASE_CHAIN_ID);
// v1 wire uses bare names; v2-era clients may echo CAIP-2 for the same chain
// (same accommodation kotobase.x402 makes).
const canonNet = (n) => (n === "eip155:8453" ? "base"
  : n === "eip155:84532" ? "base-sepolia" : n);

// Keyless JSON-RPC endpoints (same list as kotobase.evm-index; a keyed
// KOTOBASE_EVM_RPC / KOTOBASE_EVM_RPC_BASE goes FIRST when set — the
// gateway's measured lesson: keyless defaults get throttled, so the
// configured endpoint must be tried first, and a provider outage must not
// take the route down).
export function rpcUrls(env, net) {
  const configured = [env.KOTOBASE_EVM_RPC_BASE, env.KOTOBASE_EVM_RPC].filter(Boolean);
  const keyless = canonNet(net) === "base-sepolia"
    ? ["https://base-sepolia.gateway.tenderly.co", "https://sepolia.base.org"]
    : ["https://base.gateway.tenderly.co", "https://gateway.tenderly.co/public/base",
       "https://base.drpc.org", "https://base-rpc.publicnode.com", "https://mainnet.base.org"];
  return [...configured, ...keyless];
}

export async function rpcCall(env, net, method, params) {
  let lastErr = new Error("no rpc configured");
  for (const url of rpcUrls(env, net)) {
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      });
      if (!r.ok) { lastErr = new Error("rpc status " + r.status); continue; }
      const j = await r.json();
      if (j.error) { lastErr = new Error("rpc error: " + (j.error.message || j.error.code)); continue; }
      return j.result;
    } catch (e) { lastErr = e; }
  }
  throw lastErr;
}

const hexToLong = (h) => {
  if (typeof h !== "string" || !/^0x[0-9a-f]+$/i.test(h)) return null;
  try { return Number(BigInt(h)); } catch (_) { return null; }
};
const hexToBytes = (h) => {
  const s = h.startsWith("0x") ? h.slice(2) : h;
  if (s.length % 2 !== 0 || /[^0-9a-f]/i.test(s)) return null;
  return Uint8Array.from((s.match(/../g) || []).map((x) => parseInt(x, 16)));
};
const bytesToHex = (b) => [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

// ---- EIP-191 / SIWE (EOA) ----

export function eip191Digest(message) {
  const payload = enc.encode(message);
  const prefix = enc.encode(`\x19Ethereum Signed Message:\n${payload.length}`);
  const buf = new Uint8Array(prefix.length + payload.length);
  buf.set(prefix, 0); buf.set(payload, prefix.length);
  return keccak_256(buf);
}

export function siweMessage(p) {
  const lines = [`${p.domain} wants you to sign in with your Ethereum account:`,
    String(p.iss || "").split(":").at(-1), "", `URI: ${p.aud}`,
    `Version: ${p.version}`, `Chain ID: ${p.chainId}`, `Nonce: ${p.nonce}`,
    `Issued At: ${p.iat}`];
  if (p.exp) lines.push(`Expiration Time: ${p.exp}`);
  if (p.resources?.length) lines.push("Resources:", ...p.resources.map((r) => `- ${r}`));
  return lines.join("\n");
}

// Recover the EOA address from a 65-byte personal_sign signature.
// Wire form is [r(32) || s(32) || v(27|28)]; noble's recovered form is
// [recoveryBit || r || s] — convert before recovering.
export function recoverAddress(message, sigHex) {
  try {
    const sig = hexToBytes(sigHex);
    if (!sig || sig.length !== 65) return null;
    const v = sig[64];
    if (v !== 27 && v !== 28) return null;
    const digest = eip191Digest(message);
    const noble = new Uint8Array(65);
    noble[0] = v - 27;
    noble.set(sig.slice(0, 64), 1);
    const pub = secp256k1.Signature.fromBytes(noble, "recovered")
      .recoverPublicKey(digest)
      .toBytes(false); // uncompressed 65-byte public key
    return "0x" + bytesToHex(keccak_256(pub.slice(1)).slice(12));
  } catch (_) { return null; }
}


// ---- did:pkh CACAO verification (EOA + ERC-1271) ----

const PKH_RE = /^did:pkh:eip155:(\d+):0x[0-9a-fA-F]{40}$/;

// did:pkh issuer parsing. Returns {chainId, address} or null.
export function parsePkh(did) {
  const m = PKH_RE.exec(did || "");
  if (!m) return null;
  return { chainId: Number(m[1]), address: lc(did.slice(did.lastIndexOf(":") + 1)) };
}

const netForChainId = (cid) => (cid === BASE_CHAIN_ID ? "base"
  : cid === BASE_SEPOLIA_CHAIN_ID ? "base-sepolia" : null);

// ERC-1271: ask the contract whether it owns this signature.
// bytes32 = keccak256 of the signed message (the EIP-191 digest, matching
// what personal_sign signs). ANY non-magic / failed call rejects.
export async function erc1271Valid(env, net, contract, digest32, sigHex) {
  const data = "0x1626ba7e"
    + bytesToHex(digest32).padStart(64, "0")
    + "0000000000000000000000000000000000000000000000000000000000000040"
    + "00000000000000000000000000000000000000000000000000000000000000" + (sigHex.startsWith("0x") ? (sigHex.length - 2) / 2 : sigHex.length / 2).toString(16).padStart(64, "0")
    + (sigHex.startsWith("0x") ? sigHex.slice(2) : sigHex);
  try {
    const out = await rpcCall(env, net, "eth_call",
      [{ to: contract, data }, "latest"]);
    return out && lc(out).startsWith(ERC1271_MAGIC);
  } catch (_) { return false; }
}

// Verify one did:pkh CACAO payload (already CBOR-decoded by the caller).
// `payload` is the SIWE property map; `signature` is the hex personal_sign
// signature from wire.s.s. Returns { ok: true, address } or { ok: false, reason }.
export async function verifyPkhCacao(env, payload, signature) {
  const pkh = parsePkh(payload.iss);
  if (!pkh) return { ok: false, reason: "not-a-pkh-issuer" };
  const net = netForChainId(pkh.chainId);
  if (!net) return { ok: false, reason: "chain-not-allowed" };
  if (!payload.domain || !payload.aud || !payload.nonce) return { ok: false, reason: "incomplete-siwe" };
  const iat = Date.parse(payload.iat);
  const exp = payload.exp ? Date.parse(payload.exp) : NaN;
  const now = Date.now();
  if (!Number.isFinite(iat) || iat > now + 300000) return { ok: false, reason: "bad-iat" };
  if (Number.isFinite(exp) && now >= exp) return { ok: false, reason: "expired" };
  // The message the wallet signed is the SIWE text with the pkh chain id.
  const message = siweMessage({ ...payload, chainId: pkh.chainId });
  // EOA first: a 65-byte signature that recovers to the issuer address is the
  // common case. A wrong EOA signature is NOT sent to the chain (the authn
  // rule: every typo must not become an RPC call).
  const sigHex = typeof signature === "string" && signature.length === 130 + 2
    ? (signature.startsWith("0x") ? signature : "0x" + signature) : null;
  if (sigHex) {
    const recovered = recoverAddress(message, sigHex);
    if (recovered && lc(recovered) === pkh.address) return { ok: true, address: pkh.address, signer: "eoa", net };
    // A 65-byte signature that fails to recover is an EOA's wrong signature,
    // NOT a contract's — sending it to the chain would turn every typo into
    // an RPC call (authn.siwe's rule). ERC-1271 applies only to
    // non-65-byte (or non-EIP-191-shaped) signatures.
    return { ok: false, reason: "eoa-signature-mismatch" };
  }
  const code = await rpcCall(env, net, "eth_getCode", [pkh.address, "latest"]).catch(() => null);
  if (!code || code === "0x") {
    return { ok: false, reason: sigHex ? "eoa-signature-mismatch" : "no-code-and-not-65b-sig" };
  }
  const digest = keccak_256(enc.encode(message));
  const okSig = typeof signature === "string"
    ? await erc1271Valid(env, net, pkh.address, digest, signature.startsWith("0x") ? signature : "0x" + signature)
    : false;
  return okSig ? { ok: true, address: pkh.address, signer: "erc1271", net }
    : { ok: false, reason: "erc1271-invalid" };
}


// ---- x402 payment (transaction + exact schemes) ----

const MICRO = 1_000_000;
// Floor price for one paid object/ref read. ?usd= may raise it.
export const DEFAULT_USD = 0.001;

export function quotedUsd(declared, floor) {
  const d = Number.parseFloat(declared || "");
  const f = Number(floor ?? DEFAULT_USD);
  if (!Number.isFinite(d) || d <= 0) return f;
  return Math.max(d, f);
}

const usdToMicros = (usd) => BigInt(Math.ceil(usd * MICRO)).toString();

// One accepted payment option (mirrors pay.x402/payment-requirements).
export function requirement({ payTo, usd, resource, net, scheme, facilitator }) {
  const canonical = canonNet(net);
  const req = {
    scheme,
    network: canonical,
    maxAmountRequired: usdToMicros(usd),
    resource,
    description: "kotobase git read: " + resource,
    mimeType: "application/json",
    payTo,
    maxTimeoutSeconds: 60,
    asset: usdcFor(canonical),
  };
  if (scheme === "exact") {
    // EIP-712 domain for the USDC contract (pay.x402/eip712-domain-for:
    // measured on-chain 2026-09-01 — base mainnet "USD Coin"/2, sepolia "USDC"/2).
    req.extra = canonical === "base-sepolia"
      ? { name: "USDC", version: "2" }
      : { name: "USD Coin", version: "2" };
    if (facilitator) req.facilitator = facilitator;
  }
  return req;
}

// The 402 challenge body (pay.x402/challenge shape).
export function challenge(accepts, error) {
  return { x402Version: X402_VERSION, accepts, error: error || "" };
}

const b64decode = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")
  .padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0));

// Decode the X-PAYMENT header: base64(JSON {x402Version, scheme, network, payload}).
// Returns null on any malformed input.
export function decodePayment(header) {
  try {
    const j = JSON.parse(new TextDecoder().decode(b64decode(header)));
    if (typeof j !== "object" || !j || typeof j.scheme !== "string") return null;
    j.network = canonNet(j.network);
    return j;
  } catch (_) { return null; }
}

// Structural + economic validation (pay.x402/payload-errors equivalent).
// Returns [] when acceptable.
export function payloadErrors(payment, req, nowSec) {
  const errs = [];
  if (payment.scheme !== req.scheme) errs.push("scheme-mismatch");
  if (payment.network !== req.network) errs.push("network-mismatch");
  const p = payment.payload || {};
  if (req.scheme === "exact") {
    const auth = p.authorization || {};
    if (lc(auth.to) !== lc(req.payTo)) errs.push("wrong-recipient");
    const value = Number.parseInt(String(auth.value), 10);
    if (!Number.isFinite(value) || value < Number(req.maxAmountRequired)) errs.push("underpaid");
    if (auth.validBefore && Number.parseInt(auth.validBefore, 10) <= nowSec) errs.push("authorization-expired");
    if (auth.validAfter && Number.parseInt(auth.validAfter, 10) > nowSec) errs.push("authorization-not-yet-valid");
    if (typeof p.signature !== "string" || !p.signature) errs.push("missing-signature");
  } else if (req.scheme === "transaction") {
    if (typeof p.txHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(p.txHash)) errs.push("missing-tx-hash");
    if (typeof p.from !== "string" || !/^0x[0-9a-fA-F]{40}$/.test(p.from)) errs.push("missing-payer");
  }
  return errs;
}


// On-chain verification of a scheme=transaction payment: the USDC Transfer
// log to the treasury, amount >= required, >= MIN_CONFIRMATIONS deep, on a
// successful tx. Mirrors treasury.core/receipt->onchain + verify-payment.
// Returns { ok: true, payer, paidMicros } or { ok: false, reason }.
export async function verifyTxPayment(env, req, payment) {
  const net = req.network;
  const treasury = env.KOTOBASE_TREASURY_ADDR;
  if (!treasury) return { ok: false, reason: "treasury-not-configured" };
  const txHash = payment.payload.txHash;
  const payer = lc(payment.payload.from);
  const requiredMicros = BigInt(req.maxAmountRequired);
  let receipt, headHex;
  try {
    [receipt, headHex] = await Promise.all([
      rpcCall(env, net, "eth_getTransactionReceipt", [txHash]),
      rpcCall(env, net, "eth_blockNumber", []),
    ]);
  } catch (_) { return { ok: false, reason: "rpc-unavailable" }; }
  // A missing receipt (tx not yet mined / never existed) is a rejection —
  // never a pass.
  if (!receipt) return { ok: false, reason: "tx-not-found" };
  if (lc(receipt.status) !== "0x1") return { ok: false, reason: "tx-reverted" };
  const head = hexToLong(headHex);
  const txBlock = hexToLong(receipt.blockNumber);
  // NaN head (malformed eth_blockNumber) must NOT fold into a pass —
  // the gateway's measured bug, kept closed here too.
  if (head === null || txBlock === null) return { ok: false, reason: "bad-block-number" };
  const confirmations = head - txBlock + 1;
  if (confirmations < MIN_CONFIRMATIONS) return { ok: false, reason: "insufficient-confirmations" };
  const usdc = lc(usdcFor(net));
  const transfer = (receipt.logs || []).find((l) => l.address && lc(l.address) === usdc
    && Array.isArray(l.topics) && l.topics.length >= 3
    && lc(l.topics[0]) === TRANSFER_TOPIC);
  if (!transfer) return { ok: false, reason: "no-usdc-transfer" };
  const to = "0x" + lc(transfer.topics[2]).slice(-40);
  if (to !== lc(treasury)) return { ok: false, reason: "wrong-recipient" };
  const paidMicros = BigInt(hexToLong(transfer.data) ?? 0);
  if (paidMicros < requiredMicros) return { ok: false, reason: "underpaid" };
  return { ok: true, payer, paidMicros: paidMicros.toString(), txHash };
}

// Spend-dedupe: one tx hash pays exactly once, via the GIT_STORE KV
// namespace (same store the worker already uses for durable state).
// Reserves for `ttlHours` even if the caller crashes after allow.
export async function spendReserve(env, req, verification, ttlHours = 72) {
  const store = env.GIT_STORE;
  if (!store) return { allow: false, reason: "spend-store-unavailable" };
  // Dedupe key: the tx hash for scheme=transaction (exact settlements have
  // no reusable hash — each authorization settles once at the facilitator),
  // falling back to payer+amount.
  const k = "x402-spend:" + req.network + ":"
    + (verification.txHash || (verification.payer + ":" + verification.paidMicros));
  const existing = await store.get(k);
  if (existing) return { allow: false, reason: "tx-already-spent" };
  await store.put(k, JSON.stringify({ paidMicros: verification.paidMicros, payer: verification.payer, at: Date.now() }),
    { expirationTtl: Math.max(3600, ttlHours * 3600) });
  return { allow: true };
}

// Settle scheme=exact through the configured facilitator
// (mirrors kotobase.x402/settle-exact). Null when no facilitator configured.
export async function settleExact(env, payment, req) {
  const facilitator = env.KOTOBASE_X402_FACILITATOR;
  if (!facilitator) return null;
  const r = await fetch(facilitator.replace(/\/+$/, "") + "/settle", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ x402Version: X402_VERSION, paymentPayload: payment, paymentRequirements: req }),
  });
  const j = await r.json();
  const value = payment?.payload?.authorization?.value;
  return {
    included: Boolean(j.success),
    reason: j.errorReason || j.error || null,
    tx: j.transaction || null,
    payer: j.payer || payment?.payload?.authorization?.from || null,
    paidMicros: value != null && !Number.isNaN(Number.parseInt(value, 10)) ? String(value) : null,
    txHash: j.transaction || null,
  };
}

// The JSON 402 response.
export function paymentRequiredResponse(accepts, error) {
  return new Response(JSON.stringify(challenge(accepts, error), null, 2), {
    status: 402,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
