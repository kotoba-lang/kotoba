# karakuri (絡繰) — web-service-to-CLI actor

**DID**: `did:web:etzhayyim.com:actor:karakuri` · **Tier**: B · **Status**: R0 · **ADR**: 2606039200

## What this is

The actor that **turns a GUI-only web service into a CLI** — the charter-clean answer to the
`clianything.org`-shaped request (*「squarespace のような webservice も CLI にする actor」*). 絡繰 =
the karakuri mechanism that drives a manual service by command (the Toyota karakuri-kaizen sense:
clever automation that removes manual toil; ties to the labor-liberation mission + KaizenObserverCell).

It is the **charter-clean inverse of clianything.org**, the way okaimono inverts Amazon and yadori
inverts GoDaddy: **own-account-only · official-API-first · ToS-honest (no detection-evasion) ·
no-server-key · member-signed mutate · data-portability over lock-in**. The uniform vocabulary is a
normalized **`ServiceOp`** (`service · noun · verb · safety · destructive · adapter-tier`), one vocab
across the TS/py runtimes (the sumitsubo `ModelOp` pattern). Three adapter tiers, safest-first:
**T1 official-API** > **T2 ToS-permitted headless-browser (engine: browser-use)** > **T3 structured
export**. Routing uses two independent stance axes: `:service/tos-stance` (official-API → T1) and
`:service/t2-stance` (browser-automation → T2); a `:prohibited` browser stance refuses T2 by
construction *even when an API exists* — **Google + Facebook are the canonical `:api-ok` /
browser-prohibited case** (drive the official API on the member's own account; never browser-automate
the consumer surface). The T2 engine **browser-use** (LangGraph browser agent over Playwright) plans
in `src/karakuri/methods/t2_browser.cljk`, where detection-evasion verbs are structurally unrepresentable.

ISIC J6201 · ISCO 2512/3514 · UNSPSC 81112 (computer programming / web automation).

## Cells (langgraph→WASM; Murakumo-only; `.solve()` raises at R0)

All five are coded reference cells (state machines unit-tested; `.solve()` raises at R0):
**service_resolve** (reuben — resolve → tier + both stance axes) · **command_plan** (simeon — NL
brief → gated ServiceOps via the Murakumo planner, N6 scan) · **session_broker** (levi — member-keyless
session broker) · **adapter_invoke** (judah — wires command.py + t2_browser.py into
tos-gate→mutate-gate→dry-run→execute-gated) · **export_roundtrip** (zebulun — T3 own-data-only
encrypted export).

Methods layer: `command.py` (parser/planner) · `t2_browser.py` (browser-use T2 plan builder) ·
`nl_plan.py` (Murakumo NL→ServiceOp, G4 — live LLM operator-gated) · `export.py` (T3 export, G9) ·
`adapter_live.py` (the single live-execution membrane — refuses unless flag + operator + Council Lv6+
+ member-sig, G6/G3) · `datom.py` (kotoba Datom audit projector, G7). browser-use live-driver contract:
`docs/browser-use-live-integration.md`.

## Gates (immutable R0→R3)

**G1 member-principal / own-account-only** (drives only the member's OWN authenticated account; no
third-party access; no scrape-this-site product) · **G2 official-API-preferred / ToS-honest** (prefer
T1; T2 headless only where ToS permits; **no detection-evasion** — no captcha-farm / proxy-cloaking /
rate-limit circumvention; `:automation-prohibited` refuses T2 by construction) · **G3 no-server-key**
(member creds/sessions member-held + encrypted; mutate authorized by member signature; server
signature refused, ADR-2605231525) · G4 Murakumo-only · **G5 read-default / mutate-gated** (read +
export ship at R0; create/update/**delete** require member-sig + explicit dry-run confirm) ·
**G6 outward-gated** (ANY live third-party network call Council Lv6+ + operator gated; R0 =
parse/plan/dry-run only) · **G7 kotoba-EAVT audit** (every planned + executed ServiceOp = a Datom;
member can audit what touched their account) · G8 sourcing-honesty (`:representative` registry;
unknown service/op degrades honestly) · G9 PII / portability-consent (export = member's OWN data only,
encrypted).

## Non-goals

N1 not a scraper/surveillance/third-party-harvesting tool · N2 no detection-evasion / anti-bot
circumvention / captcha-farming / proxy-cloaking · N3 no credential-stuffing / account-takeover /
shared-account abuse · N4 no paywall/license/DRM circumvention or content piracy (portability =
member's OWN data) · N5 not a bot-farm / mass-automation / spam / fake-engagement engine · N6 no
driving of prohibited-content or third-party ad/affiliate systems (Charter-Rider §2(a)–(h)).

## Build / test

```
cd methods && python3 -m pytest                 # command/t2_browser/nl_plan/export/adapter_live/datom (87 tests)
cd cells   && python3 -m pytest                 # all five coded cells (31 tests)
kbb -M:test
kbb -M:test
kbb -M:test
```

(If a global pytest plugin errors on pydantic, prefix `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` — the
karakuri code is stdlib-only.)

R0 = design + ServiceOp parser/planner + session_broker state-machine + `:representative` service
registry only. **No live execution** of any adapter (T1/T2/T3); all gated Council Lv6+ + operator (G6).

## Do not

- Do not operate any account that is not the member's OWN, and do not build a third-party scraper /
  surveillance / data-harvesting feature — G1 / N1.
- Do not use the T2 browser-use adapter on a service whose browser-automation stance is prohibited
  (incl. Google/Facebook — `:api-ok` but browser-prohibited; route to T1), and never add
  detection-evasion (captcha-solving-as-evasion, proxy/IP rotation, rate-limit circumvention) —
  G2 / N2 (`command.py tos_gate()` refuses; `select_tier()` is official-API-first; and
  `t2_browser.py` makes evasion verbs unrepresentable — `_make_step` raises on them).
- Do not store member service credentials/sessions server-side or let karakuri sign a mutating op —
  G3 / ADR-2605231525. The grant carries only an encrypted-envelope ref; the member signs.
- Do not execute any create/update/delete without member-sig + dry-run confirm, and never run a live
  adapter call without operator + Council — G5 / G6.
- Do not call any cell's `.solve()` — R0 scaffolds raise `RuntimeError` by design.
- Do not drive prohibited-content or third-party ad/affiliate systems — N6 / Charter-Rider §2.
