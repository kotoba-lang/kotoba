import { Grant } from "./provider-capability.mjs";

export function sha256(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== "hash/sha256" ||
      !(request?.bytes instanceof Uint8Array) ||
      new TextDecoder().decode(request.bytes) !== "payload") throw "provider-failed";
  return { bytes: Uint8Array.from(Array.from({ length: 32 }, (_, index) => index)) };
}
