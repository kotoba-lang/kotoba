#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";

const FORMAT = "kotoba-kcm-provider-release/v1";
const INSTALL_FORMAT = "kotoba-kcm-provider-install/v1";
const TRUSTED_SIGNER = "did:key:z6MknAaLaoj8doPeDrPgszg199YG8kZreH2D3UrWAmLcwgYM";

const argv = process.argv.slice(2);
const opt = (flag, fallback = undefined) => {
  const i = argv.indexOf(flag);
  return i >= 0 ? argv[i + 1] : fallback;
};
const fail = (message) => {
  throw new Error(message);
};

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

function canonicalJson(value) {
  return JSON.stringify(canonical(value));
}

function b58decode(text) {
  const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let value = 0n;
  for (const ch of text) {
    const digit = alphabet.indexOf(ch);
    if (digit < 0) fail("invalid did:key base58 character");
    value = value * 58n + BigInt(digit);
  }
  let hex = value.toString(16);
  if (hex.length % 2) hex = `0${hex}`;
  let bytes = hex ? Buffer.from(hex, "hex") : Buffer.alloc(0);
  const zeros = text.match(/^1*/)?.[0].length ?? 0;
  if (zeros) bytes = Buffer.concat([Buffer.alloc(zeros), bytes]);
  return bytes;
}

function publicKeyFromDid(did) {
  if (!did.startsWith("did:key:z")) fail("release signer is not did:key:z");
  const decoded = b58decode(did.slice("did:key:z".length));
  if (decoded.length !== 34 || decoded[0] !== 0xed || decoded[1] !== 0x01) {
    fail("release signer is not an Ed25519 did:key");
  }
  return crypto.createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: decoded.subarray(2).toString("base64url") },
    format: "jwk",
  });
}

export function verifyDescriptor(descriptor, trustedSigner = TRUSTED_SIGNER) {
  if (descriptor.format !== FORMAT) fail(`unsupported descriptor format: ${descriptor.format}`);
  if (descriptor.signer !== trustedSigner) fail(`untrusted provider signer: ${descriptor.signer}`);
  const signature = descriptor.signature;
  if (typeof signature !== "string" || !/^[0-9a-f]{128}$/.test(signature)) {
    fail("invalid provider descriptor signature encoding");
  }
  const body = { ...descriptor };
  delete body.signature;
  if (!crypto.verify(null, Buffer.from(canonicalJson(body)), publicKeyFromDid(descriptor.signer),
                     Buffer.from(signature, "hex"))) {
    fail("provider descriptor signature verification failed");
  }
  const platform = `${process.platform}-${process.arch}`;
  if (descriptor.platform !== platform) {
    fail(`provider platform mismatch: need ${descriptor.platform}, host is ${platform}`);
  }
  return descriptor;
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function readResource(location, redirects = 0) {
  if (/^https:\/\//.test(location)) {
    if (redirects > 5) fail("too many HTTPS redirects");
    const response = await fetch(location, { redirect: "manual" });
    if (response.status >= 300 && response.status < 400) {
      const next = response.headers.get("location");
      if (!next) fail("HTTPS redirect had no location");
      const resolved = new URL(next, location);
      if (resolved.protocol !== "https:") fail("provider redirect downgraded from HTTPS");
      return readResource(resolved.toString(), redirects + 1);
    }
    if (!response.ok) fail(`download failed ${response.status}: ${location}`);
    return Buffer.from(await response.arrayBuffer());
  }
  if (/^[a-z]+:/i.test(location)) fail(`unsupported provider URL scheme: ${location}`);
  return fs.readFileSync(path.resolve(location));
}

async function fetchAsset(asset, destination) {
  if (!asset || typeof asset.url !== "string" || typeof asset.sha256 !== "string") {
    fail("release descriptor has an invalid asset");
  }
  const bytes = await readResource(asset.url);
  if (bytes.length !== asset.bytes) fail(`asset size mismatch: ${asset.name}`);
  if (sha256(bytes) !== asset.sha256) fail(`asset digest mismatch: ${asset.name}`);
  fs.writeFileSync(destination, bytes, { mode: 0o644 });
}

function safeExtract(archive, destination) {
  const listed = spawnSync("tar", ["tf", archive], { encoding: "utf8" });
  if (listed.status !== 0) fail(`cannot list provider archive: ${listed.stderr}`);
  for (const entry of listed.stdout.split("\n").filter(Boolean)) {
    const clean = entry.replace(/^\.\//, "");
    const parts = clean.split("/").filter(Boolean);
    if (path.isAbsolute(clean) || parts.includes("..")) fail(`unsafe archive entry: ${entry}`);
  }
  const detailed = spawnSync("tar", ["tvf", archive], { encoding: "utf8" });
  if (detailed.status !== 0) fail(`cannot inspect provider archive: ${detailed.stderr}`);
  for (const entry of detailed.stdout.split("\n").filter(Boolean)) {
    if (!"-d".includes(entry[0])) fail(`provider archive contains a link or special entry: ${entry}`);
  }
  fs.mkdirSync(destination, { recursive: true, mode: 0o755 });
  const extracted = spawnSync("tar", ["xf", archive, "-C", destination], { encoding: "utf8" });
  if (extracted.status !== 0) fail(`cannot extract provider archive: ${extracted.stderr}`);
}

function shellQuote(value) {
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

function launcherSource(root, script, injected = []) {
  const words = injected.map((word) => shellQuote(word)).join(" ");
  return `#!/bin/sh\n` +
    `root=${shellQuote(root)}\n` +
    `exec "$root/current/runtime/runtime/bin/node" --stack-size=4096 ` +
    `"$root/current/runtime/node_modules/nbb/cli.js" --classpath ` +
    `"$root/current/runtime/runner/hosts/nbb" ` +
    `"$root/current/runtime/runner/bin/${script}"${words ? ` ${words}` : ""} "$@"\n`;
}

async function main() {
  if (argv.includes("--help") || argv.includes("-h")) {
    console.log("usage: node install-kcm-provider.mjs --descriptor URL_OR_FILE [--install DIR]");
    return;
  }
  const descriptorLocation = opt("--descriptor");
  if (!descriptorLocation) fail("missing --descriptor");
  const root = path.resolve(opt("--install", path.join(os.homedir(), ".local", "share", "kotoba-kcm")));
  const descriptor = verifyDescriptor(JSON.parse((await readResource(descriptorLocation)).toString("utf8")));
  const closure = descriptor.provider.providerClosureSha256;
  if (!/^[0-9a-f]{64}$/.test(closure)) fail("invalid provider closure digest");
  const releaseName = `${descriptor.version}-${descriptor.platform}-${closure.slice(0, 12)}`;
  fs.mkdirSync(root, { recursive: true, mode: 0o755 });
  const target = path.join(root, "releases", releaseName);
  const staging = path.join(root, `.${releaseName}.staging-${process.pid}`);
  fs.rmSync(staging, { recursive: true, force: true });
  fs.mkdirSync(staging, { recursive: true, mode: 0o755 });
  try {
    const archive = path.join(staging, descriptor.assets.archive.name);
    const manifest = path.join(staging, descriptor.assets.manifest.name);
    await fetchAsset(descriptor.assets.archive, archive);
    await fetchAsset(descriptor.assets.manifest, manifest);
    const runtimeRoot = path.join(staging, "runtime");
    safeExtract(archive, runtimeRoot);
    const bundledNode = path.join(runtimeRoot, "runtime", "bin", "node");
    if (!fs.existsSync(bundledNode)) fail("provider has no bundled Node runtime");
    if (sha256(fs.readFileSync(bundledNode)) !== descriptor.provider.runtimeSha256) {
      fail("bundled Node runtime digest does not match the signed release descriptor");
    }
    fs.chmodSync(bundledNode, 0o755);
    const keyDir = path.join(root, "keys");
    const receiptKey = path.join(keyDir, "pilot-receipt-ed25519.pem");
    fs.mkdirSync(keyDir, { recursive: true, mode: 0o700 });
    if (!fs.existsSync(receiptKey)) {
      const { privateKey } = crypto.generateKeyPairSync("ed25519");
      fs.writeFileSync(receiptKey,
        privateKey.export({ format: "pem", type: "pkcs8" }),
        { mode: 0o600, flag: "wx" });
    }
    fs.chmodSync(receiptKey, 0o600);
    const installed = {
      format: INSTALL_FORMAT,
      version: descriptor.version,
      platform: descriptor.platform,
      signer: descriptor.signer,
      "runtime-root": path.join(target, "runtime"),
      "receipt-key": receiptKey,
      provider: {
        archive: path.join(target, descriptor.assets.archive.name),
        manifest: path.join(target, descriptor.assets.manifest.name),
        "archive-sha256": descriptor.assets.archive.sha256,
        "provider-closure-sha256": descriptor.provider.providerClosureSha256,
        "compiler-cid": descriptor.provider.compilerCid,
        "module-lock-cid": descriptor.provider.moduleLockCid,
        "runtime-sha256": descriptor.provider.runtimeSha256,
        files: descriptor.provider.files,
        bytes: descriptor.provider.bytes,
      },
    };
    fs.writeFileSync(path.join(staging, "install.json"), `${JSON.stringify(installed, null, 2)}\n`);
    if (fs.existsSync(target)) {
      const existing = JSON.parse(fs.readFileSync(path.join(target, "install.json"), "utf8"));
      if (existing.provider["archive-sha256"] !== descriptor.assets.archive.sha256) {
        fail(`immutable provider release already exists with different bytes: ${target}`);
      }
      fs.rmSync(staging, { recursive: true, force: true });
    } else {
      fs.mkdirSync(path.dirname(target), { recursive: true, mode: 0o755 });
      fs.renameSync(staging, target);
    }
    const current = fs.readFileSync(path.join(target, "install.json"));
    const currentTmp = path.join(root, `.current-${process.pid}.json`);
    fs.writeFileSync(currentTmp, current, { mode: 0o644 });
    fs.renameSync(currentTmp, path.join(root, "current.json"));
    const currentLinkTmp = path.join(root, `.current-${process.pid}`);
    fs.rmSync(currentLinkTmp, { recursive: true, force: true });
    fs.symlinkSync(path.join("releases", releaseName), currentLinkTmp, "dir");
    fs.renameSync(currentLinkTmp, path.join(root, "current"));
    fs.mkdirSync(path.join(root, "bin"), { recursive: true, mode: 0o755 });
    const launchers = {
      "kcm-evaluate": launcherSource(root, "kcm-evaluate.cljs",
                                      ["--provider", path.join(root, "current", "install.json")]),
      "kcm-verify": launcherSource(root, "kcm-verify.cljs"),
    };
    for (const [name, source] of Object.entries(launchers)) {
      const launcher = path.join(root, "bin", name);
      const launcherTmp = path.join(root, "bin", `.${name}-${process.pid}`);
      fs.writeFileSync(launcherTmp, source, { mode: 0o755 });
      fs.renameSync(launcherTmp, launcher);
    }
    const launcher = path.join(root, "bin", "kcm-evaluate");
    console.log(JSON.stringify({ status: "installed", root, release: releaseName,
                                launcher, verifier: path.join(root, "bin", "kcm-verify"),
                                signer: descriptor.signer,
                                providerClosureSha256: closure }));
  } catch (error) {
    fs.rmSync(staging, { recursive: true, force: true });
    throw error;
  }
}

if (process.argv[1] === "-" ||
    path.resolve(process.argv[1] ?? "") === path.resolve(new URL(import.meta.url).pathname)) {
  main().catch((error) => {
    console.error(JSON.stringify({ status: "rejected", reason: error.message }));
    process.exitCode = 2;
  });
}

export { canonicalJson, TRUSTED_SIGNER };
