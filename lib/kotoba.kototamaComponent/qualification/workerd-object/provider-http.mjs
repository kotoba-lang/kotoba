import { Grant } from "./provider-capability.mjs";

export function post(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== "http/post" ||
      request?.path !== "/safe" || !Array.isArray(request.headers) ||
      !(request.body instanceof Uint8Array) ||
      new TextDecoder().decode(request.body) !== "body") throw "provider-failed";
  return { status: 202, headers: [], body: new Uint8Array() };
}
