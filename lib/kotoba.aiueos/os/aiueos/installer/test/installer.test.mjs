import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runInstaller } from "../install.mjs";
import { destructivePhrase } from "../device-policy.mjs";
import { fakeBackend, linuxSystemDiskPaths, realBackend } from "../backends.mjs";

async function fixture() {
  const dir = await mkdtemp(join(tmpdir(), "aiueos-installer-test-"));
  const image = join(dir, "release.img");
  const receipt = join(dir, "receipt.json");
  const bytes = Buffer.from("test-only release image");
  await writeFile(image, bytes);
  await writeFile(receipt, JSON.stringify({ disk: { bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") } }));
  return { dir, image, receipt, bytes };
}

function backend(info, outputPath) {
  let writes = 0;
  return {
    kind: "fake",
    inspect: async () => ({ info, systemDisks: ["/dev/fake-system"] }),
    writeImage: async (image, _device, expected) => {
      writes += 1;
      const bytes = await readFile(image); await writeFile(outputPath, bytes);
      return { bytes: expected.bytes, sha256: expected.sha256 };
    },
    writes: () => writes,
  };
}

const safe = { path: "/dev/fake-second", type: "disk", whole: true, internal: true, empty: true, mounted: false, boot: false, system: false, bytes: 1000000, model: "fake" };

test("default mode inspects and never writes", async () => {
  const f = await fixture(); const b = backend(safe, join(f.dir, "target"));
  const report = await runInstaller({ device: safe.path, image: f.image, receipt: f.receipt }, b);
  assert.equal(report.mode, "inspect"); assert.equal(report.allowed, true); assert.equal(b.writes(), 0);
});

test("install requires repeated target and exact destructive phrase", async () => {
  const f = await fixture(); const b = backend(safe, join(f.dir, "target"));
  await assert.rejects(runInstaller({ install: true, device: safe.path, confirmDevice: "/dev/fake-other", destructivePhrase: destructivePhrase(safe.path), image: f.image, receipt: f.receipt }, b), /exactly repeat/);
  await assert.rejects(runInstaller({ install: true, device: safe.path, confirmDevice: safe.path, destructivePhrase: "yes", image: f.image, receipt: f.receipt }, b), /must exactly equal/);
  assert.equal(b.writes(), 0);
});

test("only a second empty internal whole disk can be written", async () => {
  const f = await fixture();
  for (const mutation of [{ system: true }, { boot: true }, { empty: false }, { internal: false }, { whole: false, type: "partition" }, { mounted: true }]) {
    const info = { ...safe, ...mutation }; const b = backend(info, join(f.dir, `target-${JSON.stringify(mutation)}`));
    await assert.rejects(runInstaller({ install: true, device: info.path, confirmDevice: info.path, destructivePhrase: destructivePhrase(info.path), image: f.image, receipt: f.receipt }, b), /refusing install/);
    assert.equal(b.writes(), 0);
  }
});

test("unknown system disk, noncanonical target, and insufficient capacity fail closed", async () => {
  const f = await fixture();
  const cases = [
    { info: safe, systemDisks: [] },
    { info: { ...safe, path: "/dev/canonical-second" }, systemDisks: ["/dev/fake-system"] },
    { info: { ...safe, bytes: 1 }, systemDisks: ["/dev/fake-system"] },
  ];
  for (const value of cases) {
    let writes = 0;
    const b = { kind: "fake", inspect: async () => value, writeImage: async () => { writes += 1; } };
    await assert.rejects(runInstaller({ install: true, device: safe.path, confirmDevice: safe.path, destructivePhrase: destructivePhrase(safe.path), image: f.image, receipt: f.receipt }, b), /refusing install/);
    assert.equal(writes, 0);
  }
});

test("validated fake-device install writes and reports readback", async () => {
  const f = await fixture(); const output = join(f.dir, "fake-target"); const b = backend(safe, output);
  const report = await runInstaller({ install: true, device: safe.path, confirmDevice: safe.path, destructivePhrase: destructivePhrase(safe.path), image: f.image, receipt: f.receipt }, b);
  assert.equal(report.installed, true); assert.deepEqual(await readFile(output), f.bytes); assert.equal(b.writes(), 1);
});

test("installer passes the re-inspected target identity into the single write operation", async () => {
  const f = await fixture();
  const identity = { dev: 1, ino: 2, rdev: 3, mode: 4 };
  const info = { ...safe, nodeIdentity: identity };
  let receivedTarget;
  const b = {
    kind: "fake",
    inspect: async () => ({ info, systemDisks: ["/dev/fake-system"] }),
    writeImage: async (_image, _device, expected, target) => {
      receivedTarget = target;
      return expected;
    },
  };
  await runInstaller({ install: true, device: info.path, confirmDevice: info.path, destructivePhrase: destructivePhrase(info.path), image: f.image, receipt: f.receipt }, b);
  assert.deepEqual(receivedTarget.nodeIdentity, identity);
});

test("macOS backend refuses real writes when it cannot hold an exclusive block-device open", async () => {
  assert.throws(
    () => realBackend("darwin").writeImage("unused", "/dev/unused", { bytes: 1, sha256: "0".repeat(64) }, {}, {}),
    /supported only from Linux/,
  );
});

test("Linux live media identifies its USB system disk even when root is overlay", () => {
  const outputs = new Map([
    ["findmnt --noheadings --output SOURCE --target /", "overlay\n"],
    ["findmnt --noheadings --output SOURCE --target /cdrom", "/dev/sdb3\n"],
    ["lsblk --json --inverse --paths --output PATH,TYPE /dev/sdb3", JSON.stringify({ blockdevices: [{ path: "/dev/sdb3", type: "part", children: [{ path: "/dev/sdb", type: "disk" }] }] })],
  ]);
  const fakeRun = (command, args) => {
    const key = [command, ...args].join(" ");
    if (!outputs.has(key)) throw new Error(`not mounted: ${key}`);
    return outputs.get(key);
  };
  assert.deepEqual(linuxSystemDiskPaths(fakeRun), ["/dev/sdb"]);
});

test("bad receipt is rejected before device inspection or writing", async () => {
  const f = await fixture(); const b = backend(safe, join(f.dir, "target"));
  await writeFile(f.receipt, JSON.stringify({ disk: { bytes: f.bytes.length, sha256: "0".repeat(64) } }));
  await assert.rejects(runInstaller({ device: safe.path, image: f.image, receipt: f.receipt }, b), /does not match receipt/);
  assert.equal(b.writes(), 0);
});

test("the gated fake-device backend writes only to its configured regular file", async () => {
  const f = await fixture(); const outputPath = join(f.dir, "configured-fake-target"); const configPath = join(f.dir, "fake.json");
  await writeFile(configPath, JSON.stringify({ info: safe, systemDisks: ["/dev/fake-system"], outputPath }));
  const previousNodeEnv = process.env.NODE_ENV;
  const previousAllow = process.env.AIUEOS_INSTALLER_ALLOW_FAKE;
  process.env.NODE_ENV = "test"; process.env.AIUEOS_INSTALLER_ALLOW_FAKE = "1";
  try {
    const b = await fakeBackend(configPath);
    const report = await runInstaller({ install: true, device: safe.path, confirmDevice: safe.path, destructivePhrase: destructivePhrase(safe.path), image: f.image, receipt: f.receipt }, b);
    assert.equal(report.installed, true); assert.deepEqual(await readFile(outputPath), f.bytes);
  } finally {
    if (previousNodeEnv === undefined) delete process.env.NODE_ENV; else process.env.NODE_ENV = previousNodeEnv;
    if (previousAllow === undefined) delete process.env.AIUEOS_INSTALLER_ALLOW_FAKE; else process.env.AIUEOS_INSTALLER_ALLOW_FAKE = previousAllow;
  }
});
