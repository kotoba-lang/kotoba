# catalog-maturity

Scoring truth for a reference **catalog**: how mature is it, where is it
weakest, and what is the highest-leverage thing to do next.

A **library** under `kotoba-lang`'s repository-role taxonomy
(`loop-ux-kaizen/resources/repository-rules.edn`): it computes and ranks, it
never fetches, writes, or schedules. `loop-*` repos own the running; this owns
the meaning of the numbers, so the rubric is testable and reusable without
standing up a runner.

## Axes

| axis | weight | measures |
|---|---|---|
| `:breadth` | 0.25 | distinct countries covered / target countries |
| `:concentration` | 0.20 | distance from being dominated by one country |
| `:documentation` | 0.20 | companies with ≥1 archived legal document |
| `:provenance` | 0.20 | documents carrying **both** a timestamp and a hash |
| `:reachability` | 0.15 | companies with a published contact route |

## Two properties worth knowing

**`:unmeasured` is not zero.** An axis with no observation is excluded from the
total and reported in `:measured-weight`, so a catalog is neither punished for a
metric it cannot yet observe nor able to inflate its score by declining to
measure something.

**Concentration is a first-class axis, not a footnote.** The catalog this was
written for reported "53 jurisdictions" while really covering 27 countries with
the United States at 55%. Both numbers were arithmetically correct and together
they were badly misleading. Breadth without concentration is a vanity metric.

## Test

    kbb --backend sci --classpath "src:test" run_tests.cljk
