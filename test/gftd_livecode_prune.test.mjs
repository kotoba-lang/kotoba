import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const TARGET_FILES = {
  b2Probe: path.join(
    REPO_ROOT,
    "lib/kotoba.kotobaseStorage/providers/kotoba.kotobase.storage.s3/test/b2_range_probe.cljk",
  ),
  s3Readme: path.join(
    REPO_ROOT,
    "lib/kotoba.kotobaseStorage/providers/kotoba.kotobase.storage.s3/README.md",
  ),
  ingestShiropico: path.join(
    REPO_ROOT,
    "lib/kotoba.kuraNode/script/ingest_shiropico.cljk",
  ),
};

function findKbbEngine() {
  const candidates = [
    process.env.KBB_ENGINE,
    path.resolve(REPO_ROOT, "../org-babashka-nbb/cli.js"),
  ].filter(Boolean);
  return candidates.find((p) => fs.existsSync(p)) ?? null;
}

const KBB_BIN = path.join(REPO_ROOT, "bin/kbb");
const KBB_ENGINE = findKbbEngine();

const B2_PROBE_CP = [
  "lib/kotoba.kotobaseStorage/providers/kotoba.kotobase.storage.s3/src",
  "lib/kotoba.kotobaseStorage/providers/kotoba.kotobase.storage.s3/test",
  "lib/kotoba.kotobaseStorage/src",
  "lib/kotoba.text/src",
  "lib/kotoba.sigv4/src",
  "lib/gov.nist.sha2/src",
  "lib/kotoba.ioIpld/src",
  "lib/kotoba.ioIpldCar/src",
  "lib/kotoba.ioMultiformats/src",
  "lib/kotoba.coll/src",
  "lib/kotoba.bytes/src",
  "lib/org.ietf.cbor/src",
].map((p) => path.join(REPO_ROOT, p)).join(":");

const INGEST_CP = [
  "lib/kotoba.kuraNode/src",
  "lib/kotoba.kuraNode/script",
  "lib/kotoba.text/src",
  "lib/kotoba.spec/src",
  "lib/kotoba.osaho/src",
  "lib/kotoba.kotobaHir/src",
  "lib/kotoba.bytes/src",
  "lib/kotoba.erasure/src",
  "lib/kotoba.kura/src",
  "lib/kotoba.merkleSum/src",
  "lib/kotoba.sigv4/src",
  "lib/gov.nist.sha2/src",
  "lib/kotoba.coll/src",
  "lib/kotoba.json/src",
].map((p) => path.join(REPO_ROOT, p)).join(":");

test("target files contain zero occurrences of ai-gftd", () => {
  for (const [label, filePath] of Object.entries(TARGET_FILES)) {
    const content = fs.readFileSync(filePath, "utf8");
    const matches = content.match(/ai-gftd/gi) ?? [];
    assert.equal(
      matches.length,
      0,
      `${label} (${path.relative(REPO_ROOT, filePath)}) must have 0 matches for ai-gftd, found ${matches.length}`,
    );
  }
});

test("static fail-closed contracts in b2_range_probe.cljk, README.md, and ingest_shiropico.cljk", () => {
  const probe = fs.readFileSync(TARGET_FILES.b2Probe, "utf8");
  assert.match(probe, /B2_PROBE_KEYCHAIN_SERVICE/);
  assert.match(probe, /B2_PROBE_BUCKET/);
  assert.match(probe, /\(require-config!\)/);
  assert.ok(
    probe.indexOf("(require-config!)") < probe.indexOf("(keychain)"),
    "require-config! must run before (keychain) in -main",
  );
  assert.match(probe, /\(js\/process\.exit 2\)/);

  const readme = fs.readFileSync(TARGET_FILES.s3Readme, "utf8");
  assert.match(readme, /B2_PROBE_KEYCHAIN_SERVICE/);
  assert.match(readme, /B2_PROBE_BUCKET/);

  const ingest = fs.readFileSync(TARGET_FILES.ingestShiropico, "utf8");
  assert.match(ingest, /:bucket\s+\(env\s+"SRC_BUCKET"\)/);
  assert.match(ingest, /"SRC_BUCKET"/);
  assert.match(ingest, /SRC_BUCKET/);
});

test("b2_range_probe.cljk fails closed with exit 2 and never invokes security when env vars are missing/blank", (t) => {
  if (!KBB_ENGINE) {
    t.skip("kbb SCI engine (org-babashka-nbb) not available in this environment");
    return;
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "b2-probe-fail-closed-"));
  const poisonLog = path.join(tmpDir, "security-invoked.log");
  const poisonSecurity = path.join(tmpDir, "security");
  fs.writeFileSync(
    poisonSecurity,
    `#!/bin/sh\necho "POISON_SECURITY_CALLED $*" >> "${poisonLog}"\nexit 99\n`,
    { mode: 0o755 },
  );

  const nodeBinDir = path.dirname(process.execPath);
  const safePath = `${tmpDir}:${nodeBinDir}:/usr/bin:/bin`;

  const cases = [
    {
      name: "both env vars unset",
      extraEnv: {},
      expectMentioned: ["B2_PROBE_KEYCHAIN_SERVICE", "B2_PROBE_BUCKET"],
    },
    {
      name: "only B2_PROBE_KEYCHAIN_SERVICE set",
      extraEnv: { B2_PROBE_KEYCHAIN_SERVICE: "b2:dummy-probe-service" },
      expectMentioned: ["B2_PROBE_BUCKET"],
    },
    {
      name: "B2_PROBE_KEYCHAIN_SERVICE empty and B2_PROBE_BUCKET set",
      extraEnv: { B2_PROBE_KEYCHAIN_SERVICE: "", B2_PROBE_BUCKET: "dummy-bucket" },
      expectMentioned: ["B2_PROBE_KEYCHAIN_SERVICE"],
    },
    {
      name: "both env vars whitespace-only",
      extraEnv: { B2_PROBE_KEYCHAIN_SERVICE: "   ", B2_PROBE_BUCKET: "\t " },
      expectMentioned: ["B2_PROBE_KEYCHAIN_SERVICE", "B2_PROBE_BUCKET"],
    },
  ];

  try {
    for (const c of cases) {
      const res = spawnSync(
        KBB_BIN,
        ["--backend", "sci", "--classpath", B2_PROBE_CP, "-e", "(require '[b2-range-probe])"],
        {
          cwd: tmpDir,
          encoding: "utf8",
          env: {
            PATH: safePath,
            HOME: tmpDir,
            KBB_NO_STDLIB: "1",
            KBB_ENGINE,
            ...c.extraEnv,
          },
          timeout: 15000,
        },
      );

      assert.equal(
        res.status,
        2,
        `${c.name}: expected exit code 2, got ${res.status}\nstdout:\n${res.stdout}\nstderr:\n${res.stderr}`,
      );
      const combined = `${res.stdout}\n${res.stderr}`;
      for (const varName of c.expectMentioned) {
        assert.match(
          combined,
          new RegExp(varName),
          `${c.name}: output should mention ${varName}\n${combined}`,
        );
      }
      assert.equal(
        fs.existsSync(poisonLog),
        false,
        `${c.name}: security binary must never be invoked before env validation`,
      );
    }
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test("ingest_shiropico.cljk fails closed on SRC_BUCKET assertion before storage/network calls", (t) => {
  if (!KBB_ENGINE) {
    t.skip("kbb SCI engine (org-babashka-nbb) not available in this environment");
    return;
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ingest-fail-closed-"));
  const nodeBinDir = path.dirname(process.execPath);
  const safePath = `${nodeBinDir}:/usr/bin:/bin`;

  const dummyRequiredExceptBucket = {
    SRC_KEY_ID: "dummy-src-key-id",
    SRC_APP_KEY: "dummy-src-app-key",
    B2_KEY_ID: "dummy-b2-key-id",
    B2_APP_KEY: "dummy-b2-app-key",
    KURA_NODE_TOKEN: "dummy-kura-node-token",
  };

  const cases = [
    { name: "SRC_BUCKET unset", extraEnv: {} },
    { name: "SRC_BUCKET empty", extraEnv: { SRC_BUCKET: "" } },
    { name: "SRC_BUCKET whitespace-only", extraEnv: { SRC_BUCKET: "   " } },
  ];

  const erasureKirPath = path.join(
    REPO_ROOT,
    "lib/kotoba.erasure/resources/erasure/oracle/erasure-core.kir.edn",
  );
  const bootstrapExpr = `(require '["node:fs" :as fs] '[cljs.reader :as r] '[erasure.kotoba-oracle :as eo]) (eo/register-kir! :erasure-core (r/read-string (.readFileSync fs ${JSON.stringify(erasureKirPath)} "utf8"))) (require '[ingest-shiropico])`;

  try {
    for (const c of cases) {
      const res = spawnSync(
        KBB_BIN,
        ["--backend", "sci", "--classpath", INGEST_CP, "-e", bootstrapExpr],
        {
          cwd: tmpDir,
          encoding: "utf8",
          env: {
            PATH: safePath,
            HOME: tmpDir,
            KBB_NO_STDLIB: "1",
            KBB_ENGINE,
            ...dummyRequiredExceptBucket,
            ...c.extraEnv,
          },
          timeout: 15000,
        },
      );

      assert.notEqual(
        res.status,
        0,
        `${c.name}: expected non-zero exit status, got 0\nstdout:\n${res.stdout}\nstderr:\n${res.stderr}`,
      );
      const combined = `${res.stdout}\n${res.stderr}`;
      assert.match(
        combined,
        /SRC_BUCKET is required/,
        `${c.name}: expected 'SRC_BUCKET is required' assertion error, got:\n${combined}`,
      );
    }
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});
