import { Grant } from "./provider-capability.mjs";

function authorize(grant, operation) {
  if (!(grant instanceof Grant) || grant.operation !== operation) throw "provider-failed";
}

export function sign(grant, request) {
  authorize(grant, "identity/sign");
  if (!(request?.bytes instanceof Uint8Array) ||
      new TextDecoder().decode(request.bytes) !== "payload") throw "provider-failed";
  return { bytes: Uint8Array.from([1, 2, 3]) };
}

export function verify(grant, request) {
  authorize(grant, "identity/verify");
  if (!(request?.bytes instanceof Uint8Array) ||
      new TextDecoder().decode(request.bytes) !== "signed") throw "provider-failed";
  return true;
}
