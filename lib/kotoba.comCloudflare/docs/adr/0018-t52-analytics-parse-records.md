# ADR 0018: T5.2 native guest records — analytics_parse tallies/sums

- Status: accepted
- Date: 2026-08-01
- Depends: ADR 0017 native guest records
- WBS: T5.2 residual multi-arg pure (analytics_parse)

## Decision

Fold remaining multi-arg pure on `analytics_parse_core` into single guest records:

| Export | Schema |
|--------|--------|
| `sum2` | `:parse/pair` |
| `sum3` | `:parse/triple` |
| `sum4` | `:parse/quad` |
| `string-tally-get` | `:parse/str-get` (`m` map + `k`) |
| `string-tally-add` | `:parse/str-add` (`m` + `k` + `n`) |
| `i64-tally-get` | `:parse/i64-get` |
| `i64-tally-add` | `:parse/i64-add` |

Record fields may hold `[:map K V]` tallies (compiler accepts map-typed record fields).

## Non-claims

- Host `parse-path-report` / `parse-daily-report` still fold in cljc (JSON projection host)
- analytics path GraphQL transport stays host
- T8.3 / W4 residuals unchanged

## Evidence

- KIR regenerated `analytics_parse_core`
- full suite 94/519 green
