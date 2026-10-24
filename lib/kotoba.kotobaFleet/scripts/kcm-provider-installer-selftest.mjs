#!/usr/bin/env node
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { canonicalJson, verifyDescriptor } from "./install-kcm-provider.mjs";

function b58encode(bytes) {
  const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let value = BigInt(`0x${bytes.toString("hex")}`);
  let out = "";
  while (value > 0n) {
    out = alphabet[Number(value % 58n)] + out;
    value /= 58n;
  }
  for (const byte of bytes) {
    if (byte !== 0) break;
    out = `1${out}`;
  }
  return out;
}

const { privateKey, publicKey } = crypto.generateKeyPairSync("ed25519");
const raw = Buffer.from(publicKey.export({ format: "jwk" }).x, "base64url");
const did = `did:key:z${b58encode(Buffer.concat([Buffer.from([0xed, 0x01]), raw]))}`;
const body = {
  format: "kotoba-kcm-provider-release/v1",
  version: "test",
  platform: `${process.platform}-${process.arch}`,
  provider: {
    compilerCid: "git:test",
    moduleLockCid: "sha256:test",
    providerClosureSha256: "a".repeat(64),
    runtimeSha256: "b".repeat(64),
    files: 1,
    bytes: 1,
  },
  assets: {
    archive: { name: "provider.tar", url: "/tmp/provider.tar", sha256: "c".repeat(64), bytes: 1 },
    manifest: { name: "provider.edn", url: "/tmp/provider.edn", sha256: "d".repeat(64), bytes: 1 },
  },
  signer: did,
};
const descriptor = {
  ...body,
  signature: crypto.sign(null, Buffer.from(canonicalJson(body)), privateKey).toString("hex"),
};

assert.equal(verifyDescriptor(descriptor, did), descriptor);
assert.throws(() => verifyDescriptor({ ...descriptor, version: "tampered" }, did),
              /signature verification failed/);
assert.throws(() => verifyDescriptor(descriptor, "did:key:zOTHER"), /untrusted provider signer/);
assert.throws(() => verifyDescriptor({ ...descriptor, signature: "00" }, did),
              /invalid provider descriptor signature encoding/);
console.log("KCM provider installer signature selftest PASSED (4 checks)");
