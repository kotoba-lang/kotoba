import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";

export async function sha256File(path, limit = undefined) {
  const hash = createHash("sha256");
  let seen = 0;
  for await (const chunk of createReadStream(path)) {
    const usable = limit === undefined ? chunk : chunk.subarray(0, Math.max(0, Math.min(chunk.length, limit - seen)));
    if (usable.length) hash.update(usable);
    seen += usable.length;
    if (limit !== undefined && seen === limit) break;
  }
  return { sha256: hash.digest("hex"), bytes: seen };
}

export async function validateReleaseReceipt(imagePath, receiptPath) {
  const receipt = JSON.parse(await readFile(receiptPath, "utf8"));
  const expected = receipt?.disk;
  if (!expected || !Number.isSafeInteger(expected.bytes) || !/^[0-9a-f]{64}$/.test(expected.sha256 ?? "")) {
    throw new Error("receipt does not contain valid disk.bytes and disk.sha256 fields");
  }
  const actualBytes = (await stat(imagePath)).size;
  if (actualBytes !== expected.bytes) throw new Error(`image byte size ${actualBytes} does not match receipt ${expected.bytes}`);
  const actual = await sha256File(imagePath);
  if (actual.sha256 !== expected.sha256) throw new Error(`image sha256 ${actual.sha256} does not match receipt ${expected.sha256}`);
  return { bytes: actualBytes, sha256: actual.sha256 };
}
