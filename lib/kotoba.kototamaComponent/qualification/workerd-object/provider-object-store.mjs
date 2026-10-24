import { BytesTask, Grant } from "./provider-capability.mjs";

function authorize(grant, operation) {
  if (!(grant instanceof Grant) || grant.operation !== operation) {
    throw "provider-failed";
  }
}

export function getStream(grant, request) {
  authorize(grant, "object/get-stream");
  if (request?.key !== "blocks/key") throw "provider-failed";
  return new BytesTask(Uint8Array.from([7, 8, 9, 10]));
}

export function putBlock(grant, request) {
  authorize(grant, "object/put-block");
  if (request?.key !== "blocks/hash" ||
      !(request.bytes instanceof Uint8Array) ||
      new TextDecoder().decode(request.bytes) !== "payload") {
    throw "provider-failed";
  }
}

export function compareAndSetRef(grant, request) {
  authorize(grant, "object/compare-and-set-ref");
  if (request?.key !== "refs/main" || request.expectedEtag !== "etag-1" ||
      !(request.bytes instanceof Uint8Array) ||
      new TextDecoder().decode(request.bytes) !== "next") {
    throw "provider-failed";
  }
  return { won: true, etag: "etag-2" };
}
