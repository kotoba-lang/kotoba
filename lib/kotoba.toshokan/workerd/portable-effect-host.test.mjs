import assert from "node:assert/strict";
import { dispatchPortableEffect } from "./portable-effect-host.mjs";

const request = {
  format: "kotoba.portable-effect/v1",
  id: "ndl-test-1",
  call: "toshokan/fetch",
  effects: ["host/http"],
  ability: {
    kind: "host/http",
    resource: "library:ndl",
    target: "toshokan/http",
    operation: "get",
    limits: { maxBytes: 2097152, maxItems: 20, deadlineMs: 30000 },
    auditId: "ndl-test-1"
  },
  input: {
    method: "GET",
    url: "https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve",
    headers: { "User-Agent": "toshokan-test" }
  }
};

let calls = 0;
const policy = {
  ndlScopeAdmitted: () => 1n,
  ndlLimitsAdmitted: () => 1n
};
const granted = await dispatchPortableEffect(request, {
  policy,
  now: () => "2026-07-25T00:00:00Z",
  fetchImpl: async () => {
    calls += 1;
    return new Response("<searchRetrieveResponse/>", {
      status: 200,
      headers: { "content-type": "application/xml" }
    });
  }
});
assert.equal(granted.ok, true);
assert.equal(calls, 1);
assert.equal(granted.receipt.outcome, "ok");

console.log("workerd portable effect adapter smoke: ok");
