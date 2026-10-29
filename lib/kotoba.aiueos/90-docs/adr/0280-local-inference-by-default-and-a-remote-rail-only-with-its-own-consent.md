# ADR-0280 — Local inference by default; a remote rail only with its own consent (W7)

Date: 2026-10-28

## Status

Proposed (design only, nothing in this ADR is implemented). W7 of ADR-0275: "local inference by default; a remote rail needs its own
consent". It applies the workspace's shared architecture contract (inference runs in the user's environment; downloading a model never
authorises sending a prompt) to the native desktop. It creates no capability, no rail and no trust root. Every row is `:spec` until its gate
prints green. Owner questions are listed at the end.

## Facts this design starts from

- The native desktop's consent panel already carries the local-model request as static text (kotoba#927 and later): "Service: local model /
  Endpoint: none, runs here / Action: run one local call / Data: Goal text". The Allow stops the desktop loop with the approved request; the
  Itonami turn itself is tracked by JUN-414 (an Amu-built user program run at CPL3) and JUN-444 (the canonical `:llm/generate` kit and host).
- The desktop has no network driver (W8: it emits nothing, measured by the idle gate, kotoba#941); W4 will add one that is off by default.
- Two CLIs, two rails (workspace AGENTS.md and itonami-agent): the itonami agent CLI's `:inference` rails (murakumo, mishima) are for itonami
  profiles only; Hermes profiles never use them. The OS desktop is neither; it has no remote rail today.

## Decisions

1. **Local is the default and needs no network.** The inference call runs inside the user's machine; with the network driver absent or off it
   emits no frame. The local request keeps its own consent (the existing panel); Deny runs nothing.
2. **A remote rail is a different operation, never a fallback.** If the local call cannot run (no model, no fuel, a refusal), the desktop shows
   the reason and stops. It does not retry remotely. A remote call is offered as a separate request the user starts, with its own consent panel:
   Service "remote inference", Endpoint the **full origin** of the rail (not a label), Action "send the text to a remote model", Data the exact
   categories sent (the Goal text; never conversation history unless that category is shown and approved on its own). Denial sends nothing; an
   approval covers that one operation, that endpoint and those categories (ADR-0275 W1 semantics, nothing persists).
3. **No rail ships enabled.** The OS image contains no configured remote rail. A rail is added by the user (an origin, shown in full in every
   consent) and the list is empty by default. Whether the project's own rails (murakumo, mishima) are offered to Itonami OS users is an owner
   decision: they are external services, so they obey this ADR like any other rail, and they stay out of Hermes profiles.
4. **Model download is its own operation.** Fetching a model is an external operation (service, endpoint origin, data categories "none sent,
   bytes received"); its approval never authorises sending a prompt, and a prompt approval never authorises a download. Models are pinned by
   an immutable source revision and verified against a digest before they are used; a missing digest is recorded as unverified and the
   qualification stays open (shared contract). Needs W4 (network, scheme/driver) and W5 (descriptor text).
5. **The consent text is data the user can read in full.** Long origins or category lists that do not fit the panel are refused, not truncated
   (ADR-0278 decision 7), so an approval can never hide where the text goes.
6. **Limits and fuel are shown.** A remote call carries a bounded size and the local call a fuel bound; both are stated in the panel and
   enforced by the runtime, so "one call" is one call.

## What the gates must show (each with a negative control)

(a) a local call with the network driver off emits no frame (the W8 capture, extended to a call in progress); (b) a remote request without
consent emits no frame and, denied, none either; (c) a local failure produces no remote frame (no silent fallback; the capture stays empty);
(d) the remote panel shows the endpoint origin in full (pixel check against the descriptor) and refuses an over-long origin; (e) a download
approval does not permit a prompt frame and a prompt approval does not permit a download; (f) a model whose digest does not match is not used;
(g) approving one remote operation does not cover a second one. QEMU TCG with a captured virtual NIC and synthetic input only; this proves no
human consent and no physical-NIC behaviour.

## Order of work

After W5's descriptor path (JUN-519) and W4's network driver that is off by default (JUN-520); the consent panel kinds (a remote request, a
model download) can be drafted earlier against static text. Decision 1 and gate (a) can be done first: they need only the existing local path
and the W8 capture.

## Not decided here (owner questions)

1. Which remote rails, if any, Itonami OS offers, and whether murakumo/mishima are among them (decision 3).
2. Where models come from and live (a digest-pinned source, a user-selected store; interacts with the W6 backup ADR-0279).
3. The size and fuel limits (decision 6) and whether conversation history can ever be a sendable category.
