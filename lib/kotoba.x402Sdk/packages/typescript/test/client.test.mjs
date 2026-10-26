import { test } from "node:test";
import assert from "node:assert/strict";
import {
  selectOffer, chainIdFor, encodePaymentHeader, buildAuthorization,
  parseChallenge, fetchWithPayment, PaidOutputRejectedError,
} from "../dist/index.js";

const policy = {
  networks: ["base-sepolia"],
  assets: ["0x036CbD53842c5426634e7929541eC2318f3dCF7e"],
  maxAmount: "5000",
};
const offer = (over = {}) => ({
  scheme: "exact", network: "base-sepolia",
  asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
  payTo: "0xA00366234D29d4F882088048c0B2fa0dB7302D4E",
  maxAmountRequired: "1000", maxTimeoutSeconds: 60,
  extra: { name: "USDC", version: "2" }, ...over,
});

test("a buyer without a policy pays nothing", () => {
  const r = selectOffer({ x402Version: 1, accepts: [offer()] }, {});
  assert.equal(r.refused, "no-policy");
});

test("the cheapest allowed offer wins, not the first", () => {
  const c = { x402Version: 1, accepts: [offer({ maxAmountRequired: "4000" }), offer({ maxAmountRequired: "1000" })] };
  assert.equal(selectOffer(c, policy).maxAmountRequired, "1000");
});

test("mainnet is not paid by a testnet policy, and the refusal says which", () => {
  const c = { x402Version: 1, accepts: [offer({ network: "base", asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" })] };
  const r = selectOffer(c, policy);
  assert.match(r.refused, /network-not-allowed/);
  assert.match(r.refused, /asset-not-allowed/);
});

test("over budget is refused as over budget", () => {
  const r = selectOffer({ x402Version: 1, accepts: [offer({ maxAmountRequired: "9999" })] }, policy);
  assert.equal(r.refused, "over-budget");
});

test("an unknown network throws rather than defaulting", () => {
  assert.throws(() => chainIdFor("optimism"), /unknown x402 network/);
  assert.equal(chainIdFor("base-sepolia"), 84532);
  assert.equal(chainIdFor("eip155:8453"), 8453);
});

test("a non-402 response is returned untouched", async () => {
  const res = new Response("ok", { status: 500 });
  assert.equal(await parseChallenge(res), null);
});

test("a 402 that is not JSON is not a challenge", async () => {
  assert.equal(await parseChallenge(new Response("nope", { status: 402 })), null);
});

test("the payment header round-trips", () => {
  const p = { x402Version: 1, scheme: "exact", network: "base-sepolia", payload: { signature: "0x01" } };
  assert.deepEqual(JSON.parse(Buffer.from(encodePaymentHeader(p), "base64").toString("utf8")), p);
});

test("the authorization expires by the offer's own timeout", () => {
  const a = buildAuthorization(offer({ maxTimeoutSeconds: 30 }), "0xabc", 1000);
  assert.equal(a.validBefore, "1030");
  assert.equal(a.validAfter, "0");
  assert.match(a.nonce, /^0x[0-9a-f]{64}$/);
});

test("an offer with no EIP-712 domain is refused rather than guessed", async () => {
  const challenge = { x402Version: 1, accepts: [offer({ extra: undefined })] };
  const fetchImpl = async () => new Response(JSON.stringify(challenge), { status: 402 });
  await assert.rejects(
    fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xabc", signTransferWithAuthorization: async () => "0x00" },
    }),
    /no EIP-712 domain/,
  );
});

test("the signer is handed the offer's own domain, not a configured one", async () => {
  const challenge = { x402Version: 1, accepts: [offer()] };
  let seen = null;
  let calls = 0;
  const fetchImpl = async (_u, init) => {
    calls++;
    if (calls === 1) return new Response(JSON.stringify(challenge), { status: 402 });
    return new Response("paid", { status: 200, headers: { "x-echo": new Headers(init.headers).get("X-PAYMENT") ?? "" } });
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: {
      address: "0xdeadbeef",
      signTransferWithAuthorization: async (args) => { seen = args; return "0xsig"; },
    },
  });
  assert.equal(res.status, 200);
  assert.equal(seen.domain.name, "USDC");
  assert.equal(seen.domain.chainId, 84532);
  assert.equal(seen.domain.verifyingContract, offer().asset);
  assert.equal(seen.message.from, "0xdeadbeef");
  const sent = JSON.parse(Buffer.from(res.headers.get("x-echo"), "base64").toString("utf8"));
  assert.equal(sent.payload.signature, "0xsig");
  assert.equal(sent.scheme, "exact");
});

test("an unparseable amount is named as such, not silently over budget", () => {
  const r = selectOffer({ x402Version: 1, accepts: [offer({ maxAmountRequired: "one dollar" })] }, policy);
  assert.equal(r.refused, "unparseable-amount");
});

test("challenge() returns null for an ungated resource, and terms for a gated one", async () => {
  const { challenge } = await import("../dist/index.js");
  assert.equal(await challenge("https://x/y", undefined, async () => new Response("ok", { status: 200 })), null);
  const c = await challenge("https://x/y", undefined,
    async () => new Response(JSON.stringify({ x402Version: 1, accepts: [offer()] }), { status: 402 }));
  assert.equal(c.accepts.length, 1);
});

test("RESIDUAL on main: invalid paid output is returned with no validation seam", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let calls = 0;
  const fetchImpl = async () => {
    calls++;
    if (calls === 1) return new Response(JSON.stringify(challengeBody), { status: 402 });
    return new Response(JSON.stringify({ wrong: true }), { status: 200 });
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
  });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { wrong: true });
  assert.equal(calls, 2);
});

test("validatePaidOutput accepts valid paid output", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let calls = 0;
  const fetchImpl = async () => {
    calls++;
    if (calls === 1) return new Response(JSON.stringify(challengeBody), { status: 402 });
    return new Response(JSON.stringify({ value: 42 }), { status: 200 });
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
    validatePaidOutput: (view) => {
      const data = view.json();
      if (typeof data?.value !== "number") throw new Error("missing value");
    },
  });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { value: 42 });
  assert.equal(calls, 2);
});

test("validatePaidOutput rejects malformed output without retry or extra payment", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let calls = 0;
  let paidResponse;
  const fetchImpl = async () => {
    calls++;
    if (calls === 1) return new Response(JSON.stringify(challengeBody), { status: 402 });
    paidResponse = new Response("not-json", { status: 200 });
    return paidResponse;
  };
  await assert.rejects(
    fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
      validatePaidOutput: (view) => { view.json(); },
    }),
    (err) => {
      assert.ok(err instanceof PaidOutputRejectedError);
      assert.equal(calls, 2);
      assert.equal(err.response, paidResponse);
      assert.equal(err.attemptEvidence.signature, "0xsig");
      assert.equal(err.attemptEvidence.scheme, "exact");
      return true;
    },
  );
});

test("validatePaidOutput preserves attempt evidence and response when validator mutates the view", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let paidResponse;
  const fetchImpl = async (_u, init) => {
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    paidResponse = new Response(JSON.stringify({ ok: true }), { status: 200 });
    return paidResponse;
  };
  let err;
  try {
    await fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
      validatePaidOutput: (view) => {
        view.body[0] = 0x7b;
        throw new Error("hostile");
      },
    });
  } catch (e) {
    err = e;
  }
  assert.ok(err instanceof PaidOutputRejectedError);
  assert.equal(err.response, paidResponse);
  assert.equal(await err.response.text(), '{"ok":true}');
  assert.equal(err.attemptEvidence.signature, "0xsig");
});

test("payment attempt evidence preserves all extra fields detached, deeply immutable, and hostile-safe", async () => {
  const extraFromChallenge = JSON.parse(
    '{"name":"USDC","version":"2","sellerTag":"alpha","nested":{"depth":1,"tags":["a","b"]},"__proto__":{"polluted":true}}',
  );
  const pickedOffer = offer({ extra: extraFromChallenge });
  const challengeBody = { x402Version: 1, accepts: [pickedOffer] };
  const originalExtra = challengeBody.accepts[0].extra;
  const fetchImpl = async (_u, init) => {
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  let err;
  try {
    await fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
      validatePaidOutput: (view) => {
        view.attemptEvidence.offer.extra.name = "tampered";
        view.attemptEvidence.offer.extra.sellerTag = "tampered";
        view.attemptEvidence.offer.extra.nested.depth = 9;
        view.attemptEvidence.offer.extra.nested.tags[0] = "z";
        view.attemptEvidence.offer.extra["__proto__"] = { polluted: false };
        throw new Error("hostile extra");
      },
    });
  } catch (e) {
    err = e;
  }
  assert.ok(err instanceof PaidOutputRejectedError);
  assert.notEqual(err.attemptEvidence.offer.extra, originalExtra);
  assert.equal(
    JSON.stringify(err.attemptEvidence.offer.extra),
    '{"name":"USDC","version":"2","sellerTag":"alpha","nested":{"depth":1,"tags":["a","b"]},"__proto__":{"polluted":true}}',
  );
  assert.equal(err.attemptEvidence.offer.extra["__proto__"].polluted, true);
  assert.equal(originalExtra.sellerTag, "alpha");
  assert.equal(originalExtra.nested.depth, 1);
  assert.equal(originalExtra.nested.tags[0], "a");
  assert.equal(Object.prototype.polluted, undefined);
  assert.throws(() => {
    err.attemptEvidence.offer.extra.nested.depth = 9;
  }, TypeError);
  assert.throws(() => {
    err.attemptEvidence.offer.extra.nested.tags.push("c");
  }, TypeError);
});

test("validatePaidOutput retains original attempt evidence when validator mutates nested fields", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  const fetchImpl = async (_u, init) => {
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  let err;
  try {
    await fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
      validatePaidOutput: (view) => {
        view.attemptEvidence.offer.extra.name = "tampered";
        view.attemptEvidence.authorization.from = "0xtampered";
        throw new Error("hostile nested");
      },
    });
  } catch (e) {
    err = e;
  }
  assert.ok(err instanceof PaidOutputRejectedError);
  assert.equal(err.attemptEvidence.offer.extra.name, "USDC");
  assert.equal(err.attemptEvidence.authorization.from, "0xdeadbeef");
  assert.equal(err.attemptEvidence.signature, "0xsig");
});

test("validatePaidOutput returns the original paid response on success", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let paidResponse;
  const fetchImpl = async (_u, init) => {
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    paidResponse = new Response(JSON.stringify({ value: 1 }), {
      status: 200,
      statusText: "OK",
    });
    return paidResponse;
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
    validatePaidOutput: () => {},
  });
  assert.equal(res, paidResponse);
  assert.equal(res.statusText, "OK");
});

test("validatePaidOutput is not invoked for a terminal second 402", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let calls = 0;
  let validated = false;
  const fetchImpl = async (_u, init) => {
    calls++;
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    return new Response(JSON.stringify({ still: "gated" }), { status: 402 });
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
    validatePaidOutput: () => { validated = true; },
  });
  assert.equal(res.status, 402);
  assert.equal(validated, false);
  assert.equal(calls, 2);
});

test("validatePaidOutput is not invoked for a post-payment application error", async () => {
  const challengeBody = { x402Version: 1, accepts: [offer()] };
  let calls = 0;
  let validated = false;
  const fetchImpl = async (_u, init) => {
    calls++;
    if (!init?.headers?.get?.("X-PAYMENT")) {
      return new Response(JSON.stringify(challengeBody), { status: 402 });
    }
    return new Response("server fault", { status: 500 });
  };
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xdeadbeef", signTransferWithAuthorization: async () => "0xsig" },
    validatePaidOutput: () => { validated = true; },
  });
  assert.equal(res.status, 500);
  assert.equal(await res.text(), "server fault");
  assert.equal(validated, false);
  assert.equal(calls, 2);
});

test("validatePaidOutput is not invoked for free initial success", async () => {
  let validated = false;
  const fetchImpl = async () => new Response("free", { status: 200 });
  const res = await fetchWithPayment("https://x/y", undefined, {
    policy, fetchImpl,
    signer: { address: "0xabc", signTransferWithAuthorization: async () => "0x00" },
    validatePaidOutput: () => { validated = true; },
  });
  assert.equal(await res.text(), "free");
  assert.equal(validated, false);
});

test("validatePaidOutput is not invoked when policy refuses before payment", async () => {
  let validated = false;
  const fetchImpl = async () =>
    new Response(JSON.stringify({ x402Version: 1, accepts: [offer({ maxAmountRequired: "99999" })] }), { status: 402 });
  await assert.rejects(
    fetchWithPayment("https://x/y", undefined, {
      policy, fetchImpl,
      signer: { address: "0xabc", signTransferWithAuthorization: async () => "0x00" },
      validatePaidOutput: () => { validated = true; },
    }),
  );
  assert.equal(validated, false);
});
