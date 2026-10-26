"""x402 client. The protocol, not the wallet.

The loop is: ask without paying, read the terms off the 402, pay, retry with
the proof. This package owns the first, second and fourth steps and injects
the third, so it holds no key and has no cryptography dependency.

See ../../spec/wire.md for the contract both packages implement.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "Policy", "Offer", "Challenge", "Refusal", "Authorization",
    "chain_id_for", "parse_challenge", "select_offer", "random_nonce",
    "build_authorization", "encode_payment_header", "fetch_with_payment",
    "challenge",
    "catalog", "X402Error",
]

CHAIN_IDS = {
    "base": 8453,
    "base-sepolia": 84532,
    "eip155:8453": 8453,
    "eip155:84532": 84532,
}


class X402Error(Exception):
    """Raised when the protocol cannot proceed. Carries `refused` when the
    reason is a policy decision rather than a transport failure."""

    def __init__(self, message: str, refused: str | None = None) -> None:
        super().__init__(message)
        self.refused = refused


@dataclass(frozen=True)
class Policy:
    """What this buyer will pay. Every field is required: a buyer with an empty
    policy pays anything, and defaults here would be a ceiling nobody chose."""

    networks: Sequence[str]
    assets: Sequence[str]
    max_amount: str
    schemes: Sequence[str] = ("exact", "transaction")


Offer = dict
Challenge = dict


@dataclass(frozen=True)
class Refusal:
    refused: str
    detail: str


@dataclass(frozen=True)
class Authorization:
    frm: str
    to: str
    value: str
    valid_after: str
    valid_before: str
    nonce: str

    def to_wire(self) -> dict:
        return {
            "from": self.frm, "to": self.to, "value": self.value,
            "validAfter": self.valid_after, "validBefore": self.valid_before,
            "nonce": self.nonce,
        }


def chain_id_for(network: str) -> int:
    """The chain id for a network name, or a raise.

    Never a default: a wrong chainId in an EIP-712 domain makes a valid
    signature recover a different address, and the payment is rejected as a
    bad signature -- which reads like the buyer's fault.
    """
    try:
        return CHAIN_IDS[network]
    except KeyError:
        raise X402Error(f"unknown x402 network: {network}") from None


def parse_challenge(status: int, body: bytes | str) -> Challenge | None:
    """A 402 body as a challenge, or None.

    None means "not a challenge", which a caller must be able to tell from "a
    challenge with nothing usable in it" -- those need different handling and
    returning the same value for both is how one gets logged as the other.
    """
    if status != 402:
        return None
    try:
        parsed = json.loads(body)
    except Exception:
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("accepts"), list):
        return None
    return parsed


def select_offer(challenge: Challenge, policy: Policy | None) -> Offer | Refusal:
    """The cheapest offer this policy allows, or a refusal naming why.

    NOT `accepts[0]`. A seller listing the same resource on mainnet and on a
    testnet lists them in its own order, and taking the first is how a buyer
    pays real money to rehearse.

    Every failing check is recorded, not just the first: an offer on the wrong
    network usually names that network's token too, and a caller told only
    `network-not-allowed` will fix the network and be refused again.
    """
    if challenge is None:
        # `parse_challenge` returns None for anything that is not a challenge,
        # and being handed that is the "could not measure" case. Raising
        # AttributeError here would report a protocol outcome as a bug in the
        # caller's own code. Measured 2026-09-01 against the live facilitator.
        return Refusal("not-a-challenge", "the response was not a 402 x402 challenge")
    if (policy is None or not policy.networks or not policy.assets
            or not policy.max_amount):
        return Refusal("no-policy", "a buyer without a policy would pay anything")

    reasons: set[str] = set()
    allowed: list[Offer] = []
    for offer in challenge.get("accepts", []):
        failures: list[str] = []
        if offer.get("scheme") not in policy.schemes:
            failures.append("scheme-not-allowed")
        if offer.get("network") not in policy.networks:
            failures.append("network-not-allowed")
        asset = str(offer.get("asset", "")).lower()
        if asset not in {a.lower() for a in policy.assets}:
            failures.append("asset-not-allowed")
        try:
            if int(offer["maxAmountRequired"]) > int(policy.max_amount):
                failures.append("over-budget")
        except (KeyError, TypeError, ValueError):
            failures.append("unparseable-amount")
        reasons.update(failures)
        if not failures:
            allowed.append(offer)

    if not allowed:
        return Refusal(
            "+".join(sorted(reasons)) if reasons else "no-offers",
            f"none of {len(challenge.get('accepts', []))} offer(s) satisfied the policy",
        )
    return min(allowed, key=lambda o: int(o["maxAmountRequired"]))


def random_nonce() -> str:
    return "0x" + secrets.token_hex(32)


def build_authorization(offer: Offer, frm: str, now: int | None = None) -> Authorization:
    now = int(time.time()) if now is None else now
    return Authorization(
        frm=frm,
        to=offer["payTo"],
        value=str(offer["maxAmountRequired"]),
        valid_after="0",
        valid_before=str(now + int(offer.get("maxTimeoutSeconds", 60))),
        nonce=random_nonce(),
    )


def encode_payment_header(payload: Any) -> str:
    return base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")


USER_AGENT = "x402-sdk-python/0.1.0 (+https://github.com/kotoba-lang/x402-sdk)"


def _default_fetch(url: str, method: str, headers: dict, body: bytes | None):
    # A User-Agent, always. urllib sends `Python-urllib/3.x` by default and
    # Cloudflare answers 403 to it -- measured 2026-09-01 against
    # x402.nexus/gateway, which is a Cloudflare Worker. An SDK that cannot
    # reach the facilitator it is written for is not an SDK, and the failure
    # arrives as a 403 that looks like authorisation rather than as a bot rule.
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def fetch_with_payment(
    url: str,
    *,
    policy: Policy,
    sign: Callable[[dict, dict], str],
    address: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | None = None,
    fetch: Callable[..., tuple[int, dict, bytes]] = _default_fetch,
):
    """Fetch a resource, paying if it asks.

    `sign(domain, message) -> "0x..."` is injected: this package holds no key
    and has no cryptography dependency, so the wallet stays wherever its owner
    put it. `domain` is built from the OFFER, never from configuration.

    A non-402 response is returned untouched -- including errors, because a
    500 is the server's answer and swallowing it to retry would hide it.
    """
    headers = dict(headers or {})
    status, res_headers, res_body = fetch(url, method, headers, body)
    challenge = parse_challenge(status, res_body)
    if challenge is None:
        return status, res_headers, res_body

    picked = select_offer(challenge, policy)
    if isinstance(picked, Refusal):
        raise X402Error(f"{picked.refused}: {picked.detail}", refused=picked.refused)
    if picked.get("scheme") != "exact":
        raise X402Error(
            f"this client signs the 'exact' scheme; the offer asks for "
            f"'{picked.get('scheme')}', which needs a transfer this package does not make"
        )
    extra = picked.get("extra") or {}
    if not extra.get("name") or not extra.get("version"):
        raise X402Error(
            "the offer carries no EIP-712 domain (extra.name/version); signing under "
            "a guessed one recovers a different address and is rejected as a bad signature"
        )

    auth = build_authorization(picked, address)
    signature = sign(
        {
            "name": extra["name"],
            "version": extra["version"],
            "chainId": chain_id_for(picked["network"]),
            "verifyingContract": picked["asset"],
        },
        auth.to_wire(),
    )
    headers["X-PAYMENT"] = encode_payment_header({
        "x402Version": challenge.get("x402Version", 1),
        "scheme": "exact",
        "network": picked["network"],
        "payload": {"signature": signature, "authorization": auth.to_wire()},
    })
    return fetch(url, method, headers, body)


def challenge(url: str, *, method: str = "GET",
              fetch: Callable[..., tuple[int, dict, bytes]] = _default_fetch) -> Challenge | None:
    """Ask what a resource costs, without paying.

    The safe first call: no key, no payment, no side effect on the seller. It
    returns the 402 terms, or None when the resource is not gated -- which a
    caller must be able to tell from a gated resource whose terms it could not
    read, so None is only ever "not a challenge".
    """
    status, _, body = fetch(url, method, {}, None)
    return parse_challenge(status, body)


def catalog(origin: str, fetch: Callable[..., tuple[int, dict, bytes]] = _default_fetch) -> Any:
    status, _, body = fetch(origin.rstrip("/") + "/catalog", "GET", {}, None)
    if status != 200:
        raise X402Error(f"catalog returned {status}")
    return json.loads(body)
