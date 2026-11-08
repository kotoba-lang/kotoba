#!/usr/bin/env node
// oracle/fs_bench.mjs -- one-shot filesystem bench, 4 backends, identical workload.
//
// Backends:
//   (1) host  : mac host fs baseline (node:fs under os.tmpdir).
//   (2) awai  : static-verified-artifact overlay (sha256-pinned reads).
//             No standalone awai fs namespace was discovered in
//             network-awai-apex (only awai.apex.db app state); this arm models
//             the shared-contract discipline (origin = static verified assets).
//   (3) datom : this task's new datom-plane fs (ports oracle/fs_datom_adapter.cljc
//             semantics: :fs/path + :fs/content datoms, one round trip per op).
//   (4) git   : real git binary (hash-object -w / cat-file -p), counted per op.
//             git-workspace is a repo/forge catalog read-model, not an fs
//             mechanism, so the arm shells the mechanism itself.
//
// Metrics: operation/round-trip counts (primary, ayatori ADR convention) +
// wall clock with loaded-machine caveat + sweep over >=3 sizes with an
// answer-equivalence gate (any backend disagreement -> exit 2, like fitness).
//
// Oracle rules: one-shot measurement. Do not wire into CI/gates/builds/
// packaging/execution. No silent fallback.
import { mkdtempSync, writeFileSync, readFileSync, existsSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";

const sha256 = (s) => createHash("sha256").update(s, "utf8").digest("hex");
const nowMs = () => Date.now();
const argSizes = (() => {
  const m = process.argv.find((a) => a.startsWith("--sizes="));
  if (m) return m.slice(8).split(",").map(Number).filter((n) => n > 0);
  return [16, 64, 256]; // 1x / 4x / 16x
})();

function workload(n) {
  const files = [];
  for (let i = 0; i < n; i++) {
    const name = `f${String(i).padStart(5, "0")}.txt`;
    files.push({ path: name, content: `content-${i}-of-${n}\n` });
  }
  return files;
}

// ---- (1) host fs ----
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

// ---- (2) awai static-artifact overlay ----
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

// ---- (3) datom fs (ports fs_datom_adapter.cljc) ----
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

// ---- (4) git mechanism (real binary) ----
function makeGit() {
  const root = mkdtempSync(join(tmpdir(), "oracle-gitfs-"));
  execFileSync("git", ["init", "-q"], { cwd: root });
  const idx = new Map(); // path -> sha
  let trips = 0, bytes = 0, spawns = 0;
  const gitHash = (args, input) => { spawns++; return execFileSync("git", args, { cwd: root, input, encoding: "utf8" }).trim(); };
  const gitShow = (args) => { spawns++; return execFileSync("git", args, { cwd: root, encoding: "utf8" }); };
  const git = gitHash;
  return {
    name: "git",
    write: (p, c) => { const s = git(["hash-object", "-w", "--stdin"], c); idx.set(p, s); trips++; bytes += c.length; },
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

function runSize(n) {
  const files = workload(n);
  const backends = [makeHost(), makeAwai(), makeDatom(), makeGit()];
  const out = {};
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
    b.cleanup();
  }
  const hashes = new Set(Object.values(out).map((r) => r.snapHash));
  if (hashes.size !== 1) { console.error(`ANSWER DIVERGENCE at n=${n}: ${JSON.stringify(Object.fromEntries(Object.entries(out).map(([k, v]) => [k, v.snapHash])))}`); process.exit(2); }
  return out;
}

console.log(`oracle fs bench | date=${new Date().toISOString()} | node=${process.version} | ${gitVersion()} | sizes=${argSizes.join(",")} | cwd=${process.cwd()}`);
console.log("wall-clock caveat: loaded-machine number, describes host load not transport (ADR-2608160100). Primary metric: round-trip/operation counts.");
const all = {};
for (const n of argSizes) {
  all[n] = runSize(n);
  console.log(`--- n=${n} ---`);
  for (const [b, r] of Object.entries(all[n])) console.log(`${b}: trips=${r.trips} bytes=${r.bytes} wallMs=${r.wallMs} listedN=${r.listedN} survivorsN=${r.survivorsN} snap=${r.snapHash.slice(0, 12)}${r.spawns ? ` spawns=${r.spawns}` : ""}${r.datoms ? ` datoms=${r.datoms}` : ""}`);
}
console.log("GATE: all backends agree on survivors snapshot at every size (else exit 2). OK.");
