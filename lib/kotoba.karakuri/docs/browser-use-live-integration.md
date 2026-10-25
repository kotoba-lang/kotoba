# karakuri × browser-use — live T2 integration (design draft)

**Status**: design draft (R0; live execution NOT shipped) · **Actor**: karakuri 絡繰 ·
**Anchor ADR**: 2606039200 · **Gate to ship**: Council Lv6+ + operator (G6)

This is the design for wiring the real **browser-use** library as karakuri's T2 (headless-browser)
adapter. It is a *draft contract*, not an activation. No live browser execution exists in the repo;
everything below is gated behind the `methods/adapter_live.py` membrane and a Council activation ADR.

## Why browser-use is the T2 engine (and only T2)

karakuri prefers the safest adapter (T1 official-API > **T2 browser-use** > T3 export). T2 is used
**only** for a service that (a) has no usable official API for the member's task and (b) whose ToS
permits automation (`:service/t2-stance :permitted`). **Google and Facebook are `:api-ok` but
browser-prohibited**, so they route to T1 and the T2 path is refused by construction — browser-use is
never engaged for them.

browser-use is a LangGraph-driven browser agent over Playwright; it fits karakuri's
`langgraph→WASM`, Murakumo-only cell model (the NL→intent step is Murakumo, G4; browser-use executes
the resulting deterministic step plan).

## The path, end to end

```
NL brief ──(command_plan, Murakumo G4)──▶ ServiceOp
ServiceOp ──(service_resolve)──▶ tier = T2, engine = browser-use   (only if t2-stance permits)
ServiceOp ──(t2_browser.build_browser_plan)──▶ dry-run step plan   (G6; no network)
dry-run plan ──(adapter_live.authorize_live)──▶ authorization      (G6+G3; refuses by default)
authorization + plan ──(browser-use driver, POST-ACTIVATION)──▶ live actions on the member's session
every step ──(datom.op_to_entity)──▶ kotoba Datom audit            (G7)
```

The first four hops are implemented and tested at R0. The fifth hop (the actual browser-use driver)
is the only piece that does not exist and must not be built until the gate opens.

## What the driver MUST honor (the contract)

1. **Plan-bound.** The driver executes ONLY the steps in a `t2_browser.build_browser_plan` output.
   It may not invent actions outside `BROWSER_ACTIONS`. The plan is the contract.
2. **No detection-evasion (G2/N2).** `EVASION_ACTIONS` (proxy/IP rotation, captcha-solving, stealth
   fingerprinting, rate-limit circumvention, UA randomization) are unrepresentable in the plan and
   the driver must not add them. browser-use's own stealth/proxy options stay **off**; if a service
   blocks automation, karakuri stops — it does not evade.
3. **Member's own session (G1/G3).** The driver attaches the member's OWN authenticated session via
   the encrypted-envelope grant ref (`open_session`, `server_held_key=false`). It never holds a
   platform credential, never signs on the member's behalf, and operates no third-party account.
4. **Mutate = member signature (G5).** `submit`/mutating steps carry `requires: member-signature`;
   the driver blocks at that step until a member signature is presented. The server never signs.
5. **Human-paced, ToS-respecting (G2).** `wait_for` is real waiting; rate limits and `robots`/site
   rules are respected; backoff on errors. No busy-loops, no bulk hammering.
6. **Audited (G7).** Every executed step is appended to the kotoba Datom log (`:op/executed-at`),
   so the member can replay exactly what touched their account.

## The activation gate (`methods/adapter_live.py`)

A live call is authorized ONLY when ALL hold (default-deny):

- operator flag `KARAKURI_ALLOW_LIVE_ADAPTER=1` on an opted-in host, AND
- an operator attestation DID, AND
- Council Lv6+ (G6), AND
- a member signature (G3 no-server-key; the server can never sign).

`authorize_live` returns an authorization descriptor and **still does not execute** — it is an
authorization membrane, not the driver. Shipping the driver is a separate Council activation ADR that
must cite this draft and the six contract rules above.

## Out of scope until activation

- The browser-use driver binary/process and any Playwright browser launch.
- Any live network call to Google/Facebook/Squarespace/etc. (every T1/T2/T3 leg is G6-gated).
- Persisting member sessions anywhere server-side (forbidden; G3).
