import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { chmod, mkdtemp, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import { formatRecoveryKey } from "../encrypted-image.mjs";

const run = promisify(execFile);
const cli = resolve("os/aiueos/installer/encrypted-image-cli.mjs");
const key = formatRecoveryKey(Buffer.alloc(32, 7));

test("CLI refuses recovery keys in process arguments", async () => {
  await assert.rejects(
    run(process.execPath, [cli, "encrypt", "--input", "in", "--output", "out", "--recovery-key", key]),
    /command-line keys leak/,
  );
});

test("CLI requires a private key file and round trips", async () => {
  const dir = await mkdtemp(join(tmpdir(), "aiueos-key-file-"));
  const input = join(dir, "input");
  const encrypted = join(dir, "encrypted");
  const output = join(dir, "output");
  const keyFile = join(dir, "key");
  await writeFile(input, "private bytes");
  await writeFile(keyFile, `${key}\n`);
  await chmod(keyFile, 0o644);
  await assert.rejects(
    run(process.execPath, [cli, "encrypt", "--input", input, "--output", encrypted, "--recovery-key-file", keyFile]),
    /must not be readable or writable by group\/others/,
  );
  await chmod(keyFile, 0o600);
  await run(process.execPath, [cli, "encrypt", "--input", input, "--output", encrypted, "--recovery-key-file", keyFile]);
  await run(process.execPath, [cli, "decrypt", "--input", encrypted, "--output", output, "--recovery-key-file", keyFile]);
  const { readFile } = await import("node:fs/promises");
  assert.equal(await readFile(output, "utf8"), "private bytes");
});

test("CLI refuses a symlink recovery-key path", async () => {
  const dir = await mkdtemp(join(tmpdir(), "aiueos-key-symlink-"));
  const input = join(dir, "input");
  const keyFile = join(dir, "key");
  const keyLink = join(dir, "key-link");
  await writeFile(input, "private bytes");
  await writeFile(keyFile, `${key}\n`, { mode: 0o600 });
  await symlink(keyFile, keyLink);
  await assert.rejects(
    run(process.execPath, [cli, "encrypt", "--input", input, "--output", join(dir, "encrypted"), "--recovery-key-file", keyLink]),
    /ELOOP|symbolic link/,
  );
});
