import { generateKeyPairSync } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const base = process.env.KOTOBASE_GIT_URL || "https://git.kotobase.net";
const repo = `fabric-witness/cli-${Date.now()}`;
const dir = mkdtempSync(join(tmpdir(), "kotobase-git-witness-"));
const { privateKey } = generateKeyPairSync("ed25519");
const key = privateKey.export({ format: "der", type: "pkcs8" }).toString("base64");
const quorumKeys = Array.from({ length: 2 }, () => generateKeyPairSync("ed25519").privateKey
  .export({ format: "der", type: "pkcs8" }).toString("base64"));
const helperDir = resolve("bin");
const receiptFile = join(dir, "push-receipt.json");
const env = { ...process.env, KOTOBASE_GIT_PRIVATE_KEY: key, KOTOBASE_GIT_QUORUM_KEYS: JSON.stringify(quorumKeys),
  KOTOBASE_GIT_TEST_QUORUM: "1", KOTOBASE_GIT_RECEIPT_FILE: receiptFile, PATH: `${helperDir}:${process.env.PATH}` };
const git = (...args) => execFileSync("git", args, { cwd: dir, env, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();

git("init", "-b", "main");
git("config", "user.name", "Kotobase Git Witness");
git("config", "user.email", "witness@kotobase.net");
git("remote", "add", "origin", `kotobase::${base}/${repo}`);
writeFileSync(join(dir, "witness.txt"), "first\n");
writeFileSync(join(dir, "test.mjs"), "import test from 'node:test'; import assert from 'node:assert/strict';\ntest('fabric witness', () => assert.equal(1 + 1, 2));\n");
git("add", "witness.txt"); git("commit", "-m", "first");
git("push", "origin", "main:refs/heads/main");
writeFileSync(join(dir, "witness.txt"), "first\nsecond\n");
git("add", "witness.txt"); git("commit", "-m", "second");
git("push", "origin", "main:refs/heads/main");
const sha = git("rev-parse", "HEAD");
git("reset", "--hard", "HEAD^");
let forceRejected = false;
try { git("push", "--force", "origin", "main:refs/heads/main"); }
catch (error) { forceRejected = String(error.stderr || "").includes("force/delete pushes are prohibited"); }
if (!forceRejected) throw new Error("bonsai force-push rejection was not observed");

let refsResponse;
let refs = "";
for (let attempt = 0; attempt < 8; attempt += 1) {
  refsResponse = await fetch(`${base}/${repo}/info/refs`);
  refs = await refsResponse.text();
  if (refsResponse.ok && refs.includes(`${sha}\trefs/heads/main`)) break;
  await new Promise((resolveDelay) => setTimeout(resolveDelay, 250 * (attempt + 1)));
}
if (!refsResponse?.ok || !refs.includes(`${sha}\trefs/heads/main`)) throw new Error(`remote ref mismatch: ${refsResponse?.status} ${refs}`);
const metadataResponse = await fetch(`${base}/xrpc/kotobase.git.ref.get?${new URLSearchParams({ repo, ref: "refs/heads/main" })}`);
const metadata = await metadataResponse.json();
if (!metadataResponse.ok || !metadata.kotobaseGraph?.startsWith("bafy") || !metadata.kotobaseCommit?.startsWith("bafy"))
  throw new Error(`Kotobase authority metadata missing: ${JSON.stringify(metadata)}`);
const receipt = JSON.parse(readFileSync(receiptFile, "utf8"));
let kaizen = null;
if (process.env.KAIZEN_RESULT_SECRET && receipt.eventId) {
  const workerScript = resolve("../../gftdcojp/cloud-murakumo/scripts/kaizen-fleet-worker.mjs");
  const eventUrl = `https://murakumo.cloud/api/kaizen/events/${receipt.eventId}`;
  kaizen = JSON.parse(execFileSync(process.execPath, [workerScript, eventUrl], { encoding: "utf8", env }).trim());
}
const witness = { ok: true, generatedAt: new Date().toISOString(), transport: "git-remote-kotobase", policy: "bonsai-fast-forward",
  authorization: "nekko-sigref+delegated-cacao-chain+2-of-2-quorum", storageAuthority: "kotobase-datom-graph", forceRejected, repo, sha,
  quorumRequired: receipt.quorumRequired, quorumSigners: receipt.quorumSigners,
  underQuorumRejected: receipt.underQuorumRejected, cacaoReplayRejected: receipt.cacaoReplayRejected,
  kotobaseGraph: metadata.kotobaseGraph, kotobaseCommit: metadata.kotobaseCommit, eventId: receipt.eventId, kaizen };
const witnessPath = resolve("../../../80-data/system/kotobase-git-witness.json");
writeFileSync(witnessPath, `${JSON.stringify(witness, null, 2)}\n`);
console.log(JSON.stringify(witness));
