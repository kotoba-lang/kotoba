# AGENTS.md — kotoba-lang/activity

Automatic work-time capture: observations → sessions → attribution → timesheet
entries. Zero dependencies, no I/O, no clock.

## Three invariants. Do not weaken them.

Each has a test that fails if it stops holding. They are the reason this output
can be a billing basis instead of a guess.

1. **Time is never extrapolated.** A session ends at its last observation — not
   at the next one's start, not at "now". Capture undercounts by at most one
   sample interval. If you are tempted to add the trailing dwell, you are about
   to inflate every session by however long the poller slept.
2. **Unattributed time stays unattributed.** Never spread leftover minutes to
   make a day add up. `coverage` reports the shortfall.
3. **Rounding goes down or to nearest.** There is no `:ceil` and an unknown mode
   falls back to `:floor`. Rounding up bills time nobody observed.

## The LLM boundary

`admit` is where an externally produced proposal crosses. The model may **label**
a span. It may not create, lengthen or reassign one. A nil project is admitted —
"observed, nobody knows what for" is the honest answer invariant 2 protects — but
a named project must exist and a restated duration must match.

## Conventions

- Anything needing the current time or a timezone takes it from the caller
  (`date-of`), so a run is reproducible from its observations alone.
- `:obs/detail` is the privacy-sensitive field. `redact` drops it; anything
  leaving the worker's device goes through there first.
- `->timesheet-entries` emits the `:ts/*` shape `kotoba.labor`, `kotoba.psa` and
  `kotoba.shift` all read. Keep it compatible; none of them depends on the others.
- Keep this repo dependency-free. A capture agent embedding it should not pull in
  wage or payroll code it has no business holding.

## Test

    kbb -M:test && kbb -M:lint
