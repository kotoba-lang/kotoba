# AGENTS.md — kotoba-lang/shift

Attendance: punches, shifts, rosters, coverage, leave, swaps. Zero dependencies.
The statutory side is deliberately **not** here — see `kotoba-lang/worklaw`.

## The invariant. Do not weaken it.

**An unpaired punch is never completed.** A missing clock-out does not become
"end of shift", "end of day" or "now": it is an anomaly with no worked time,
because the alternative is inventing the most consequential number on the
timesheet. The same refusal covers an unclosed break — how long it was is
unreconstructable after the fact.

## Sibling, not duplicate, of `kotoba.activity`

`activity` **samples** ("what is in front of you just now", many times); this
**records** (a punch is a deliberate assertion). So `activity` segments a stream
and undercounts by a sample interval, while this pairs discrete events. And
attendance is **not rounded at all** — 7h13m stays 7h13m, because rounding an
assertion changes what someone said.

## Rostering: report, never impose

- **Availability is declared, never inferred.** Nobody is available by default.
- `coverage` reports the gap and does not close it.
- `propose-roster` mutates nothing and leaves an unfillable gap as
  `:still-short`. Candidates are taken **in the order given** — ranking people
  for shift assignment decides whose weekend gets taken, and that belongs to an
  operator who can be held to it, not to a library default. Do not add a
  "fairness" or "cost" heuristic here.
- A swap needs **both** parties, and the receiver's availability is re-checked at
  apply time. That check is the point: a swap is exactly where someone quietly
  ends up working through their own approved leave.

## Conventions

- `date-of` comes from the caller; this library owns no timezone.
- Leave accrues per hours **worked**, not per calendar month.
- `->timesheet-entries` emits the shared `:ts/*` shape.

## Test

    kbb -M:test && kbb -M:lint
