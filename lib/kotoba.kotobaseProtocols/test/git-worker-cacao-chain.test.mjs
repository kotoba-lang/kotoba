import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import { adminAuthorized, rawCid, verifyCacaoChain } from "../worker/git-worker.mjs";

const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function base58(bytes) {
  let n = 0n; for (const b of bytes) n = (n << 8n) + BigInt(b);
  let out = ""; while (n) { out = alphabet[Number(n % 58n)] + out; n /= 58n; }
  for (const b of bytes) { if (b) break; out = `1${out}`; } return out || "1";
}
function identity() {
  const pair = generateKeyPairSync("ed25519");
  const pub = pair.publicKey.export({ format: "der", type: "spki" }).subarray(-32);
  return { ...pair, did: `did:key:z${base58(Buffer.concat([Buffer.from([0xed, 1]), pub]))}` };
}
function head(major, n) {
  if (n < 24) return Buffer.from([(major << 5) + n]);
  if (n < 256) return Buffer.from([(major << 5) + 24, n]);
  return Buffer.from([(major << 5) + 25, n >> 8, n & 255]);
}
function cbor(value) {
  if (typeof value === "string") { const b = Buffer.from(value); return Buffer.concat([head(3, b.length), b]); }
  if (Array.isArray(value)) return Buffer.concat([head(4, value.length), ...value.map(cbor)]);
  const entries = Object.entries(value); return Buffer.concat([head(5, entries.length), ...entries.flatMap(([k, v]) => [cbor(k), cbor(v)])]);
}
function mint(issuer, audience, resources, nonce, expOffset = 3600000) {
  const now = new Date(); const payload = { iss: issuer.did, aud: audience, iat: now.toISOString(),
    nonce, domain: "git.kotobase.net", version: "1", resources,
    exp: new Date(now.getTime() + expOffset).toISOString() };
  const message = [`${payload.domain} wants you to sign in with your Ethereum account:`, issuer.did.split(":").at(-1), "",
    `URI: ${payload.aud}`, "Version: 1", "Chain ID: 1", `Nonce: ${payload.nonce}`,
    `Issued At: ${payload.iat}`, `Expiration Time: ${payload.exp}`, "Resources:", ...resources.map((r) => `- ${r}`)].join("\n");
  return cbor({ p: payload, s: { t: "EdDSA", s: sign(null, Buffer.from(message), issuer.privateKey).toString("base64url") } }).toString("base64");
}

test("owner to intermediate to signer chain narrows resource and verifies", async () => {
  const owner = identity(), mid = identity(), signer = identity();
  const wildcard = "kotoba-rad://urn:kotobase:git:org/repo/push/*";
  const wanted = "kotoba-rad://urn:kotobase:git:org/repo/push/refs/heads/main";
  const chain = [mint(owner, mid.did, [wildcard], "root-1", 7200000), mint(mid, signer.did, [wanted], "leaf-1")];
  const result = await verifyCacaoChain(chain, owner.did, signer.did, wanted);
  assert.equal(result.length, 2);
});

test("resource escalation, wrong holder and expiry are rejected", async () => {
  const owner = identity(), mid = identity(), signer = identity(), attacker = identity();
  const wanted = "kotoba-rad://urn:kotobase:git:org/repo/push/refs/heads/main";
  const other = "kotoba-rad://urn:kotobase:git:org/repo/push/refs/heads/dev";
  assert.equal(await verifyCacaoChain([mint(owner, mid.did, [wanted], "r2"), mint(mid, signer.did, [other], "l2")], owner.did, signer.did, wanted), null);
  assert.equal(await verifyCacaoChain([mint(owner, attacker.did, [wanted], "r3")], owner.did, signer.did, wanted), null);
  assert.equal(await verifyCacaoChain([mint(owner, signer.did, [wanted], "r4", -1000)], owner.did, signer.did, wanted), null);
});

test("canonical Git bytes receive a stable CIDv1 raw sha2-256 identity", async () => {
  const bytes = Buffer.from("blob 5\0hello");
  const cid = await rawCid(bytes);
  assert.match(cid, /^bafkre[a-z2-7]{50,}$/);
  assert.equal(cid, await rawCid(bytes));
  assert.notEqual(cid, await rawCid(Buffer.from("blob 6\0hello!")));
});

test("write bearer authorization fails closed and accepts only the configured token", async () => {
  assert.equal(await adminAuthorized(new Request("https://git.kotobase.net/xrpc/write"), {}), false);
  assert.equal(await adminAuthorized(new Request("https://git.kotobase.net/xrpc/write", {
    headers: { authorization: "Bearer wrong" },
  }), { ADMIN_TOKEN: "right" }), false);
  assert.equal(await adminAuthorized(new Request("https://git.kotobase.net/xrpc/write", {
    headers: { authorization: "Bearer right" },
  }), { ADMIN_TOKEN: "right" }), true);
});
