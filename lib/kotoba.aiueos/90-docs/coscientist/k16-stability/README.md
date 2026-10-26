# K16 stability — Co-Scientist program

Owner's brief (2026-09-06): make aiueos, kototama, kotoba and amu "as stable as
Linux / ChromeOS", using the Co-Scientist loop (Generate → Reflect → Rank →
Evolve → Meta-review) and parallel agents, iterating over the LAN without a
hand on the power button.

Pattern lineage: `orgs/gftdcojp/network-isekai` ADR-0007 → superproject
`90-docs/design-quality/coscientist.cljc`. The judge here is NOT an LLM: every
hypothesis carries a decisive measurement (wire byte on the netlog, bridge
log line, QEMU debug-port marker, offline recomputation, or a unit test), and
Rank compares hypotheses on those, not on prose.

## Loop

| stage | who | output |
|---|---|---|
| Generate | 7 read-only agents, one per theme | `hypotheses/gen-<theme>.edn` |
| Reflect | orchestrator + agents | annotate `:reflection {:verified? :counter-evidence :risk}` |
| Rank | pairwise tournament (Elo, K=32) on: decisive test exists · blast radius · cost · predicted gain · dependency depth | `rank-NN.edn` |
| Evolve | execution agents in isolated worktrees; ONE deploy channel (the orchestrator) to the physical board | commits on `k16-stream-*` branches |
| Meta | what the loop itself got wrong (instruments, collisions, retractions) | `iteration-NN.md` |

## Ground truth for Rank (from 2026-09-06)

Eleven kernel defects were fixed and every one was preceded or accompanied by an
INSTRUMENT that failed silently (dead logger thread, UTF-8 grep, socat sink,
netstat zeros, unreachable QEMU expectation, fuel `ud2`, non-atomic deploy,
colliding trace bytes, `$?` after echo). A hypothesis that makes a silence
impossible ranks above one that adds a feature. See ADR-0156 for the record.

## Hypothesis schema

```edn
{:id "theme-hN" :title "…" :claim "one falsifiable sentence"
 :evidence ["file:line — …"] :test "decisive check + predicted outcome"
 :fix-sketch "…" :blast-radius :small|:medium|:large :cost :S|:M|:L
 :confidence 0.0 :depends-on []
 ;; added by Reflect / Rank / Evolve
 :reflection {…} :elo 1500 :status :proposed|:verified|:refuted|:landed|:withdrawn}
```

Ranking criteria are ordered: a hypothesis with no decisive test is not ranked.
