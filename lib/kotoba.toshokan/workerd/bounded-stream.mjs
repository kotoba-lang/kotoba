const DEFAULT_LIMITS = Object.freeze({
  maxBytes: 2_097_152,
  chunkBytes: 32_768,
  maxChunks: 64,
  maxRecords: 20,
  maxRecordBytes: 65_536
});

function utf8Bytes(text) {
  return new TextEncoder().encode(text);
}

async function sha256(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
}

function canonicalManifest(manifest) {
  return JSON.stringify({
    format: manifest.format,
    totalBytes: manifest.totalBytes,
    chunkBytes: manifest.chunkBytes,
    chunks: manifest.chunks.map(chunk => ({
      ordinal: chunk.ordinal,
      bytes: chunk.bytes,
      sha256: chunk.sha256
    }))
  });
}

export async function chunkText(text, limits = DEFAULT_LIMITS) {
  const bytes = utf8Bytes(text);
  if (bytes.byteLength > limits.maxBytes) throw new Error("stream-byte-limit");
  const chunks = [];
  for (let offset = 0, ordinal = 0; offset < bytes.byteLength; ordinal += 1) {
    if (ordinal >= limits.maxChunks) throw new Error("stream-chunk-limit");
    const value = bytes.slice(offset, offset + limits.chunkBytes);
    chunks.push(Object.freeze({
      ordinal,
      bytes: value.byteLength,
      sha256: await sha256(value),
      value
    }));
    offset += value.byteLength;
  }
  const manifest = {
    format: "kotoba.chunk-manifest/v1",
    totalBytes: bytes.byteLength,
    chunkBytes: limits.chunkBytes,
    chunks
  };
  return Object.freeze({
    ...manifest,
    rootSha256: await sha256(utf8Bytes(canonicalManifest(manifest)))
  });
}

export function frameXmlElements(xml, elementName, limits = DEFAULT_LIMITS) {
  if (!/^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$/.test(elementName))
    throw new Error("invalid-xml-frame-name");
  const open = `<${elementName}>`;
  const close = `</${elementName}>`;
  const frames = [];
  let cursor = 0;
  while (frames.length < limits.maxRecords) {
    const start = xml.indexOf(open, cursor);
    if (start < 0) break;
    const end = xml.indexOf(close, start + open.length);
    if (end < 0) throw new Error("xml-frame-unclosed");
    const value = xml.slice(start, end + close.length);
    if (utf8Bytes(value).byteLength > limits.maxRecordBytes)
      throw new Error("xml-frame-byte-limit");
    frames.push(value);
    cursor = end + close.length;
  }
  if (xml.indexOf(open, cursor) >= 0) throw new Error("xml-frame-count-limit");
  return Object.freeze(frames);
}

export async function persistChunkManifest(bucket, prefix, manifest) {
  for (const chunk of manifest.chunks) {
    await bucket.put(`blocks/sha256/${chunk.sha256}`, chunk.value, {
      onlyIf: { etagDoesNotMatch: "*" },
      httpMetadata: { contentType: "application/octet-stream" },
      customMetadata: {
        format: "kotoba.chunk/v1",
        ordinal: String(chunk.ordinal)
      }
    });
  }
  const stored = {
    format: manifest.format,
    rootSha256: manifest.rootSha256,
    totalBytes: manifest.totalBytes,
    chunkBytes: manifest.chunkBytes,
    chunks: manifest.chunks.map(({ ordinal, bytes, sha256 }) => ({
      ordinal, bytes, sha256
    }))
  };
  await bucket.put(`${prefix}.manifest.json`, JSON.stringify(stored), {
    httpMetadata: { contentType: "application/json; charset=utf-8" }
  });
  return Object.freeze(stored);
}

export { DEFAULT_LIMITS };
