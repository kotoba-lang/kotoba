# tedai (手代) — member-computer-operation actor

**DID**: `did:web:etzhayyim.com:actor:tedai` · **Tier**: B · **Status**: R0 · **ADR**: 2606101400

## What this is

The actor that **operates the member's own computer** — the charter-clean answer to the
computer-use-shaped request (*「browser, computer 操作ができるような actor」→「do it」*). 手代 =
the Edo merchant-house clerk who operates the house's affairs *on the master's instruction and
under the master's seal* — member-principal by etymology. It is **karakuri's OS-layer sibling**
(web-service : karakuri = computer : tedai = robot body : tazuna): the same gate system lifted from
the vendor-ToS axis to the **device-consent / surveillance / input-injection** axes.

It is the **charter-clean inverse of commercial computer-use**: **own-device-only ·
T1-scripting-API-first · stance-honest (no anti-cheat/DRM/detection evasion) · no-server-key ·
member-signed mutate · on-device vision (a screenshot NEVER leaves the device) · no-surveillance
(never bossware) · hash-only evidence**. The uniform vocabulary is a normalized **`DesktopOp`**
(`app · noun · verb · safety · destructive · adapter-tier`, the sumitsubo `ModelOp` / karakuri
`ServiceOp` pattern) with one OS-layer-specific addition: the **`:outward`** safety class — a verb
whose effect leaves the device (send / pay / post / upload) is held at the Council outward gate
even WITH a member signature. Three adapter tiers, safest-first: **T1 scripting/accessibility-API**
(AppleScript/JXA + AXUIElement, Windows UIA, AT-SPI2, app CLI) > **T2 stance-permitted
vision-pointer (engine: on-device-vision — baien edge / LAN Murakumo)** > **T3 file-level**.
A `:prohibited` synthetic-input stance refuses T2 by construction — **anti-cheat games / DRM
players / banking apps are the canonical case**; a missing stance is default-deny. **Browser apps
route to karakuri** (N7 — one owner per surface; tedai never re-implements web automation).

ISIC J6201 · ISCO 2512/3514 · UNSPSC 81112.

## Cells (langgraph→WASM; Murakumo-only; `.solve()` raises at R0)

All five are coded reference cells (state machines unit-tested; `.solve()` raises at R0):
**app_resolve** (dan — resolve → tier + synthetic-input stance + karakuri route) · **intent_plan**
(naphtali — brief → prohibition-scan → gated DesktopOps; NL leg is R1 Murakumo, G4) ·
**pairing_broker** (gad — member-keyless device pairing; outward held at Council gate even with
member-sig) · **actuate_invoke** (asher — wires the Clojure desktop + T2 vision methods into
stance-gate→mutate-gate→dry-run) · **evidence_audit** (joseph — sha256-only evidence + Datom
projection, G7/G9).

Methods layer: `src/tedai/methods/desktop.cljk` (DesktopOp parser/planner) ·
`src/tedai/methods/t2_vision.cljk` (vision-pointer T2 plan builder — surveillance + evasion
verbs structurally unrepresentable) · `src/tedai/methods/actuate_live.cljk` (the
single live-actuation membrane — refuses unless env flag + operator + Council Lv6+ + member-sig,
and refuses at R0 even then, G6/G3) · `src/tedai/methods/datom.cljk` (kotoba Datom audit
projector; raw frames refused, G7/G9).

## Gates (immutable R0→R3)

**G1 member-principal / own-device-only** (only a device the member owns + physically paired;
structurally not a RAT) · **G2 T1-preferred / stance-honest** (prefer the OS automation surface;
T2 vision only where the synthetic-input stance permits; **no detection-evasion** — no anti-cheat
bypass / DRM circumvention / input forgery; `:prohibited` refuses T2 by construction) ·
**G3 no-server-key** (pairing keys member-held + encrypted; mutate by member signature; server
signature refused, ADR-2605231525) · **G4 Murakumo-only / on-device-vision** (a screenshot never
leaves the device; baien edge or LAN Murakumo only) · **G5 read-default / mutate-gated /
outward-held** (read ships at R0; create/update/**delete** need member-sig + dry-run confirm;
**:outward** ops additionally need the Council outward gate) · **G6 actuation-gated** (ANY live
input injection Council Lv6+ + operator gated; R0 = parse/plan/dry-run only) · **G7 kotoba-EAVT
audit** (every DesktopOp = a Datom; member can audit what touched their machine) ·
**G8 no-surveillance** (op-scoped observation of the member's own session only; no keylogging /
camera / mic / other persons; never bossware) · **G9 evidence-minimization** (hashes + summaries,
never raw frames; flag keys never values).

## Non-goals

N1 not bossware / employee-monitoring / parental-stalkerware / partner-surveillance · N2 no
anti-cheat / DRM / bot-detection evasion or driver-level input forgery · N3 not a RAT / botnet (no
unpaired or third-party device) · N4 no keylogging / credential harvesting (credentials are typed
by the member, never by tedai) · N5 not a click-farm / ad-fraud / mass-automation engine · N6 no
prohibited-content driving (Charter-Rider §2) · N7 not a browser-automation tool (browser → karakuri).

## Build / test

```
kbb -M:test
kbb -M:test
```

R0 = design + DesktopOp parser/planner + pairing_broker state-machine + `:representative` app
registry only. **No live actuation** of any tier (T1/T2/T3); all gated Council Lv6+ + operator (G6).

## Do not

- Do not operate any device that is not the member's OWN + physically paired, and do not build
  any monitoring-of-others feature (employee/child/partner) — G1 / G8 / N1 / N3.
- Do not use the T2 vision-pointer adapter on an app whose synthetic-input stance is prohibited
  (anti-cheat games, DRM players, banking apps), and never add detection-evasion (anti-cheat/DRM
  bypass, input-driver forgery) — G2 / N2 (`desktop.py stance_gate()` refuses; `t2_vision.py`
  makes evasion AND surveillance verbs unrepresentable — `_make_step` raises on them).
- Do not let a screenshot leave the device (no cloud computer-use API, no frame upload) and do not
  store a raw frame in the audit log — G4 / G9 (`datom.py op_entity()` refuses `raw_frame`;
  evidence is `evidence_hash()` only).
- Do not store pairing keys server-side or let tedai sign a mutating op — G3 / ADR-2605231525. The
  grant carries only an encrypted-envelope ref; the member signs.
- Do not authorize an `:outward` op (send/pay/post/upload) on a member signature alone — G5; the
  outward gate is Council-level (`pairing_broker` holds it at `awaiting_outward_gate`;
  `actuate_live.py` has no parameter that satisfies it at R0).
- Do not re-implement browser automation — N7; browser surfaces route to karakuri.
- Do not call any cell's `.solve()` — R0 scaffolds raise `RuntimeError` by design.
