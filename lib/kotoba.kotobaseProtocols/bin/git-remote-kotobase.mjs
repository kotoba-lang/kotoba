#!/usr/bin/env node
import { createHash, createPrivateKey, createPublicKey, randomUUID, sign } from "node:crypto";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

const fetchTimeoutMs = Math.max(1000, Number(process.env.KOTOBASE_GIT_FETCH_TIMEOUT_MS || "30000"));
function fetchBounded(url, init = {}) {
  return fetch(url, { ...init, signal: init.signal || AbortSignal.timeout(fetchTimeoutMs) });
}

process.stdout.on("error", (error) => {
  if (error.code === "EPIPE") process.exit(0);
  throw error;
});

const remoteName = process.argv[2];
const inputUrl = process.argv[3] || "";
const parsed = new URL(inputUrl.replace(/^kotobase::/, "").replace(/^kotobase:\/\//, "https://"));
const repo = parsed.pathname.replace(/^\/+|\/+$/g, "").replace(/\.git$/, "");
if (!/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repo)) throw new Error(`invalid kotobase repo: ${repo}`);
const base = `${parsed.protocol}//${parsed.host}`;

const privateMaterial = process.env.KOTOBASE_GIT_PRIVATE_KEY || "";
if (!privateMaterial) throw new Error("KOTOBASE_GIT_PRIVATE_KEY must contain an Ed25519 PKCS8 PEM or base64 DER key");
const privateKey = privateMaterial.includes("BEGIN PRIVATE KEY")
  ? createPrivateKey(privateMaterial.replace(/\\n/g, "\n"))
  : createPrivateKey({ key: Buffer.from(privateMaterial, "base64"), format: "der", type: "pkcs8" });
const publicKey = createPublicKey(privateKey);
const pub = publicKey.export({ format: "der", type: "spki" }).subarray(-32);
const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function base58(bytes) {
  let n = 0n;
  for (const b of bytes) n = (n << 8n) + BigInt(b);
  let out = "";
  while (n > 0n) { out = alphabet[Number(n % 58n)] + out; n /= 58n; }
  for (const b of bytes) { if (b !== 0) break; out = `1${out}`; }
  return out || "1";
}
const did = `did:key:z${base58(Buffer.concat([Buffer.from([0xed, 0x01]), pub]))}`;
const b64url = (x) => Buffer.from(x).toString("base64url");
const git = (...args) => execFileSync("git", args, { encoding: "utf8" }).trim();
function identityFromMaterial(material) {
  const key = material.includes("BEGIN PRIVATE KEY") ? createPrivateKey(material.replace(/\\n/g, "\n"))
    : createPrivateKey({ key: Buffer.from(material, "base64"), format: "der", type: "pkcs8" });
  const rawPublic = createPublicKey(key).export({ format: "der", type: "spki" }).subarray(-32);
  return { privateKey: key, pub: rawPublic,
    did: `did:key:z${base58(Buffer.concat([Buffer.from([0xed, 0x01]), rawPublic]))}` };
}
const quorumIdentities = JSON.parse(process.env.KOTOBASE_GIT_QUORUM_KEYS || "[]").map(identityFromMaterial);

function cborText(value) {
  const bytes = Buffer.from(value);
  if (bytes.length < 24) return Buffer.concat([Buffer.from([0x60 + bytes.length]), bytes]);
  if (bytes.length < 256) return Buffer.concat([Buffer.from([0x78, bytes.length]), bytes]);
  return Buffer.concat([Buffer.from([0x79, bytes.length >> 8, bytes.length & 255]), bytes]);
}
function sigrefPayload(value) {
  const entries = ["rid", "ref", "commit", "ts"].map((key) => [cborText(key), cborText(value[key])]);
  entries.sort((a, b) => a[0].length - b[0].length || Buffer.compare(a[0], b[0]));
  return Buffer.concat([Buffer.from([0xa4]), ...entries.flat()]);
}
function cborHead(major, length) {
  if (length < 24) return Buffer.from([(major << 5) + length]);
  if (length < 256) return Buffer.from([(major << 5) + 24, length]);
  if (length < 65536) return Buffer.from([(major << 5) + 25, length >> 8, length & 255]);
  throw new Error(`CBOR value too large: ${length}`);
}
function cbor(value) {
  if (typeof value === "string") { const bytes = Buffer.from(value); return Buffer.concat([cborHead(3, bytes.length), bytes]); }
  if (Array.isArray(value)) return Buffer.concat([cborHead(4, value.length), ...value.map(cbor)]);
  if (value && typeof value === "object") return Buffer.concat([cborHead(5, Object.keys(value).length), ...Object.entries(value).flatMap(([k, v]) => [cbor(k), cbor(v)])]);
  return cbor(String(value));
}
function base32(bytes) {
  const chars = "abcdefghijklmnopqrstuvwxyz234567";
  let bits = 0; let value = 0; let out = "";
  for (const byte of bytes) {
    value = (value << 8) | byte; bits += 8;
    while (bits >= 5) { out += chars[(value >>> (bits - 5)) & 31]; bits -= 5; }
  }
  if (bits > 0) out += chars[(value << (5 - bits)) & 31];
  return out;
}
function kotobaseGraph() {
  const digest = createHash("sha256").update(`kotobase/db/${did}/git`).digest();
  return `b${base32(Buffer.concat([Buffer.from([0x01, 0x71, 0x12, 0x20]), digest]))}`;
}
function mintCacao() {
  const iat = new Date(); const exp = new Date(iat.getTime() + 3600000);
  const payload = { iss: did, aud: "did:web:kotobase.net", iat: iat.toISOString(), nonce: `git-kotobase-${randomUUID()}`,
    domain: "kotobase.net", version: "1", resources: ["kotoba://can/kotobase:pin"], exp: exp.toISOString() };
  const address = did.split(":").at(-1);
  const message = [`${payload.domain} wants you to sign in with your Ethereum account:`, address, "",
    `URI: ${payload.aud}`, `Version: ${payload.version}`, "Chain ID: 1", `Nonce: ${payload.nonce}`,
    `Issued At: ${payload.iat}`, `Expiration Time: ${payload.exp}`, "Resources:", ...payload.resources.map((r) => `- ${r}`)].join("\n");
  const wire = { p: payload, s: { t: "EdDSA", s: b64url(sign(null, Buffer.from(message), privateKey)) } };
  return cbor(wire).toString("base64");
}
function mintDelegationCacao(audience, resource) {
  const iat = new Date(); const exp = new Date(iat.getTime() + 3600000);
  const payload = { iss: did, aud: audience, iat: iat.toISOString(), nonce: `git-delegate-${randomUUID()}`,
    domain: "git.kotobase.net", version: "1", resources: [resource], exp: exp.toISOString() };
  const message = [`${payload.domain} wants you to sign in with your Ethereum account:`, did.split(":").at(-1), "",
    `URI: ${payload.aud}`, "Version: 1", "Chain ID: 1", `Nonce: ${payload.nonce}`,
    `Issued At: ${payload.iat}`, `Expiration Time: ${payload.exp}`, "Resources:", `- ${resource}`].join("\n");
  return cbor({ p: payload, s: { t: "EdDSA", s: b64url(sign(null, Buffer.from(message), privateKey)) } }).toString("base64");
}
function makeSigref(ref, sha, identity = { did, privateKey }) {
  const value = { rid: `urn:kotobase:git:${repo}`, ref, commit: `git:sha1:${sha}`, ts: new Date().toISOString(), signer: identity.did };
  value.sig = sign(null, sigrefPayload(value), identity.privateKey).toString("hex");
  return value;
}
async function signedPut(path, body = Buffer.alloc(0), sigref = null, projection = null, approvals = null) {
  const url = new URL(path, base);
  const timestamp = new Date().toISOString();
  const nonce = randomUUID();
  const bodyHash = createHash("sha256").update(body).digest("hex");
  const sigrefHeader = sigref ? b64url(JSON.stringify(sigref)) : "";
  const projectionGraph = projection?.graph || "";
  const projectionCommit = projection?.commitCid || "";
  const cacaoValue = projection?.cacao || "";
  const cacaoHash = createHash("sha256").update(cacaoValue).digest("hex");
  const approvalsHeader = approvals ? b64url(JSON.stringify(approvals)) : "";
  const approvalSuffix = approvalsHeader ? `\n${createHash("sha256").update(approvalsHeader).digest("hex")}` : "";
  const authorizationHash = createHash("sha256").update(`${sigrefHeader}\n${projectionGraph}\n${projectionCommit}\n${cacaoHash}${approvalSuffix}`).digest("hex");
  const message = `PUT\n${url.pathname}${url.search}\n${bodyHash}\n${timestamp}\n${nonce}\n${authorizationHash}`;
  const headers = {
    "x-nekko-did": did, "x-nekko-public-key": b64url(pub),
    "x-nekko-signature": b64url(sign(null, Buffer.from(message), privateKey)),
    "x-nekko-timestamp": timestamp, "x-nekko-nonce": nonce, "x-nekko-authorization-hash": authorizationHash,
  };
  if (process.env.KOTOBASE_GIT_TOKEN)
    headers.authorization = `Bearer ${process.env.KOTOBASE_GIT_TOKEN}`;
  if (sigref) headers["x-nekko-sigref"] = sigrefHeader;
  if (approvalsHeader) headers["x-nekko-approvals"] = approvalsHeader;
  if (projection) {
    headers["x-kotobase-graph"] = projection.graph;
    headers["x-kotobase-commit-cid"] = projection.commitCid;
    headers["x-kotobase-cacao"] = projection.cacao;
  }
  return fetch(url, { method: "PUT", body, headers });
}
let quorumConfigured = false;
async function configureQuorum() {
  if (quorumConfigured || quorumIdentities.length === 0) return;
  for (const identity of quorumIdentities) {
    const response = await signedPut(`/xrpc/kotobase.git.delegate.set?${new URLSearchParams({ repo, did: identity.did })}`);
    if (!response.ok) throw new Error(`delegate set: HTTP ${response.status} ${await response.text()}`);
  }
  const minimum = quorumIdentities.length;
  const response = await signedPut(`/xrpc/kotobase.git.quorum.set?${new URLSearchParams({ repo, min: String(minimum) })}`);
  if (!response.ok) throw new Error(`quorum set: HTTP ${response.status} ${await response.text()}`);
  quorumConfigured = true;
}
async function remoteRefs() {
  const response = await fetch(`${base}/${repo}/info/refs`);
  if (response.status === 404) return new Map();
  if (!response.ok) throw new Error(`list failed: HTTP ${response.status}`);
  return new Map((await response.text()).trim().split("\n").filter(Boolean).map((line) => line.split("\t").reverse()));
}
async function refMetadata(ref) {
  const params = new URLSearchParams({ repo, ref });
  const response = await fetch(`${base}/xrpc/kotobase.git.ref.get?${params}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`ref metadata failed: HTTP ${response.status}`);
  return response.json();
}
const ednString = (value) => JSON.stringify(value);
async function projectRef(ref, sha, sigref, expectedParent) {
  const graph = kotobaseGraph();
  const id = `${repo}#${ref}`;
  const schema = [
    [":git.ref/id", ":db.type/string", ":db.unique/identity"], [":git.ref/repo", ":db.type/string"],
    [":git.ref/name", ":db.type/string"], [":git.ref/sha", ":db.type/string"],
    [":git.ref/signer", ":db.type/string"], [":git.ref/sigref", ":db.type/string"],
    [":git.ref/updated-at", ":db.type/string"],
  ].flatMap(([attr, type, unique]) => {
    const eid = ednString(`schema:${attr}`);
    const rows = [`[:db/add ${eid} :db/ident ${attr}]`, `[:db/add ${eid} :db/valueType ${type}]`, `[:db/add ${eid} :db/cardinality :db.cardinality/one]`];
    if (unique) rows.push(`[:db/add ${eid} :db/unique ${unique}]`);
    return rows;
  });
  const entity = [ `:db/add ${ednString(`git.ref:${id}`)} :git.ref/id ${ednString(id)}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/repo ${ednString(repo)}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/name ${ednString(ref)}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/sha ${ednString(sha)}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/signer ${ednString(did)}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/sigref ${ednString(JSON.stringify(sigref))}`,
    `:db/add [:git.ref/id ${ednString(id)}] :git.ref/updated-at ${ednString(new Date().toISOString())}`]
    .map((x) => `[${x}]`);
  const cacao = mintCacao();
  const body = { graph, db_name: "git", tx_edn: `[${[...schema, ...entity].join(" ")}]`, cacao_b64: cacao, tenant_did: did };
  if (expectedParent) body.expected_parent = expectedParent;
  const response = await fetch(`${process.env.KOTOBASE_URL || "https://kotobase.net"}/xrpc/ai.gftd.apps.kotobase.datomic.transact`, {
    method: "POST", headers: { "content-type": "application/json", "accept": "application/json", authorization: `CACAO ${cacao}`, "x-kotoba-did": did },
    body: JSON.stringify(body),
  });
  const responseText = await response.text();
  if (!response.ok) throw new Error(`Kotobase transact: HTTP ${response.status} ${responseText}`);
  const result = JSON.parse(responseText);
  const commitCid = result.commit_cid || result.commit;
  if (!commitCid) throw new Error(`Kotobase transact returned no commit CID: ${responseText}`);
  if (result.graph !== graph) throw new Error(`Kotobase graph mismatch: expected ${graph}, received ${result.graph}`);
  const readback = await fetch(`${process.env.KOTOBASE_URL || "https://kotobase.net"}/xrpc/ai.gftd.apps.kotobase.datomic.datoms`, {
    method: "POST", headers: { "content-type": "application/json", "accept": "application/json", authorization: `CACAO ${cacao}`, "x-kotoba-did": did },
    body: JSON.stringify({ graph, index: ":avet", components_edn: [":git.ref/sigref"], cacao_b64: cacao }),
  });
  const readbackText = await readback.text();
  if (!readback.ok || !readbackText.includes(sha) || !readbackText.includes(sigref.sig))
    throw new Error(`Kotobase projection readback failed: HTTP ${readback.status} ${readbackText}`);
  return { graph, commitCid, cacao };
}
function objectRaw(sha) {
  const type = git("cat-file", "-t", sha);
  const body = execFileSync("git", ["cat-file", type, sha]);
  return { type, raw: Buffer.concat([Buffer.from(`${type} ${body.length}\0`), body]), body };
}
async function push(spec) {
  const force = spec.startsWith("+");
  const [source, ref] = (force ? spec.slice(1) : spec).split(":");
  if (!source || !ref || force) throw new Error("force/delete pushes are prohibited by bonsai fast-forward policy");
  const sha = git("rev-parse", source);
  const refs = await remoteRefs();
  const old = refs.get(ref) || "";
  const priorMetadata = await refMetadata(ref);
  const objectIds = git("rev-list", "--objects", sha).split("\n").filter(Boolean).map((line) => line.split(" ")[0]);
  for (const oid of [...new Set(objectIds)]) {
    const { type, raw, body } = objectRaw(oid);
    const params = new URLSearchParams({ repo, sha: oid });
    if (type === "commit") for (const line of body.toString("utf8").split("\n")) if (line.startsWith("parent ")) params.append("parent", line.slice(7));
    const response = await signedPut(`/xrpc/kotobase.git.object.put?${params}`, raw);
    if (response.status !== 201) throw new Error(`object ${oid}: HTTP ${response.status} ${await response.text()}`);
  }
  const params = new URLSearchParams({ repo, ref, sha });
  if (old) params.set("old", old);
  const sigref = makeSigref(ref, sha);
  const projection = await projectRef(ref, sha, sigref, priorMetadata?.kotobaseCommit);
  await configureQuorum();
  const resource = `kotoba-rad://urn:kotobase:git:${repo}/push/${ref}`;
  const approvals = quorumIdentities.length ? quorumIdentities.map((identity) => ({
    sigref: makeSigref(ref, sha, identity), publicKey: b64url(identity.pub),
    chain: [mintDelegationCacao(identity.did, resource)],
  })) : null;
  let underQuorumRejected = null;
  if (process.env.KOTOBASE_GIT_TEST_QUORUM === "1" && approvals?.length > 1) {
    const negative = await signedPut(`/xrpc/kotobase.git.ref.set?${params}`, Buffer.alloc(0), sigref, projection, approvals.slice(0, -1));
    const detail = await negative.json();
    underQuorumRejected = negative.status === 403 && detail.error === "QuorumNotReached";
    if (!underQuorumRejected) throw new Error(`under-quorum negative witness failed: HTTP ${negative.status} ${JSON.stringify(detail)}`);
  }
  const response = await signedPut(`/xrpc/kotobase.git.ref.set?${params}`, Buffer.alloc(0), sigref, projection, approvals);
  if (!response.ok) throw new Error(`ref ${ref}: HTTP ${response.status} ${await response.text()}`);
  const receipt = await response.json();
  let replayRejected = null;
  if (process.env.KOTOBASE_GIT_TEST_QUORUM === "1" && approvals?.length) {
    const replay = await signedPut(`/xrpc/kotobase.git.ref.set?${params}`, Buffer.alloc(0), sigref, projection, approvals);
    const detail = await replay.json();
    replayRejected = replay.status === 403 && detail.error === "CacaoChainReplay";
    if (!replayRejected) throw new Error(`CACAO replay negative witness failed: HTTP ${replay.status} ${JSON.stringify(detail)}`);
  }
  receipt.underQuorumRejected = underQuorumRejected;
  receipt.cacaoReplayRejected = replayRejected;
  if (process.env.KOTOBASE_GIT_RECEIPT_FILE)
    writeFileSync(process.env.KOTOBASE_GIT_RECEIPT_FILE, `${JSON.stringify(receipt, null, 2)}\n`, { mode: 0o600 });
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  if (line === "capabilities") { process.stdout.write("push\n\n"); continue; }
  if (line === "list" || line === "list for-push") {
    for (const [ref, sha] of await remoteRefs()) process.stdout.write(`${sha} ${ref}\n`);
    process.stdout.write("\n"); continue;
  }
  if (line.startsWith("push ")) {
    const spec = line.slice(5);
    try { await push(spec); process.stdout.write(`ok ${spec.split(":")[1]}\n`); }
    catch (error) { process.stdout.write(`error ${spec.split(":")[1]} ${String(error.message).replace(/[\r\n]+/g, " ")}\n`); }
    continue;
  }
  if (line === "") { process.stdout.write("\n"); continue; }
  throw new Error(`unsupported remote-helper command from ${remoteName}: ${line}`);
}
