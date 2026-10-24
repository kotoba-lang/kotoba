import { Grant } from "./provider-capability.mjs";

export function append(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== "log/append") {
    throw "provider-failed";
  }
  if (!(request?.bytes instanceof Uint8Array)) {
    throw "provider-failed";
  }
  if (new TextDecoder().decode(request.bytes) !== "安全") {
    throw "provider-failed";
  }
}
