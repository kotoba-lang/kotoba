# cloud-itonami-isco Integration

`cloud-itonami-isco-*` repositories publish sole-proprietor occupation
blueprints. `kotoba-occupation` declares what technology capabilities are
required to run them.

Runtime flow:

```text
cloud-itonami-isco-{code}
        |
        v
kotoba.occupation/execution-plan
        |
        v
kotoba.technology/stack
        |
        v
concrete repos and operator services
```

The occupation UI should show:

- operating states
- required technologies
- missing technologies
- available operator services
- proof and audit contracts

The occupation blueprint should not import a capability implementation
directly. It should request the capability contract from `kotoba-technology`.

## Maturity & readiness

`kotoba.occupation/maturity-summary` and `execution-plan` expose per-occupation
maturity and UI/export readiness so an operator console can show them:

| Maturity tier | Meaning |
|---|---|
| `:implemented` | source actor exists (reference implementation) |
| `:blueprint` | blueprint repo published (`:repo` set) |
| `:spec` | registry entry only (blueprint repo pending) |

Current state (ISCO-08 unit-group coverage 100%):

- Total entries: 436 (full ISCO-08 unit-group list)
- Major groups: 10/10 represented (group 0 "Armed Forces" registry-only)
- `:implemented` 69 · `:blueprint` 19 · `:spec` 348
- 46 of the 69 `:implemented` entries (6130, 8160, 2166, 2641, 2651, 2652,
  2654, 1219, 1223, 1330, 1341, 1349, 1412, 1439, 2144, 2320, 2411, 2422, 2431, 2621, 2634, 3122, 3123, 3141, 3255, 3339, 3512, 4120, 4131, 4132, 4211, 4224, 4229, 4322, 4413, 4415, 5120, 5162, 5164, 5169, 5230, 5249, 5312, 6111, 6114, 6121) are on the full `langgraph.graph` Actor pattern
  (Advisor+Governor as StateGraph nodes) — the direction all future
  promotions follow; the rest use a lighter standalone
  Store+governor-function pattern from before that direction was
  adopted

Every entry requires `:robotics` (ADR-2607011000 robotics-premise, adopted
here for parity with `kotoba-industry`): a robot performs the physical domain
work under an actor + independent occupation-specific governor.
