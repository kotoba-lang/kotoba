import { Grant } from "./provider-capability.mjs";

export function read(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== "log/read" ||
      request?.cursor !== 0n || request.maxBytes !== 128) throw "provider-failed";
  return { nextCursor: 4n, bytes: Uint8Array.from([9, 8, 7, 6]) };
}
