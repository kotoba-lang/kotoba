# Announcement drafts (HN / Reddit / Base) — DRAFT, not submitted

**Status: draft, awaiting owner review.** These are prepared per ADR-0002
(`gftdcojp/nexus-x402/docs/adr/0002-external-facilitator-gtm-plan.md`)
step 4 ("content/positioning"). Per that ADR's own explicit boundary,
**submission is an owner-executed action, not something carried out on
the owner's behalf** — nothing here has been posted anywhere. Edit freely
before use; none of this copy is final.

**Honesty constraints these drafts follow** (matching this codebase's
"never fabricate" rule, see `x402-directory`'s README and test suite):
no invented user counts, no claimed "customers" (the 3 registered sellers
— murakumo, kotobase, shinshi — are the same team's own products, i.e.
dogfooding, not external paying customers — every draft below says so
explicitly), no fake urgency/testimonials. Every factual claim below was
verified live (curl'd against `x402.nexus`) as of 2026-07-10.

---

## Hacker News — "Show HN"

**Title** (80 char limit, pick one):
- `Show HN: x402-directory – open directory UI for x402 payment facilitators`
- `Show HN: I self-hosted an x402 facilitator instead of Cloudflare's waitlist`

**Body**:

> Cloudflare announced a Monetization Gateway built on x402 (HTTP 402
> Payment Required as an agent-native micropayment rail — a resource
> returns a 402 with price/asset/recipient, the buyer — human or
> autonomous agent — pays in USDC and retries with proof). Their gateway
> is a closed waitlist, and I didn't want to wait or be locked into one
> vendor for something that's supposed to be an open protocol.
>
> So I self-hosted the facilitator instead. It's live at
> [x402.nexus](https://x402.nexus) — no waitlist, keyless on-chain
> verification (Base JSON-RPC, no paid explorer API), and holds no keys
> or funds (payment settles straight to each seller's own treasury). It's
> currently gating 3 of my own other projects (an LLM inference API, an
> IPFS storage gateway, and a paid-content endpoint) — not external
> customers yet, just dogfooding to prove the facilitator itself works
> before opening it up further.
>
> The reusable part I'm open-sourcing today is the directory UI: any
> x402 facilitator already serves a JSON `/catalog` so agents can discover
> what they can pay for, but there was no off-the-shelf way to render that
> as a human-readable page. `x402-directory` does that — pure
> Clojure/ClojureScript, zero dependencies, works with any x402
> `/catalog` shape, MIT^H^H Apache-2.0:
> https://github.com/kotoba-lang/x402-directory (you can see it live at
> https://x402.nexus/).
>
> The underlying protocol codec and on-chain verification are also
> already open: https://github.com/kotoba-lang/pay and
> https://github.com/kotoba-lang/treasury.
>
> Curious what other agent-payment infra people are building on x402 —
> happy to answer questions about the facilitator design (no-custody,
> no admin auth needed for the read paths, KV-backed dynamic seller
> registry).

*(Note: the em-dash-strikethrough "MIT^H^H Apache-2.0" joke should
probably be cut for a wider HN audience unless the poster's voice
matches that style — flagging as optional, not a recommendation.)*

---

## Reddit

**r/Clojure** (the stack itself is genuinely on-topic there and this sub
skews toward "show me real production Clojure/ClojureScript", not hype):

**Title**: `Extracted a small pure .cljc lib from a Cloudflare Worker — HTML renderer for x402 payment-facilitator catalogs`

**Body**:

> Been running a self-hosted [x402](https://blog.cloudflare.com/monetization-gateway/)
> (HTTP 402 micropayment protocol) facilitator on Cloudflare Workers —
> ClojureScript via shadow-cljs. Pulled the HTML directory-page renderer
> out into a standalone `.cljc` library since it turned out to be entirely
> pure string-building with zero host interop, so it made sense as its own
> thing rather than staying vendored:
> https://github.com/kotoba-lang/x402-directory
>
> Nothing fancy — takes a seq of `{:seller :method :price ...}` maps and a
> branding config, returns an HTML string. What I liked about doing this
> extraction: the test suite (written for the vendored version) ported
> over with zero changes to the assertions, just the require. Testable
> without a Workers runtime the whole way through.
>
> Live example (the facilitator this was extracted from):
> https://x402.nexus/ — currently fronting 3 of my own projects, not
> taking external traffic yet.

**r/ethereum** or **r/ethdev** (Base/USDC settlement angle, more relevant
than general crypto subs — check current sub rules on self-promotion
before posting, some ban it entirely):

**Title**: `Self-hosted x402 (agent-native micropayment) facilitator — USDC on Base, no custody, no admin auth for reads`

**Body**:

> x402 is the protocol behind Cloudflare's new Monetization Gateway: a
> 402 response carries price/asset/recipient, the payer (human or
> autonomous agent) sends USDC and retries with the tx as proof. Cloudflare's
> own facilitator is a waitlist, so I self-hosted mine on Cloudflare
> Workers: https://x402.nexus
>
> - No custody — the facilitator only verifies, payment settles directly
>   to each seller's own treasury address.
> - Keyless on-chain verification — plain Base JSON-RPC
>   (`eth_getTransactionReceipt` + `eth_blockNumber`), no paid explorer
>   API key.
> - `GET /catalog` — agent-discoverable JSON menu of everything gated
>   across every registered seller (price, asset, network, gateway URL).
> - `GET /stats` — aggregate-only settlement counts, no auth needed.
>
> Currently gating 3 of my own projects (dogfooding — no external sellers
> yet). Protocol libraries (`pay`, `treasury`) are Apache-2.0:
> https://github.com/kotoba-lang/pay /
> https://github.com/kotoba-lang/treasury

---

## Base / Coinbase developer community

(Base Discord #showcase-style channel, or Base's Discourse/forum if one
exists at time of posting — verify the current venue before using this,
communities restructure.)

**Message**:

> Built a self-hosted x402 payment facilitator on Base — live at
> https://x402.nexus. x402 is the "HTTP 402 as an agent-native
> micropayment rail" protocol Cloudflare's Monetization Gateway
> standardizes (closed waitlist there; this is the open protocol,
> self-hosted, live today).
>
> USDC settlement on Base, keyless verification (plain JSON-RPC, no paid
> explorer API), zero custody — funds go straight to each seller's own
> treasury, the facilitator only verifies and never holds keys.
> `GET /catalog` gives any agent a JSON menu of what it can pay for across
> every registered seller.
>
> Currently fronting 3 of my own projects as a dogfood/proof-of-concept,
> not open to external sellers yet. Sharing mainly because I'd be curious
> whether other people building agent-payment flows on Base have run into
> the same "wait for Cloudflare's waitlist or roll your own" choice, and
> what they picked.
>
> Protocol libs are open if useful to anyone else building on x402/Base:
> https://github.com/kotoba-lang/pay · https://github.com/kotoba-lang/treasury
> · https://github.com/kotoba-lang/x402-directory (directory-page UI).

---

## Before posting (checklist for whoever submits these)

- [ ] Re-verify every URL still resolves and every stat is still current
      (traffic/seller counts change — re-curl `x402.nexus/stats` and
      `/catalog` before submitting, don't reuse stale numbers).
- [ ] Confirm `gftdcojp/nexus-x402` is still intentionally private (ADR-0002)
      before implying anywhere that the facilitator's *source* is open —
      only `kotoba-lang/pay`, `kotoba-lang/treasury`, and
      `kotoba-lang/x402-directory` are.
- [ ] Check each community's current self-promotion rules (HN's Show HN
      guidelines, each subreddit's rules, Base's community guidelines) —
      they change and weren't re-verified as part of writing this draft.
- [ ] Post from an account with enough standing history that the post
      doesn't read as a fresh single-purpose promotional account.
