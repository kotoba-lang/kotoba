# chigiri_legal_aid_clinic

LangGraph (Python / Pregel) cell — **free legal-aid intake + routing** for the
chigiri actor. Realises ADR-2605302200 Lane A (advice) intake and hands off to
ADR-2605302330 Lane B (certified mediation) where applicable.

## What it is / is NOT

- **IS**: intake → conflict check → NON-advice classification → jurisdiction
  enablement check → Public-Fund counsel assignment → `legalAidMatter` record.
- **IS NOT**: a source of legal advice. The licensed human lawyer is the
  practitioner. No node here produces advice (G14).

## Constitutional guards (enforced as code)

| Gate | Where | Behaviour |
|---|---|---|
| **G14** UPL | `_assert_no_advice` | the classifier may only emit a known practice-area label; any free-text / out-of-enum output raises (advice leak rejected). |
| **G15** zero-compensation | `assert_zero_compensation` + `emit_matter_record` | matter charges the adherent nothing; `zeroCompensation=True` pinned; no fee/consideration field exists by construction. |
| **G16** counsel supervision | `check_jurisdiction` + `assign_counsel` + `route_after_counsel` | matter cannot pass intake without a resolvable in-jurisdiction (`license == matter`) lawyer retained via Public Fund; `verify-required` jurisdictions (AT, US-state) are rejected. |

## Inference discipline (ADR-2605215000)

The only LLM use is `triage_classify`, a **non-advice classifier** that routes
through the Murakumo fleet (judah LiteLLM `127.0.0.1:4000` → gemma on EVO-X2).
It returns one label from a fixed enum; it is never asked to advise, and its
output is constrained by `_assert_no_advice`. No commercial GPU; `kotoba-llm`
stays disabled (Charter Rider §2(i)).

## Graph

```
START → load_intake → conflict_check ─(clear?)→ triage_classify → check_jurisdiction
                              │ no                      (enabled?) ┌─ yes → assign_counsel
                              ▼                                    └─ no ─────────────┐
                         emit_rejection ◄──────────────────────────────────────┐     │
                                                                                │     ▼
   assign_counsel → assert_zero_compensation → route_after_counsel ─(counsel+G15 ok?)─→ emit_matter_record → END
                                                                   └─ else → emit_rejection → END
```

## Ports (dependency-injected)

- `mst_port` — read intake record / write `com.etzhayyim.chigiri.legalAidMatter`
- `policy_port` — `jurisdictionPolicy` lookup (`enableState`)
- `counsel_port` — Public-Fund counsel registry + conflict check (G16)
- `murakumo_port` — non-advice classifier via the Murakumo fleet

## Status

R1 — control flow + constitutional guards are live and unit-tested; node I/O
(`# TODO`) is scaffolded behind ports. Lexicon: `com.etzhayyim.chigiri.legalAidMatter`.
Lint gate: `no-legal-aid-consideration.mjs` (G15).
