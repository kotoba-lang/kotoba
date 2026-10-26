#!/usr/bin/env node
import { constants } from "node:fs";
import { open } from "node:fs/promises";
import { resolve } from "node:path";
import { decryptFile, encryptFile, generateRecoveryKey } from "./encrypted-image.mjs";

function arg(name) {
  const index = process.argv.indexOf(name);
  return index < 0 ? undefined : process.argv[index + 1];
}

async function main() {
  const command = process.argv[2];
  const input = arg("--input");
  const output = arg("--output");
  if (command === "keygen") return process.stdout.write(`${generateRecoveryKey()}\n`);
  if (arg("--recovery-key")) throw new Error("--recovery-key is refused because command-line keys leak via shell history/process inspection; use --recovery-key-file");
  const keyFile = arg("--recovery-key-file");
  if (!input || !output || !keyFile) throw new Error("encrypt/decrypt require --input, --output, and --recovery-key-file");
  const keyPath = resolve(keyFile);
  const noFollow = constants.O_NOFOLLOW ?? 0;
  const keyHandle = await open(keyPath, constants.O_RDONLY | noFollow);
  let key;
  try {
    const keyStat = await keyHandle.stat();
    if (!keyStat.isFile()) throw new Error("recovery key path must be a regular file");
    if ((keyStat.mode & 0o077) !== 0) throw new Error("recovery key file must not be readable or writable by group/others (use chmod 600)");
    key = (await keyHandle.readFile("utf8")).trim();
  } finally {
    await keyHandle.close();
  }
  if (command === "encrypt") await encryptFile(resolve(input), resolve(output), key);
  else if (command === "decrypt") await decryptFile(resolve(input), resolve(output), key);
  else throw new Error("usage: encrypted-image-cli.mjs keygen | encrypt/decrypt --input PATH --output PATH --recovery-key-file PATH");
}

main().catch((error) => { process.stderr.write(`error: ${error.message}\n`); process.exitCode = 1; });
