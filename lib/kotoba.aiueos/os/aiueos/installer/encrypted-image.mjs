import {
  createCipheriv,
  createDecipheriv,
  createHash,
  createHmac,
  hkdfSync,
  randomBytes,
  timingSafeEqual,
} from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

const MAGIC = Buffer.from("AIUEENC1", "ascii");
const TAG_BYTES = 16;
const DEFAULT_CHUNK_BYTES = 1024 * 1024;
const MAX_HEADER_BYTES = 16 * 1024;
const RECOVERY_PREFIX = "AIUEOS1";

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function deriveKeys(masterKey, salt) {
  if (!Buffer.isBuffer(masterKey) || masterKey.length !== 32) {
    throw new Error("recovery key must decode to exactly 32 bytes");
  }
  const derive = (label) => Buffer.from(hkdfSync("sha256", masterKey, salt, Buffer.from(label), 32));
  return {
    metadata: derive("aiueos encrypted image v1 metadata"),
    data: derive("aiueos encrypted image v1 data"),
    verifier: derive("aiueos encrypted image v1 verifier"),
  };
}

function nonce(prefix, index) {
  if (!Buffer.isBuffer(prefix) || prefix.length !== 8) throw new Error("nonce prefix must be 8 bytes");
  if (!Number.isSafeInteger(index) || index < 0 || index > 0xffffffff) throw new Error("chunk index is out of range");
  const result = Buffer.alloc(12);
  prefix.copy(result);
  result.writeUInt32BE(index, 8);
  return result;
}

function checksum(bytes) {
  return createHash("sha256").update("aiueos recovery key v1\0").update(bytes).digest("hex").slice(0, 8).toUpperCase();
}

export function formatRecoveryKey(masterKey) {
  if (!Buffer.isBuffer(masterKey) || masterKey.length !== 32) throw new Error("recovery key must be 32 bytes");
  const body = masterKey.toString("hex").toUpperCase().match(/.{1,8}/g).join("-");
  return `${RECOVERY_PREFIX}-${body}-${checksum(masterKey)}`;
}

export function parseRecoveryKey(text) {
  if (typeof text !== "string") throw new Error("recovery key must be text");
  const parts = text.trim().toUpperCase().split("-");
  if (parts.shift() !== RECOVERY_PREFIX || parts.length !== 9) throw new Error("invalid aiueos recovery key format");
  const suppliedChecksum = parts.pop();
  if (!parts.every((part) => /^[0-9A-F]{8}$/.test(part)) || !/^[0-9A-F]{8}$/.test(suppliedChecksum)) {
    throw new Error("invalid aiueos recovery key characters");
  }
  const key = Buffer.from(parts.join(""), "hex");
  const expected = Buffer.from(checksum(key), "ascii");
  const supplied = Buffer.from(suppliedChecksum, "ascii");
  if (!timingSafeEqual(expected, supplied)) throw new Error("recovery key checksum mismatch");
  return key;
}

export function generateRecoveryKey() {
  return formatRecoveryKey(randomBytes(32));
}

export function encryptBuffer(plaintext, recoveryKey, options = {}) {
  if (!Buffer.isBuffer(plaintext)) plaintext = Buffer.from(plaintext);
  const masterKey = typeof recoveryKey === "string" ? parseRecoveryKey(recoveryKey) : recoveryKey;
  const chunkBytes = options.chunkBytes ?? DEFAULT_CHUNK_BYTES;
  if (!Number.isSafeInteger(chunkBytes) || chunkBytes < 4096 || chunkBytes > 16 * 1024 * 1024) {
    throw new Error("chunkBytes must be an integer from 4096 through 16777216");
  }
  const salt = options.salt ? Buffer.from(options.salt) : randomBytes(32);
  const noncePrefix = options.noncePrefix ? Buffer.from(options.noncePrefix) : randomBytes(8);
  if (salt.length !== 32) throw new Error("salt must be 32 bytes");
  if (noncePrefix.length !== 8) throw new Error("noncePrefix must be 8 bytes");
  const chunkCount = Math.ceil(plaintext.length / chunkBytes);
  if (chunkCount > 0xffffffff) throw new Error("image has too many chunks for the v1 nonce space");
  const keys = deriveKeys(masterKey, salt);
  const header = {
    format: "aiueos.encrypted-chunks.v1",
    cipher: "AES-256-GCM",
    kdf: "HKDF-SHA-256",
    chunkBytes,
    plaintextBytes: plaintext.length,
    chunkCount,
    salt: salt.toString("base64"),
    noncePrefix: noncePrefix.toString("base64"),
    keyVerifier: createHmac("sha256", keys.verifier).update("aiueos encrypted image v1 key verifier").digest("base64"),
  };
  const headerBytes = Buffer.from(canonical(header), "utf8");
  if (headerBytes.length > MAX_HEADER_BYTES) throw new Error("encrypted-image header exceeds the v1 bound");
  const headerDigest = createHash("sha256").update(headerBytes).digest();
  const metadataCipher = createCipheriv("aes-256-gcm", keys.metadata, nonce(noncePrefix, 0xffffffff), { authTagLength: TAG_BYTES });
  metadataCipher.setAAD(headerBytes);
  metadataCipher.final();
  const metadataTag = metadataCipher.getAuthTag();
  const prefix = Buffer.alloc(MAGIC.length + 4);
  MAGIC.copy(prefix);
  prefix.writeUInt32BE(headerBytes.length, MAGIC.length);
  const frames = [prefix, headerBytes, metadataTag];
  for (let index = 0; index < chunkCount; index += 1) {
    const clear = plaintext.subarray(index * chunkBytes, Math.min((index + 1) * chunkBytes, plaintext.length));
    const aad = Buffer.alloc(headerDigest.length + 8);
    headerDigest.copy(aad);
    aad.writeUInt32BE(index, headerDigest.length);
    aad.writeUInt32BE(clear.length, headerDigest.length + 4);
    const cipher = createCipheriv("aes-256-gcm", keys.data, nonce(noncePrefix, index), { authTagLength: TAG_BYTES });
    cipher.setAAD(aad);
    const encrypted = Buffer.concat([cipher.update(clear), cipher.final()]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(encrypted.length);
    frames.push(length, encrypted, cipher.getAuthTag());
  }
  return Buffer.concat(frames);
}

export function decryptBuffer(image, recoveryKey) {
  if (!Buffer.isBuffer(image)) image = Buffer.from(image);
  if (image.length < MAGIC.length + 4 + TAG_BYTES || !timingSafeEqual(image.subarray(0, MAGIC.length), MAGIC)) {
    throw new Error("not an aiueos encrypted image v1");
  }
  const headerLength = image.readUInt32BE(MAGIC.length);
  const headerStart = MAGIC.length + 4;
  const headerEnd = headerStart + headerLength;
  if (headerLength === 0 || headerLength > MAX_HEADER_BYTES || headerEnd + TAG_BYTES > image.length) throw new Error("truncated or oversized encrypted-image header");
  const headerBytes = image.subarray(headerStart, headerEnd);
  let header;
  try { header = JSON.parse(headerBytes.toString("utf8")); } catch { throw new Error("invalid encrypted-image header JSON"); }
  if (canonical(header) !== headerBytes.toString("utf8")) throw new Error("encrypted-image header is not canonical");
  if (header.format !== "aiueos.encrypted-chunks.v1" || header.cipher !== "AES-256-GCM" || header.kdf !== "HKDF-SHA-256") {
    throw new Error("unsupported encrypted-image format or algorithms");
  }
  if (!Number.isSafeInteger(header.chunkBytes) || header.chunkBytes < 4096 || header.chunkBytes > 16 * 1024 * 1024 ||
      !Number.isSafeInteger(header.plaintextBytes) || header.plaintextBytes < 0 ||
      !Number.isSafeInteger(header.chunkCount) || header.chunkCount < 0 || header.chunkCount > 0xffffffff ||
      header.chunkCount !== Math.ceil(header.plaintextBytes / header.chunkBytes)) {
    throw new Error("invalid encrypted-image geometry");
  }
  const salt = Buffer.from(header.salt ?? "", "base64");
  const noncePrefix = Buffer.from(header.noncePrefix ?? "", "base64");
  if (salt.length !== 32 || noncePrefix.length !== 8) throw new Error("invalid encrypted-image salt or nonce prefix");
  const masterKey = typeof recoveryKey === "string" ? parseRecoveryKey(recoveryKey) : recoveryKey;
  const keys = deriveKeys(masterKey, salt);
  const expectedVerifier = createHmac("sha256", keys.verifier).update("aiueos encrypted image v1 key verifier").digest();
  const suppliedVerifier = Buffer.from(header.keyVerifier ?? "", "base64");
  if (suppliedVerifier.length !== expectedVerifier.length || !timingSafeEqual(expectedVerifier, suppliedVerifier)) {
    throw new Error("wrong recovery key or corrupt key verifier");
  }
  const metadataTag = image.subarray(headerEnd, headerEnd + TAG_BYTES);
  try {
    const metadataCipher = createDecipheriv("aes-256-gcm", keys.metadata, nonce(noncePrefix, 0xffffffff), { authTagLength: TAG_BYTES });
    metadataCipher.setAAD(headerBytes);
    metadataCipher.setAuthTag(metadataTag);
    metadataCipher.final();
  } catch { throw new Error("encrypted-image metadata authentication failed"); }
  const headerDigest = createHash("sha256").update(headerBytes).digest();
  const chunks = [];
  let offset = headerEnd + TAG_BYTES;
  for (let index = 0; index < header.chunkCount; index += 1) {
    if (offset + 4 + TAG_BYTES > image.length) throw new Error(`encrypted-image chunk ${index} is truncated`);
    const length = image.readUInt32BE(offset); offset += 4;
    const expectedLength = Math.min(header.chunkBytes, header.plaintextBytes - index * header.chunkBytes);
    if (length !== expectedLength || offset + length + TAG_BYTES > image.length) throw new Error(`encrypted-image chunk ${index} has invalid length`);
    const encrypted = image.subarray(offset, offset + length); offset += length;
    const tag = image.subarray(offset, offset + TAG_BYTES); offset += TAG_BYTES;
    const aad = Buffer.alloc(headerDigest.length + 8);
    headerDigest.copy(aad);
    aad.writeUInt32BE(index, headerDigest.length);
    aad.writeUInt32BE(length, headerDigest.length + 4);
    try {
      const decipher = createDecipheriv("aes-256-gcm", keys.data, nonce(noncePrefix, index), { authTagLength: TAG_BYTES });
      decipher.setAAD(aad);
      decipher.setAuthTag(tag);
      chunks.push(Buffer.concat([decipher.update(encrypted), decipher.final()]));
    } catch { throw new Error(`encrypted-image chunk ${index} authentication failed`); }
  }
  if (offset !== image.length) throw new Error("encrypted image has unauthenticated trailing bytes");
  return Buffer.concat(chunks);
}

export async function encryptFile(inputPath, outputPath, recoveryKey, options) {
  const encrypted = encryptBuffer(await readFile(inputPath), recoveryKey, options);
  await writeFile(outputPath, encrypted, { flag: "wx", mode: 0o600 });
}

export async function decryptFile(inputPath, outputPath, recoveryKey) {
  const clear = decryptBuffer(await readFile(inputPath), recoveryKey);
  await writeFile(outputPath, clear, { flag: "wx", mode: 0o600 });
}
