# karakuri 絡繰 — web-service-to-CLI

karakuri gives a member a uniform **command-line / programmatic handle over GUI-only web services**
(Squarespace, Wix, Notion, Shopify, …) — the charter-clean answer to the `clianything.org`-shaped
request *「squarespace のような webservice も CLI にする actor を設計して」*. 絡繰 = the *karakuri*
mechanism that drives a manual service by command — in the Toyota karakuri-kaizen sense: clever,
low-cost automation that removes manual clicking toil.

It is deliberately **not** a `clianything.org` clone. A generic "drive any website" SaaS imports four
violations; karakuri inverts each:

- **Own account only.** karakuri operates **only the member's OWN authenticated account** — never
  harvests third-party data, never a "scrape this site" product (G1, himotoki prior art).
- **Official API first, ToS-honest.** It prefers the service's **official API** (T1); uses
  headless-browser automation (T2) **only where the ToS permits**; and **never evades bot-detection**
  (no captcha-farming, no proxy/IP cloaking, no rate-limit circumvention) (G2).
- **No server-held keys.** The member's credentials/sessions stay with the member-operator,
  encrypted; the member **signs every mutating action** and a server signature is refused (G3,
  ADR-2605231525).
- **Auditable + portable.** Every planned/executed op is a **kotoba Datom** (`as-of`, replayable),
  and the **export round-trip** (T3) makes the member's data portable — the inverse of lock-in (G7/G9).

## The uniform vocabulary — `ServiceOp`

A CLI string parses into exactly one normalized op:

```
karakuri <service> <noun>.<verb> [--flag value ...]
```

…carrying a classified `safety` (`read`/`create`/`update`/`delete`), a `destructive` flag, and the
selected adapter `tier` (T1 official-API > T2 ToS-permitted headless > T3 export).

## browser操作 — the T2 engine is **browser-use**

The headless-browser tier (T2) is driven by **browser-use** (a LangGraph-driven browser agent over
Playwright), planning over the **member's OWN authenticated session**. Two independent stance axes
govern routing: `:service/tos-stance` (the official-API axis → T1) and `:service/t2-stance` (the
browser-automation axis → T2). A `:prohibited` browser stance refuses T2 **by construction**, *even
when an official API exists*.

**Google + Facebook** are exactly that case — `:api-ok` yet browser-automation-prohibited:

```
karakuri google messages.list          # → T1 official API (Gmail), NOT browser-automated
karakuri google search.query --q hi    # forced T2 → refused (G2): use the API, don't browser-automate
karakuri facebook posts.list           # → T1 Graph API for the member's OWN assets; T2 refused
karakuri legacy-portal records.list    # no API + ToS permits → T2 via browser-use (the legit path)
```

The charter-clean reading of *「Google/Facebook を browser 操作する」*: where an official API exists,
**drive the API on the member's own account** (T1); browser automation of those consumer surfaces is
ToS-prohibited and karakuri refuses it. The browser-use engine is reserved for GUI-only services whose
ToS permits automation. **Detection-evasion is unrepresentable** — `src/karakuri/methods/t2_browser.cljk` has no verb
for proxy/IP rotation, captcha-solving, stealth fingerprinting, or rate-limit circumvention; building
such a step raises (G2 / N2).

## Status

R0 (design + working ServiceOp parser/planner + session_broker state machine + `:representative`
service registry). **No live execution** — every adapter call is Council Lv6+ + operator gated (G6);
R0 is parse / plan / dry-run only. See `90-docs/adr/2606039200-*` and `AGENTS.md` for gates G1–G9 and
non-goals N1–N6.

## Try the planner (offline, no network)

```
kbb -M:test
kbb -M:test
kbb -M:test
kbb -M:test
kbb -M:test
kbb -M:test

# browser-use T2 action plan (dry-run; refuses T1/Google + ToS-prohibited services):
kbb -M:test
kbb -M:test
```
