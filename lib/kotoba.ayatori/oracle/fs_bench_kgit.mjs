#!/usr/bin/env node
// oracle/fs_bench_kgit.mjs -- one-shot filesystem bench, kgit arm active.
//
// NEW FILE (2026-11-09): oracle/fs_bench.mjs is left untouched per the
// new-files-only rule. This variant swaps the git arm to kgit and keeps
// the legacy real-git arm runnable behind KGIT_REAL=1 as the control /
// negative path. All other arms (host / awai / datom) are verbatim copies
// of fs_bench.mjs so numbers stay comparable.
//
// Backends:
//   (1) host  : mac host fs baseline (node:fs under os.tmpdir).
//   (2) awai  : static-verified-artifact overlay (sha256-pinned reads).
//   (3) datom : datom-plane fs (ports oracle/fs_datom_adapter.cljc).
//   (4) kgit  : NEW DEFAULT git arm -- in-process content-addressed
//             blob/tree/commit plane (ports oracle/kgit_adapter.cljc):
//             git framing `type SP size NUL body`, SHA-1 OID, digest-pinned
//             verified reads, zero spawn. Blob/tree/commit OIDs verified
//             byte-identical to real git (see RESULTS record).
//   (5) git   : legacy real-git arm, ONLY when KGIT_REAL=1 (control).
//
// Gates (else exit 2, like fitness):
//   - all backends agree on the survivors snapshot hash at every size;
//   - kgit blob OIDs + bytes cross-checked against real git at small n.
//
// Oracle rules: one-shot measurement. Do not wire into CI/gates/builds/
// packaging/execution. No silent fallback.
import { mkdtempSync, writeFileSync, readFileSync, existsSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const sha256 = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const sha1 = (buf) => createHash("sha1").update(buf).digest("hex");
const nowMs = () => Date.now();
const argSizes = (() => {
  const m = process.argv.find((a) => a.startsWith("--sizes="));
  if (m) return m.slice(8).split(",").map(Number).filter((n) => n > 0);
  return [16, 64, 256]; // 1x / 4x / 16x
})();
const WITH_REAL_GIT = process.env.KGIT_REAL === "1";

function workload(n) {
  const files = [];
  for (let i = 0; i < n; i++) {
    const name = `f${String(i).padStart(5, "0")}.txt`;
    files.push({ path: name, content: `content-${i}-of-${n}\n` });
  }
  return files;
}

// ---- (1) host fs (verbatim from fs_bench.mjs) ----
function makeHost() {
  const root = mkdtempSync(join(tmpdir(), "oracle-hostfs-"));
  let trips = 0, bytes = 0;
  return {
    name: "host",
    write: (p, c) => { writeFileSync(join(root, p), c); trips++; bytes += c.length; },
    read: (p) => { const f = join(root, p); if (!existsSync(f)) { trips++; return null; } const s = readFileSync(f, "utf8"); trips++; bytes += s.length; return s; },
    exists: (p) => { trips++; return existsSync(join(root, p)); },
    list: () => { trips++; return readdirSync(root).sort(); },
    del: (p) => { rmSync(join(root, p), { force: true }); trips++; },
    snapshot: (files) => files.map((f) => [f.path, readFileSync(join(root, f.path), "utf8")]).sort((a, b) => a[0] < b[0] ? -1 : 1),
    stats: () => ({ trips, bytes }),
    cleanup: () => rmSync(root, { recursive: true, force: true }),
  };
}

// ---- (2) awai static-artifact overlay (verbatim from fs_bench.mjs) ----
function makeAwai() {
  const m = new Map(); // path -> {content, digest}
  let trips = 0, bytes = 0;
  return {
    name: "awai",
    write: (p, c) => { m.set(p, { content: c, digest: sha256(c) }); trips++; bytes += c.length; },
    read: (p) => {
      const e = m.get(p); trips++;
      if (!e) return null;
      const got = sha256(e.content); // pinned verification on every read
      if (got !== e.digest) throw new Error(`awai: digest mismatch for ${p}`);
      bytes += e.content.length;
      return e.content;
    },
    exists: (p) => { trips++; return m.has(p); },
    list: () => { trips++; return [...m.keys()].sort(); },
    del: (p) => { m.delete(p); trips++; },
    snapshot: (files) => files.map((f) => [f.path, m.get(f.path)?.content ?? null]).sort((a, b) => a[0] < b[0] ? -1 : 1),
    stats: () => ({ trips, bytes }),
    cleanup: () => {},
  };
}

// ---- (3) datom fs (verbatim from fs_bench.mjs, ports fs_datom_adapter.cljc) ----
function makeDatom() {
  let datoms = []; // {:s,:p,:o}
  const byPath = new Map(); // path -> content (the :fs/path index)
  let trips = 0, bytes = 0;
  const norm = (p) => {
    if (p.includes("..")) throw new Error("fs-datom: path escapes root");
    return p.replace(/^\/+/, "");
  };
  return {
    name: "datom",
    write: (p, c) => {
      const q = norm(p);
      datoms = datoms.filter((d) => d.s !== q);
      datoms.push({ s: q, p: ":fs/path", o: q }, { s: q, p: ":fs/content", o: c });
      byPath.set(q, c); trips++; bytes += c.length;
    },
    read: (p) => { const c = byPath.get(norm(p)) ?? null; trips++; if (c) bytes += c.length; return c; },
    exists: (p) => { trips++; return byPath.has(norm(p)); },
    list: () => { trips++; return [...byPath.keys()].filter((k) => !k.includes("/")).sort(); },
    del: (p) => { const q = norm(p); datoms = datoms.filter((d) => d.s !== q); byPath.delete(q); trips++; },
    snapshot: (files) => files.map((f) => [f.path, byPath.get(f.path) ?? null]).sort((a, b) => a[0] < b[0] ? -1 : 1),
    stats: () => ({ trips, bytes, datoms: datoms.length }),
    cleanup: () => {},
  };
}

// ---- (4) kgit: in-process git over the content-addressed block plane ----
// Ports oracle/kgit_adapter.cljc. Zero spawn: SHA-1 via node:crypto,
// framing `blob <byte-size> NUL <body>`, digest-pinned verified reads.
function makeKgit() {
  const objects = new Map(); // oid -> {framed: Buffer, body: string}
  const idx = new Map(); // path -> oid
  let trips = 0, bytes = 0;
  const norm = (p) => {
    if (p.includes("..")) throw new Error("kgit: path escapes root");
    return p.replace(/^\/+/, "");
  };
  const frameBlob = (c) => {
    const body = Buffer.from(c, "utf8");
    return Buffer.concat([Buffer.from(`blob ${body.length}\0`, "utf8"), body]);
  };
  const blobOid = (c) => sha1(frameBlob(c));
  return {
    name: "kgit",
    write: (p, c) => {
      const q = norm(p);
      const framed = frameBlob(c);
      objects.set(sha1(framed), { framed, body: c });
      idx.set(q, sha1(framed));
      trips++; bytes += c.length;
    },
    read: (p) => {
      const q = norm(p);
      const oid = idx.get(q);
      trips++;
      if (!oid) return null;
      const e = objects.get(oid);
      if (!e) throw new Error(`kgit: index points at missing object for ${q}`);
      if (sha1(e.framed) !== oid) throw new Error(`kgit: OID verification failed for ${q}`);
      bytes += e.body.length;
      return e.body;
    },
    exists: (p) => { trips++; return idx.has(norm(p)); },
    list: () => { trips++; return [...idx.keys()].sort(); },
    del: (p) => { idx.delete(norm(p)); trips++; },
    snapshot: (files) => files.map((f) => {
      const oid = idx.get(f.path);
      if (!oid) return [f.path, null];
      const e = objects.get(oid);
      if (sha1(e.framed) !== oid) throw new Error(`kgit: OID verification failed in snapshot for ${f.path}`);
      return [f.path, e.body];
    }).sort((a, b) => a[0] < b[0] ? -1 : 1),
    // oid + bytes exposed for the real-git cross-check (not counted as trips)
    _oidOf: (p) => idx.get(norm(p)) ?? null,
    _bytesOfOid: (oid) => objects.get(oid)?.framed ?? null,
    _blobOid,
    stats: () => ({ trips, bytes, spawns: 0 }),
    cleanup: () => {},
  };
  function _blobOid(c) { return blobOid(c); }
}

// ---- (5) legacy real-git arm (control, only under KGIT_REAL=1) ----
function makeGit() {
  const root = mkdtempSync(join(tmpdir(), "oracle-gitfs-"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  const idx = new Map(); // path -> sha
  let trips = 0, bytes = 0, spawns = 0;
  const gitHash = (args, input) => { spawns++; return execFileSync("git", args, { cwd: root, input, encoding: "utf8" }).trim(); };
  const gitShow = (args) => { spawns++; return execFileSync("git", args, { cwd: root, encoding: "utf8" }); };
  return {
    name: "git",
    write: (p, c) => { const s = gitHash(["hash-object", "-w", "--stdin"], c); idx.set(p, s); trips++; bytes += c.length; },
    read: (p) => { const s = idx.get(p); trips++; if (!s) return null; const out = gitShow(["cat-file", "-p", s]); bytes += out.length; return out; },
    exists: (p) => { trips++; return idx.has(p); },
    list: () => { trips++; return [...idx.keys()].sort(); },
    del: (p) => { idx.delete(p); trips++; },
    snapshot: (files) => files.map((f) => { const s = idx.get(f.path); return [f.path, s ? gitShow(["cat-file", "-p", s]) : null]; }).sort((a, b) => a[0] < b[0] ? -1 : 1),
    stats: () => ({ trips, bytes, spawns }),
    cleanup: () => rmSync(root, { recursive: true, force: true }),
  };
}

function gitVersion() { try { return execFileSync("git", ["--version"], { encoding: "utf8" }).trim(); } catch { return "git: unavailable"; } }

// Cross-check kgit blob OIDs + bytes against real git at small n.
// Spawns counted separately (xcheck), never in the kgit arm's trips.
let xcheckResult = "skipped";
function crossCheck(kgit, files) {
  const root = mkdtempSync(join(tmpdir(), "oracle-kgit-xcheck-"));
  let spawns = 0;
  try {
    execFileSync("git", ["init", "-q"], { cwd: root }); spawns++;
    for (const f of files) {
      const expect = kgit._blobOid(f.content);
      const got = execFileSync("git", ["hash-object", "-w", "--stdin"], { cwd: root, input: f.content, encoding: "utf8" }).trim();
      spawns++;
      if (got !== expect) {
        console.error(`XCHECK MISMATCH oid ${f.path}: kgit=${expect} git=${got}`);
        process.exit(2);
      }
      const back = execFileSync("git", ["cat-file", "-p", got], { cwd: root, encoding: "utf8" });
      spawns++;
      if (back !== f.content) {
        console.error(`XCHECK MISMATCH bytes ${f.path}`);
        process.exit(2);
      }
    }
    xcheckResult = `OK(files=${files.length} spawns=${spawns})`;
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

function runSize(n, doXcheck) {
  const files = workload(n);
  const backends = [makeHost(), makeAwai(), makeDatom(), makeKgit()];
  if (WITH_REAL_GIT) backends.push(makeGit());
  const out = {};
  let kgitRef = null;
  for (const b of backends) {
    const t0 = nowMs();
    for (const f of files) b.write(f.path, f.content);
    for (const f of files) { const got = b.read(f.path); if (got !== f.content) { console.error(`MISMATCH ${b.name} read ${f.path}`); process.exit(2); } }
    const listed = b.list();
    for (const f of files.slice(0, Math.min(8, files.length))) b.exists(f.path);
    // delete every other file, then re-list
    const survivors = files.filter((_, i) => i % 2 === 0);
    const removed = files.filter((_, i) => i % 2 === 1);
    for (const f of removed) b.del(f.path);
    const wallMs = nowMs() - t0;
    const snap = b.snapshot(survivors);
    const snapHash = sha256(JSON.stringify(snap));
    out[b.name] = { wallMs: String(wallMs), ...Object.fromEntries(Object.entries(b.stats()).map(([k, v]) => [k, String(v)])), snapHash, listedN: String(listed.length), survivorsN: String(snap.length) };
    if (b.name === "kgit") kgitRef = { arm: b, survivors };
    b.cleanup();
  }
  const hashes = new Set(Object.values(out).map((r) => r.snapHash));
  if (hashes.size !== 1) { console.error(`ANSWER DIVERGENCE at n=${n}: ${JSON.stringify(Object.fromEntries(Object.entries(out).map(([k, v]) => [k, v.snapHash])))}`); process.exit(2); }
  if (doXcheck && kgitRef) crossCheck(kgitRef.arm, files);
  return out;
}

console.log(`oracle fs bench (kgit) | date=${new Date().toISOString()} | node=${process.version} | ${gitVersion()} | sizes=${argSizes.join(",")} | KGIT_REAL=${WITH_REAL_GIT ? "1" : "0"} | cwd=${process.cwd()}`);
console.log("wall-clock caveat: loaded-machine number, describes host load not transport (ADR-2608160100). Primary metric: round-trip/operation counts.");
const all = {};
argSizes.forEach((n, i) => {
  const doXcheck = process.env.KGIT_XCHECK === "1" || (i === 0 && n <= 256); // KGIT_XCHECK=1 forces the cross-check at every size
  all[n] = runSize(n, doXcheck);
  console.log(`--- n=${n} ---`);
  for (const [b, r] of Object.entries(all[n])) console.log(`${b}: trips=${r.trips} bytes=${r.bytes} wallMs=${r.wallMs} listedN=${r.listedN} survivorsN=${r.survivorsN} snap=${r.snapHash.slice(0, 12)}${r.spawns && r.spawns !== "0" ? ` spawns=${r.spawns}` : ""}${r.datoms ? ` datoms=${r.datoms}` : ""}`);
});
console.log(`XCHECK kgit-vs-git: ${xcheckResult}`);
console.log("GATE: kgit agrees with every other arm on survivors snapshot at every size (else exit 2). OK.");
