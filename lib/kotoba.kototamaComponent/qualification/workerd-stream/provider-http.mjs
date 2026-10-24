import { BytesTask, Grant } from "./provider-capability.mjs";

export function getStream(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== "http/get-stream") {
    throw "provider-failed";
  }
  if (request?.path !== "/data" || !Array.isArray(request.headers) ||
      request.headers.length !== 0) {
    throw "provider-failed";
  }
  return new BytesTask(Uint8Array.from([1, 2, 3, 4, 5, 6]));
}
