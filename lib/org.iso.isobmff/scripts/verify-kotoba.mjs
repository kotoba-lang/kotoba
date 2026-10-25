import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [boxWebPath, boxWasmPath, avcWebPath, avcWasmPath,
  imageWebPath, imageWasmPath, hostPath, fixturePath] =
  process.argv.slice(2);
if (!boxWebPath || !boxWasmPath || !avcWebPath || !avcWasmPath ||
    !imageWebPath || !imageWasmPath || !hostPath || !fixturePath)
  throw new Error("missing conformance paths");

const bytes = fs.readFileSync(path.resolve(fixturePath));
if (bytes.length !== 12171) throw new Error("unexpected fixture length");
const host = await import(pathToFileURL(path.resolve(hostPath)));

const boxWeb = await import(pathToFileURL(path.resolve(boxWebPath)));
if (boxWeb.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("ISO-BMFF Web graph requested a capability");
if (boxWeb.instantiateKotoba().main() !== 42n)
  throw new Error("ISO-BMFF Web negative result mismatch");
if (boxWeb.instantiateKotoba()["fixture-check"](Array.from(bytes, BigInt)) !== 42n)
  throw new Error("ISO-BMFF Web fixture mismatch");

const boxWasmBytes = fs.readFileSync(path.resolve(boxWasmPath));
const boxWasmNegative = await host.instantiateKotoba(boxWasmBytes);
if (boxWasmNegative.instance.exports.main() !== 42n)
  throw new Error("ISO-BMFF Wasm negative result mismatch");
const boxWasm = await host.instantiateKotoba(boxWasmBytes);
if (boxWasm.instance.exports["fixture-check"](boxWasm.typedValues.bytes(bytes)) !== 42n)
  throw new Error("ISO-BMFF Wasm fixture mismatch");
let oversizedRejected = false;
try { boxWasm.typedValues.bytes(Buffer.alloc(16385)); }
catch { oversizedRejected = true; }
if (!oversizedRejected) throw new Error("oversized Wasm byte input was accepted");

const avcWeb = await import(pathToFileURL(path.resolve(avcWebPath)));
if (avcWeb.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("ISO-BMFF to H264 Web graph requested a capability");
if (avcWeb.instantiateKotoba().main() !== 42n)
  throw new Error("ISO-BMFF to H264 Web negative result mismatch");
if (avcWeb.instantiateKotoba()["fixture-check"](Array.from(bytes, BigInt)) !== 42n)
  throw new Error("ISO-BMFF to H264 Web fixture mismatch");

const avcWasmBytes = fs.readFileSync(path.resolve(avcWasmPath));
const avcWasmNegative = await host.instantiateKotoba(avcWasmBytes);
if (avcWasmNegative.instance.exports.main() !== 42n)
  throw new Error("ISO-BMFF to H264 Wasm negative result mismatch");
const avcWasm = await host.instantiateKotoba(avcWasmBytes);
if (avcWasm.instance.exports["fixture-check"](avcWasm.typedValues.bytes(bytes)) !== 42n)
  throw new Error("ISO-BMFF to H264 Wasm fixture mismatch");

const avcTypeOffset = bytes.indexOf(Buffer.from("avcC"));
if (avcTypeOffset < 4) throw new Error("avcC fixture box missing");
const payloadOffset = avcTypeOffset + 4;
const mutations = [
  ["unsupported avcC version", payloadOffset, 2],
  ["unsupported SPS count", payloadOffset + 5, 0],
  ["oversized SPS", payloadOffset + 6, 1],
  ["invalid SPS length byte", payloadOffset + 7, 256],
  ["out-of-range avcC box", avcTypeOffset - 4, 127],
];
for (const [label, offset, value] of mutations) {
  const webCandidate = Array.from(bytes, BigInt);
  webCandidate[offset] = BigInt(value);
  if (avcWeb.instantiateKotoba()["reject-check"](webCandidate) !== 42n)
    throw new Error(`Web accepted ${label}`);
  const instance = await host.instantiateKotoba(avcWasmBytes);
  if (value > 255) {
    let sealedHostRejected = false;
    try { instance.typedValues.bytes(webCandidate); }
    catch { sealedHostRejected = true; }
    if (!sealedHostRejected) throw new Error(`Wasm host accepted ${label}`);
  } else {
    const wasmCandidate = Buffer.from(bytes);
    wasmCandidate[offset] = value;
    if (instance.instance.exports["reject-check"](instance.typedValues.bytes(wasmCandidate)) !== 42n)
      throw new Error(`Wasm accepted ${label}`);
  }
}

const imageFixture = Buffer.from([
  0, 0, 0, 20, 102, 116, 121, 112, 97, 118, 105, 102, 0, 0, 0, 0, 97, 118, 105, 102,
  0, 0, 0, 48, 109, 101, 116, 97, 0, 0, 0, 0,
  0, 0, 0, 36, 105, 112, 114, 112,
  0, 0, 0, 28, 105, 112, 99, 111,
  0, 0, 0, 20, 105, 115, 112, 101, 0, 0, 0, 0,
  0, 0, 1, 64, 0, 0, 0, 240,
]);
const imageWeb = await import(pathToFileURL(path.resolve(imageWebPath)));
if (imageWeb.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("image metadata Web graph requested a capability");
if (imageWeb.instantiateKotoba().main() !== 42n)
  throw new Error("image metadata Web main mismatch");
if (imageWeb.instantiateKotoba()["fixture-check"](Array.from(imageFixture, BigInt)) !== 42n)
  throw new Error("image metadata Web fixture mismatch");
const imageWasmBytes = fs.readFileSync(path.resolve(imageWasmPath));
const imageWasmMain = await host.instantiateKotoba(imageWasmBytes);
if (imageWasmMain.instance.exports.main() !== 42n)
  throw new Error("image metadata Wasm main mismatch");
const imageWasmFixture = await host.instantiateKotoba(imageWasmBytes);
if (imageWasmFixture.instance.exports["fixture-check"](
      imageWasmFixture.typedValues.bytes(imageFixture)) !== 42n)
  throw new Error("image metadata Wasm fixture mismatch");

const openDomain = Buffer.from(imageFixture);
openDomain.set(Buffer.from("zzzz"), 8);
openDomain.fill(255, 60, 68);
const openBrand = BigInt(Buffer.from("zzzz").readUInt32BE());
const maxU32 = 4294967295n;
if (imageWeb.instantiateKotoba()["metadata-check"](
      Array.from(openDomain, BigInt), openBrand, maxU32, maxU32) !== 42n)
  throw new Error("Web narrowed the open four-byte brand/u32 dimension domain");
const openWasm = await host.instantiateKotoba(imageWasmBytes);
if (openWasm.instance.exports["metadata-check"](
      openWasm.typedValues.bytes(openDomain), openBrand, maxU32, maxU32) !== 42n)
  throw new Error("Wasm narrowed the open four-byte brand/u32 dimension domain");

const imageMutations = [
  ["missing ftyp", 4, 0],
  ["nonzero ispe flags", 59, 1],
  ["zero width", 63, 0],
  ["truncated ispe", 51, 19],
  ["out-of-range ipco", 43, 127],
];
for (const [label, offset, value] of imageMutations) {
  const candidate = Buffer.from(imageFixture);
  if (label === "zero width") candidate.fill(0, 60, 64);
  else candidate[offset] = value;
  const webCandidate = Array.from(candidate, BigInt);
  if (imageWeb.instantiateKotoba()["reject-check"](webCandidate) !== 42n)
    throw new Error(`image metadata Web accepted ${label}`);
  const instance = await host.instantiateKotoba(imageWasmBytes);
  if (instance.instance.exports["reject-check"](
      instance.typedValues.bytes(candidate)) !== 42n)
    throw new Error(`image metadata Wasm accepted ${label}`);
}
const nonByteImage = Array.from(imageFixture, BigInt);
nonByteImage[56] = 256n;
if (imageWeb.instantiateKotoba()["reject-check"](nonByteImage) !== 42n)
  throw new Error("image metadata Web accepted a non-byte payload");
const nonByteWasm = await host.instantiateKotoba(imageWasmBytes);
let nonByteHostRejected = false;
try { nonByteWasm.typedValues.bytes(nonByteImage); }
catch { nonByteHostRejected = true; }
if (!nonByteHostRejected) throw new Error("image metadata Wasm host accepted a non-byte payload");
let oversizedImageWebRejected = false;
try { imageWeb.instantiateKotoba()["reject-check"](Array(16385).fill(0n)); }
catch { oversizedImageWebRejected = true; }
if (!oversizedImageWebRejected) throw new Error("image metadata Web accepted oversized input");

console.log("isobmff-kotoba: boxes, avcC/SPS, and image metadata Web/Wasm conformance passed");
