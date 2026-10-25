#!/usr/bin/env node
// Create a deterministic detached envelope for one public trust policy.
// Kagi access is exact-name only: callers supply --key once per known item;
// this script never lists or searches the vault.

import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";

function values(flag) {
  const found = [];
  for (let i = 0; i < process.argv.length - 1; i += 1) {
    if (process.argv[i] === flag) found.push(process.argv[i + 1]);
  }
  return found;
}

function value(flag) {
  return values(flag)[0];
}

const policyPath = value("--policy");
const outputPath = value("--output");
const kagiBin = value("--kagi-bin");
const keyNames = values("--key");

if (!policyPath || !outputPath || !kagiBin || keyNames.length < 2) {
  console.error("usage: sign-trust-policy.mjs --policy FILE --output FILE --kagi-bin FILE --key NAME --key NAME");
  process.exit(2);
}

const policyBytes = fs.readFileSync(policyPath);
const policyId = `urn:sha256:${crypto.createHash("sha256").update(policyBytes).digest("hex")}`;
const signedMessage = `kotoba-trust-policy-v1\n${policyId}`;

const signatures = keyNames.map((governanceKey) => {
  let pem;
  try {
    pem = execFileSync(kagiBin, ["get", governanceKey, "--compartment", "personal"], {
      encoding: "utf8",
      timeout: 120000,
      stdio: ["ignore", "pipe", "pipe"],
    }).trimEnd();
  } catch (error) {
    console.error(`exact kagi lookup failed for ${governanceKey}; no vault enumeration was attempted`);
    process.exit(2);
  }
  const privateKey = crypto.createPrivateKey(pem);
  const publicDer = crypto.createPublicKey(privateKey).export({ format: "der", type: "spki" });
  const publicKey = publicDer.subarray(publicDer.length - 32).toString("hex");
  return {
    keyId: `ed25519:${publicKey}`,
    governanceKey,
    publicKey,
    signature: crypto.sign(null, Buffer.from(signedMessage, "utf8"), privateKey).toString("base64"),
  };
}).sort((a, b) => a.keyId.localeCompare(b.keyId));

if (new Set(signatures.map(({ keyId }) => keyId)).size !== signatures.length) {
  console.error("refusing to write an envelope with duplicate signer keys");
  process.exit(2);
}

const envelope = {
  version: 1,
  policy: "murakumo-v1.json",
  policyId,
  signedMessage,
  algorithm: "Ed25519",
  threshold: 2,
  signatures,
  custodyNote: "Distinct governance keys under one operator custody; cryptographic quorum, not independent human review.",
};

fs.writeFileSync(outputPath, `${JSON.stringify(envelope, null, 2)}\n`, { flag: "w" });
console.log(`wrote ${outputPath}: ${signatures.length} distinct signatures for ${policyId}`);
