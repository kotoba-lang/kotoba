// Regenerate test/kotoba/lang/pqh/vectors.edn -- the cross-language
// known-answer vectors the Clojure/CLJC port's test suite checks its
// Bouncy-Castle/kotoba-lang-ed25519/kotoba-lang-dag-cbor output against.
//
// Usage (from the repo root):
//   node scripts/gen-cross-lang-vectors.mjs > test/kotoba/lang/pqh/vectors.edn
//
// All random material is generated programmatically (node:crypto's
// randomBytes) -- never hand-typed hex literals -- to avoid transcription
// errors (see this repo's README "Clojure/CLJC port" section for why that
// matters here).
import { randomBytes as nodeRandomBytes } from 'node:crypto';
import { xchacha20poly1305, hchacha } from '@noble/ciphers/chacha';
import { argon2id } from '@noble/hashes/argon2';
import { ed25519 } from '@noble/curves/ed25519';
import { ml_kem768 } from '@noble/post-quantum/ml-kem.js';
import { ml_dsa65 } from '@noble/post-quantum/ml-dsa.js';
import { encode as cborEncode } from '@ipld/dag-cbor';

const hex = (b) => Buffer.from(b).toString('hex');
const rb = (n) => new Uint8Array(nodeRandomBytes(n));
const utf8 = (s) => new TextEncoder().encode(s);

const out = {};

// ---- XChaCha20-Poly1305 ----
{
  const key = rb(32);
  const nonce = rb(24);
  const aad = utf8('additional data');
  const plaintext = utf8("Ladies and Gentlemen of the class of '99: If I could offer you o");
  const ct = xchacha20poly1305(key, nonce, aad).encrypt(plaintext);
  // hchacha subkey (cross-check the HChaCha20 subkey-derivation step independently)
  const sigma32 = new Uint32Array(new TextEncoder().encode('expand 32-byte k').buffer);
  const k32 = new Uint32Array(key.buffer, key.byteOffset, 8);
  const n16 = new Uint32Array(nonce.slice(0, 16).buffer);
  const subkeyOut = new Uint32Array(8);
  hchacha(sigma32, k32, n16, subkeyOut);
  const subkeyBytes = new Uint8Array(subkeyOut.buffer);
  out.xchacha20poly1305 = {
    key: hex(key), nonce: hex(nonce), aad: hex(aad), plaintext: hex(plaintext),
    ciphertext: hex(ct), subkey: hex(subkeyBytes),
  };

  const key2 = rb(32);
  const nonce2 = rb(24);
  const ct2 = xchacha20poly1305(key2, nonce2).encrypt(new Uint8Array(0));
  out.xchacha20poly1305_empty = { key: hex(key2), nonce: hex(nonce2), ciphertext: hex(ct2) };

  const key3 = rb(32);
  const nonce3 = rb(24);
  const aad3 = rb(7);
  const plaintext3 = rb(51);
  const ct3 = xchacha20poly1305(key3, nonce3, aad3).encrypt(plaintext3);
  out.xchacha20poly1305_bin = {
    key: hex(key3), nonce: hex(nonce3), aad: hex(aad3), plaintext: hex(plaintext3), ciphertext: hex(ct3),
  };
}

// ---- Argon2id ----
{
  const pw = utf8('correct horse battery staple');
  const salt = rb(16);
  const params = { mKiB: 19456, t: 2, p: 1 };
  const key = argon2id(pw, salt, { m: params.mKiB, t: params.t, p: params.p, dkLen: 32 });
  out.argon2id = { password: hex(pw), salt: hex(salt), params, key: hex(key) };

  const params2 = { mKiB: 8192, t: 3, p: 1 };
  const pw2 = utf8('pw2');
  const key2 = argon2id(pw2, salt, { m: params2.mKiB, t: params2.t, p: params2.p, dkLen: 32 });
  out.argon2id_2 = { password: hex(pw2), salt: hex(salt), params: params2, key: hex(key2) };
}

// ---- Ed25519 (via kotoba-lang/ed25519's approach: seed -> pubkey -> sign/verify) ----
{
  const seed = rb(32);
  const pub = ed25519.getPublicKey(seed);
  const msg = utf8('');
  const sig = ed25519.sign(msg, seed);
  out.ed25519_vector1 = { seed: hex(seed), pub: hex(pub), msg: hex(msg), sig: hex(sig) };

  const seed2 = rb(32);
  const pub2 = ed25519.getPublicKey(seed2);
  const msg2 = utf8('canonical body bytes for pqh cross-check');
  const sig2 = ed25519.sign(msg2, seed2);
  out.ed25519_vector2 = { seed: hex(seed2), pub: hex(pub2), msg: hex(msg2), sig: hex(sig2) };
}

// ---- dag-cbor ----
{
  const body1 = { hello: 'world', n: 42, list: [1, 2, 3] };
  out.cbor_body1 = { encoded: hex(cborEncode(body1)) };
  const body2 = { x: 1 };
  out.cbor_body2 = { encoded: hex(cborEncode(body2)) };
  const body3 = {
    did: 'did:web:alice.example',
    signalIdentityKey: new Uint8Array(32).fill(0xab),
    signalRegistrationId: 4242,
    createdAt: '2026-05-18T11:00:00.000Z',
  };
  out.cbor_body3_signalIdentity = { encoded: hex(cborEncode(body3)) };
}

// ---- ML-KEM-768 ----
{
  const kp = ml_kem768.keygen();
  const msg = rb(32);
  const { cipherText, sharedSecret } = ml_kem768.encapsulate(kp.publicKey, msg);
  const derived = ml_kem768.decapsulate(cipherText, kp.secretKey);
  out.mlkem768 = {
    publicKey: hex(kp.publicKey), secretKey: hex(kp.secretKey),
    encapMsg: hex(msg), cipherText: hex(cipherText), sharedSecret: hex(sharedSecret),
    decapsulated: hex(derived),
  };
}

// ---- ML-DSA-65 ----
{
  const seed = rb(32);
  const kp = ml_dsa65.keygen(seed);
  const msg = utf8('canonical body bytes');
  const sig = ml_dsa65.sign(msg, kp.secretKey);
  const ok = ml_dsa65.verify(sig, msg, kp.publicKey);
  out.mldsa65 = {
    seed: hex(seed), publicKey: hex(kp.publicKey), secretKey: hex(kp.secretKey),
    msg: hex(msg), sig: hex(sig), verifies: ok,
  };
}

// ---- X25519 + HKDF-SHA256 (pq.ts's classical KEM component + combiner) ----
{
  const { x25519 } = await import('@noble/curves/ed25519');
  const { hkdf } = await import('@noble/hashes/hkdf');
  const { sha256 } = await import('@noble/hashes/sha256');

  const aSecret = x25519.utils.randomPrivateKey();
  const aPublic = x25519.getPublicKey(aSecret);
  const bSecret = x25519.utils.randomPrivateKey();
  const bPublic = x25519.getPublicKey(bSecret);
  const ssA = x25519.getSharedSecret(aSecret, bPublic);
  const ssB = x25519.getSharedSecret(bSecret, aPublic);
  out.x25519 = {
    aSecret: hex(aSecret), aPublic: hex(aPublic),
    bSecret: hex(bSecret), bPublic: hex(bPublic),
    sharedSecretAB: hex(ssA), sharedSecretBA: hex(ssB),
  };

  const ikm = rb(32);
  const salt = utf8('etzhayyim/pqh-v1/kem');
  const info = rb(40);
  const okm = hkdf(sha256, ikm, salt, info, 32);
  out.hkdf_sha256 = { ikm: hex(ikm), salt: hex(salt), info: hex(info), okm: hex(okm) };
}

// ---- emit EDN (not JSON) so it loads straight into clojure.edn/read-string ----
function ednVal(v) {
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') return JSON.stringify(v); // EDN strings == JSON strings (ASCII-safe here)
  if (v && typeof v === 'object') {
    const entries = Object.entries(v).map(([k, val]) => `:${k} ${ednVal(val)}`);
    return '{' + entries.join(' ') + '}';
  }
  throw new Error(`ednVal: unsupported value ${v}`);
}

const lines = ['{'];
for (const [k, v] of Object.entries(out)) {
  lines.push(` :${k}\n ${ednVal(v)}`);
}
lines.push('}');
console.log(lines.join('\n'));
