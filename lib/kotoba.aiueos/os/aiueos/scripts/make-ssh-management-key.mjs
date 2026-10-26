#!/usr/bin/env node

import { createHash, generateKeyPairSync } from "node:crypto";
import { mkdirSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const directory = process.argv[2];
if (!directory) {
  console.error("usage: make-ssh-management-key.mjs <private-directory>");
  process.exit(2);
}

const privatePath = join(directory, "management-p256.pem");
const publicPath = `${privatePath}.pub`;
const publicHexPath = `${privatePath}.public-hex`;
for (const path of [privatePath, publicPath, publicHexPath]) {
  if (existsSync(path)) {
    console.error(`refusing to overwrite existing management key: ${path}`);
    process.exit(3);
  }
}

mkdirSync(directory, { recursive: true, mode: 0o700 });
const { privateKey, publicKey } = generateKeyPairSync("ec", {
  namedCurve: "prime256v1",
});
const jwk = publicKey.export({ format: "jwk" });
const decode = (value) => Buffer.from(value, "base64url");
const x = decode(jwk.x);
const y = decode(jwk.y);
if (x.length !== 32 || y.length !== 32) {
  throw new Error("generated key is not a P-256 public point");
}

const sshString = (value) => {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(bytes.length);
  return Buffer.concat([length, bytes]);
};
const algorithm = "ecdsa-sha2-nistp256";
const blob = Buffer.concat([
  sshString(algorithm),
  sshString("nistp256"),
  sshString(Buffer.concat([Buffer.from([4]), x, y])),
]);
const publicLine = `${algorithm} ${blob.toString("base64")} aiueos-k16-management\n`;
const fingerprint = createHash("sha256").update(blob).digest("base64").replace(/=+$/, "");

writeFileSync(
  privatePath,
  privateKey.export({ type: "sec1", format: "pem" }),
  { mode: 0o600 },
);
writeFileSync(publicPath, publicLine, { mode: 0o644 });
writeFileSync(publicHexPath, `${Buffer.concat([x, y]).toString("hex")}\n`, { mode: 0o644 });
console.log(`private: ${privatePath}`);
console.log(`public: ${publicPath}`);
console.log(`build-public: ${publicHexPath}`);
console.log(`fingerprint: SHA256:${fingerprint}`);
