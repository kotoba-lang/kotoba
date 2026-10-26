/**
 * x402 client. The protocol, not the wallet.
 *
 * The loop is: ask without paying, read the terms off the 402, pay, retry with
 * the proof. This library owns the first, second and fourth steps and injects
 * the third, so it holds no key and has no cryptography dependency.
 *
 * See ../../spec/wire.md for the contract both packages implement.
 */

export type Scheme = "exact" | "transaction";

export interface Offer {
  scheme: Scheme;
  network: string;
  asset: string;
  payTo: string;
  maxAmountRequired: string;
  maxTimeoutSeconds?: number;
  resource?: string;
  description?: string;
  /** The EIP-712 domain of `asset` on `network`. Never a constant. */
  extra?: { name: string; version: string; [k: string]: unknown };
}

export interface Challenge {
  x402Version: number;
  accepts: Offer[];
  error?: string;
}

export interface Policy {
  /** Networks this buyer will pay on. Required: an empty policy pays anything. */
  networks: string[];
  /** Token contracts this buyer will pay in, lowercased on comparison. */
  assets: string[];
  /** Ceiling per call, in the token's smallest unit, as a decimal string. */
  maxAmount: string;
  schemes?: Scheme[];
}

export interface Authorization {
  from: string;
  to: string;
  value: string;
  validAfter: string;
  validBefore: string;
  nonce: string;
}

/** What a caller must supply. The key never enters this library. */
export interface Signer {
  /** The address the authorization is `from`. */
  address: string;
  /**
   * Sign an EIP-712 TransferWithAuthorization and return `0x…` (65 bytes).
   * `domain` comes from the offer, never from configuration.
   */
  signTransferWithAuthorization(args: {
    domain: { name: string; version: string; chainId: number; verifyingContract: string };
    message: Authorization;
  }): Promise<string>;
}

export interface Refusal {
  refused: string;
  detail: string;
}

const CHAIN_IDS: Record<string, number> = {
  base: 8453,
  "base-sepolia": 84532,
  "eip155:8453": 8453,
  "eip155:84532": 84532,
};

/** The chain id for a network name, or a throw. Never a default: a wrong
 * chainId in an EIP-712 domain makes a valid signature recover a different
 * address, and the payment is rejected as a bad signature. */
export function chainIdFor(network: string): number {
  const id = CHAIN_IDS[network];
  if (id === undefined) throw new Error(`unknown x402 network: ${network}`);
  return id;
}

/** Parse a 402 response. Returns null when the response is not a challenge —
 * callers must be able to tell "not a 402" from "a 402 with nothing usable". */
export async function parseChallenge(res: Response): Promise<Challenge | null> {
  if (res.status !== 402) return null;
  let body: unknown;
  try {
    body = await res.clone().json();
  } catch {
    return null;
  }
  const c = body as Challenge;
  if (!c || !Array.isArray(c.accepts)) return null;
  return c;
}

function isRefusal(x: Offer | Refusal): x is Refusal {
  return (x as Refusal).refused !== undefined;
}

/**
 * The cheapest offer this policy allows, or a refusal naming why.
 *
 * NOT `accepts[0]`. A seller listing the same resource on mainnet and on a
 * testnet lists them in its own order, and taking the first is how a buyer
 * pays real money to rehearse. Refusals are named individually so a caller can
 * tell an over-budget offer from an unsupported network.
 */
export function selectOffer(challenge: Challenge, policy: Policy): Offer | Refusal {
  if (!policy || !policy.networks?.length || !policy.assets?.length || !policy.maxAmount) {
    return { refused: "no-policy", detail: "a buyer without a policy would pay anything" };
  }
  const schemes = policy.schemes ?? ["exact", "transaction"];
  const reasons = new Set<string>();
  // Every failing check is recorded, not just the first. An offer on the wrong
  // network usually names the wrong network's token too, and a caller told
  // only `network-not-allowed` will fix the network and be refused again.
  const allowed = challenge.accepts.filter((o) => {
    const failures: string[] = [];
    if (!schemes.includes(o.scheme)) failures.push("scheme-not-allowed");
    if (!policy.networks.includes(o.network)) failures.push("network-not-allowed");
    if (!policy.assets.some((a) => a.toLowerCase() === String(o.asset).toLowerCase())) {
      failures.push("asset-not-allowed");
    }
    let amountOk = false;
    try {
      amountOk = BigInt(o.maxAmountRequired) <= BigInt(policy.maxAmount);
    } catch {
      failures.push("unparseable-amount");
    }
    if (!amountOk && !failures.includes("unparseable-amount")) failures.push("over-budget");
    failures.forEach((f) => reasons.add(f));
    return failures.length === 0;
  });
  if (!allowed.length) {
    return {
      refused: reasons.size ? [...reasons].sort().join("+") : "no-offers",
      detail: `none of ${challenge.accepts.length} offer(s) satisfied the policy`,
    };
  }
  return allowed.sort((a, b) =>
    BigInt(a.maxAmountRequired) < BigInt(b.maxAmountRequired) ? -1 : 1)[0];
}

/** A 32-byte hex nonce. */
export function randomNonce(): string {
  const b = new Uint8Array(32);
  (globalThis.crypto as Crypto).getRandomValues(b);
  return "0x" + [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

export function buildAuthorization(
  offer: Offer,
  from: string,
  nowSeconds: number = Math.floor(Date.now() / 1000),
): Authorization {
  return {
    from,
    to: offer.payTo,
    value: offer.maxAmountRequired,
    validAfter: "0",
    validBefore: String(nowSeconds + (offer.maxTimeoutSeconds ?? 60)),
    nonce: randomNonce(),
  };
}

export function encodePaymentHeader(payload: unknown): string {
  const json = JSON.stringify(payload);
  // btoa is not defined everywhere and does not handle non-ASCII; Buffer is
  // not defined in workers. Encode explicitly rather than assuming either.
  const bytes = new TextEncoder().encode(json);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return typeof btoa === "function"
    ? btoa(bin)
    : // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any).Buffer.from(json, "utf8").toString("base64");
}

/**
 * Evidence from the paid retry attempt: signed authorization and payment header
 * sent on the retry. The library does not observe or verify on-chain settlement.
 */
export interface PaymentAttemptEvidence {
  readonly x402Version: number;
  readonly scheme: "exact";
  readonly network: string;
  readonly offer: Readonly<Offer>;
  readonly authorization: Readonly<Authorization>;
  readonly signature: string;
  readonly paymentHeader: string;
}

function detachJsonValue(value: unknown): unknown {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    return Object.freeze(value.map((item) => detachJsonValue(item)));
  }
  const detached = Object.create(null) as Record<string, unknown>;
  for (const key of Object.keys(value as object)) {
    detached[key] = detachJsonValue((value as Record<string, unknown>)[key]);
  }
  return Object.freeze(detached);
}

function detachOffer(offer: Offer): Readonly<Offer> {
  const extra =
    offer.extra !== undefined
      ? (detachJsonValue(offer.extra) as Readonly<Offer>["extra"])
      : undefined;
  return Object.freeze({
    scheme: offer.scheme,
    network: offer.network,
    asset: offer.asset,
    payTo: offer.payTo,
    maxAmountRequired: offer.maxAmountRequired,
    ...(offer.maxTimeoutSeconds !== undefined
      ? { maxTimeoutSeconds: offer.maxTimeoutSeconds }
      : {}),
    ...(offer.resource !== undefined ? { resource: offer.resource } : {}),
    ...(offer.description !== undefined ? { description: offer.description } : {}),
    ...(extra !== undefined ? { extra } : {}),
  });
}

function detachAuthorization(authorization: Authorization): Readonly<Authorization> {
  return Object.freeze({ ...authorization });
}

function buildPaymentAttemptEvidence(args: {
  x402Version: number;
  network: string;
  offer: Offer;
  authorization: Authorization;
  signature: string;
  paymentHeader: string;
}): PaymentAttemptEvidence {
  return Object.freeze({
    x402Version: args.x402Version,
    scheme: "exact",
    network: args.network,
    offer: detachOffer(args.offer),
    authorization: detachAuthorization(args.authorization),
    signature: args.signature,
    paymentHeader: args.paymentHeader,
  });
}

/**
 * Detached view of a successful paid application response. The body is a copy;
 * helpers read it without touching the Response returned to the caller.
 */
export interface PaidOutputView {
  readonly status: number;
  readonly headers: Readonly<Record<string, string>>;
  readonly body: Uint8Array;
  readonly attemptEvidence: PaymentAttemptEvidence;
  text(): string;
  json(): unknown;
}

export type ValidatePaidOutput = (view: PaidOutputView) => void | Promise<void>;

/** Thrown when `validatePaidOutput` rejects the paid body. No retry occurs. */
export class PaidOutputRejectedError extends Error {
  readonly response: Response;
  readonly attemptEvidence: PaymentAttemptEvidence;

  constructor(message: string, response: Response, attemptEvidence: PaymentAttemptEvidence) {
    super(message);
    this.name = "PaidOutputRejectedError";
    this.response = response;
    this.attemptEvidence = attemptEvidence;
  }
}

export interface PayOptions {
  policy: Policy;
  signer: Signer;
  fetchImpl?: typeof fetch;
  /**
   * Optional caller-owned validation of a successful paid application response.
   * The library signs and retries; it does not verify on-chain settlement or
   * response validity beyond what this hook checks.
   */
  validatePaidOutput?: ValidatePaidOutput;
}

/**
 * Fetch a resource, paying if it asks.
 *
 * A non-402 response is returned untouched -- including errors, because a 500
 * is the server's answer and swallowing it to retry would hide it.
 */
export async function fetchWithPayment(
  input: string | URL | Request,
  init: RequestInit | undefined,
  opts: PayOptions,
): Promise<Response> {
  const f = opts.fetchImpl ?? fetch;
  const first = await f(input as RequestInfo, init);
  const challenge = await parseChallenge(first);
  if (!challenge) return first;

  const picked = selectOffer(challenge, opts.policy);
  if (isRefusal(picked)) {
    throw Object.assign(new Error(`x402: ${picked.refused}: ${picked.detail}`), picked);
  }
  if (picked.scheme !== "exact") {
    throw new Error(
      `x402: this client signs the 'exact' scheme; the offer asks for '${picked.scheme}', ` +
        `which needs a transfer this library does not make`,
    );
  }
  const extra = picked.extra;
  if (!extra?.name || !extra?.version) {
    throw new Error(
      "x402: the offer carries no EIP-712 domain (extra.name/version); signing " +
        "under a guessed one recovers a different address and is rejected as a bad signature",
    );
  }

  const authorization = buildAuthorization(picked, opts.signer.address);
  const signature = await opts.signer.signTransferWithAuthorization({
    domain: {
      name: extra.name,
      version: extra.version,
      chainId: chainIdFor(picked.network),
      verifyingContract: picked.asset,
    },
    message: authorization,
  });

  const x402Version = challenge.x402Version ?? 1;
  const header = encodePaymentHeader({
    x402Version,
    scheme: "exact",
    network: picked.network,
    payload: { signature, authorization },
  });
  const headers = new Headers(init?.headers);
  headers.set("X-PAYMENT", header);
  const paid = await f(input as RequestInfo, { ...init, headers });
  const validate = opts.validatePaidOutput;
  if (!validate || !paid.ok) return paid;

  const attemptEvidence = buildPaymentAttemptEvidence({
    x402Version,
    network: picked.network,
    offer: picked,
    authorization,
    signature,
    paymentHeader: header,
  });

  let body: Uint8Array;
  try {
    body = new Uint8Array(await paid.clone().arrayBuffer());
  } catch {
    throw new PaidOutputRejectedError(
      "x402: paid response body is not readable",
      paid,
      attemptEvidence,
    );
  }

  const viewBody = body.slice();
  const headerRecord: Record<string, string> = {};
  paid.headers.forEach((value, key) => {
    headerRecord[key] = value;
  });
  Object.freeze(headerRecord);

  const view: PaidOutputView = Object.freeze({
    status: paid.status,
    headers: headerRecord,
    body: viewBody,
    attemptEvidence,
    text: () => new TextDecoder().decode(viewBody),
    json: () => JSON.parse(new TextDecoder().decode(viewBody)),
  });

  try {
    await validate(view);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "x402: paid application output rejected";
    throw new PaidOutputRejectedError(message, paid, attemptEvidence);
  }

  return paid;
}

/**
 * Ask what a resource costs, without paying.
 *
 * The safe first call: no key, no payment, no side effect on the seller. It
 * returns the 402 terms, or null when the resource is not gated -- which a
 * caller must be able to tell from a gated resource whose terms it could not
 * read, so null is only ever "not a challenge".
 */
export async function challenge(
  url: string,
  init?: RequestInit,
  fetchImpl: typeof fetch = fetch,
): Promise<Challenge | null> {
  return parseChallenge(await fetchImpl(url, init));
}

/** GET /catalog from a facilitator. */
export async function catalog(origin: string, fetchImpl: typeof fetch = fetch) {
  const res = await fetchImpl(`${origin.replace(/\/$/, "")}/catalog`);
  if (!res.ok) throw new Error(`x402: catalog returned ${res.status}`);
  return res.json();
}
