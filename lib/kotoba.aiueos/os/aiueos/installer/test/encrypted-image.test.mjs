import test from "node:test";
import assert from "node:assert/strict";
import { decryptBuffer, encryptBuffer, formatRecoveryKey, generateRecoveryKey, parseRecoveryKey } from "../encrypted-image.mjs";

const key = Buffer.from(Array.from({ length: 32 }, (_, i) => i));
const options = { chunkBytes: 4096, salt: Buffer.alloc(32, 0x41), noncePrefix: Buffer.alloc(8, 0x42) };
const plaintext = Buffer.concat([Buffer.alloc(4096, 0x61), Buffer.from("final chunk")]);

test("v1 format is deterministic with explicit test parameters and round trips", () => {
  const a = encryptBuffer(plaintext, key, options);
  const b = encryptBuffer(plaintext, key, options);
  assert.deepEqual(a, b);
  assert.deepEqual(decryptBuffer(a, key), plaintext);
});

test("fresh defaults produce unique salt/nonces", () => {
  assert.notDeepEqual(encryptBuffer(plaintext, key, { chunkBytes: 4096 }), encryptBuffer(plaintext, key, { chunkBytes: 4096 }));
});

test("wrong key fails closed", () => {
  const image = encryptBuffer(plaintext, key, options);
  assert.throws(() => decryptBuffer(image, Buffer.alloc(32, 9)), /wrong recovery key/);
});

test("metadata, ciphertext, tag, truncation, and trailing bytes are rejected", () => {
  const image = encryptBuffer(plaintext, key, options);
  for (const offset of [15, 300, image.length - 1]) {
    const tampered = Buffer.from(image); tampered[offset] ^= 1;
    assert.throws(() => decryptBuffer(tampered, key), /authentication|header|key verifier|format|geometry/);
  }
  assert.throws(() => decryptBuffer(image.subarray(0, image.length - 2), key), /truncated|invalid length/);
  assert.throws(() => decryptBuffer(Buffer.concat([image, Buffer.from([0])]), key), /trailing bytes/);
});

test("recovery key has a checked, versioned representation", () => {
  const text = formatRecoveryKey(key);
  assert.deepEqual(parseRecoveryKey(text), key);
  assert.match(generateRecoveryKey(), /^AIUEOS1-(?:[0-9A-F]{8}-){8}[0-9A-F]{8}$/);
  const replacement = text.endsWith("0") ? "1" : "0";
  assert.throws(() => parseRecoveryKey(`${text.slice(0, -1)}${replacement}`), /checksum mismatch/);
});
