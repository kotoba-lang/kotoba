# cloud-itonami-cofog Integration

`cloud-itonami-cofog-*` repositories publish independent-operator civic-tech
blueprints keyed by government function. `kotoba-cofog` declares what
technology capabilities are required to run them.

Runtime flow:

```text
cloud-itonami-cofog-{code}
        |
        v
kotoba.cofog/execution-plan
        |
        v
kotoba.technology/stack
        |
        v
concrete repos and operator services
```

The COFOG blueprint should not import a capability implementation directly.
It should request the capability contract from `kotoba-technology`.

## Maturity & readiness

`kotoba.cofog/maturity-summary` and `execution-plan` expose per-function
maturity and UI/export readiness so an operator console can show them.

| Maturity tier | Meaning |
|---|---|
| `:implemented` | source actor exists (reference implementation) |
| `:blueprint` | blueprint repo published (`:repo` set) |
| `:spec` | registry entry only (blueprint repo pending) |

Current state (COFOG full coverage, 79/79):

- Total entries: 79 (10 divisions + 69 groups)
- Divisions: 10/10 represented (registry-only, not independently
  blueprint-eligible)
- `:implemented` 0 · `:blueprint` 5 · `:spec` 74

Every dispatchable (group-level) entry requires `:robotics` (ADR-2607011000
robotics-premise, adopted here for parity with `kotoba-industry` /
`kotoba-occupation`): a robot performs the physical domain work under an
actor + independent function-specific governor.

## Boundary with matsurigoto (etzhayyim/root)

`matsurigoto`'s COFOG backbone (`20-actors/matsurigoto/data/cofog-standard.kotoba.edn`)
is the SAME authoritative UN COFOG table, used for a DIFFERENT principal: a
polity's OWN sovereign statecraft (etzhayyim's covenant self-governance, or an
adopting nation-state's own execution). `kotoba-cofog` /
`cloud-itonami-cofog-*` is the COMMERCIAL OPERATOR counterpart: a licensed
civic-tech vendor contracted BY a government to serve one function (e.g. fire
inspection, waste collection), not the government itself. Names/labels are
shared verbatim so the two never drift into inconsistent COFOG readings; the
governance model, principal, and repo are structurally separate.
