# ADR-0006 — Phase 4: real-time-ish scheduler & IO quota

- Status: proposed (Phase 4, not yet implemented)
- Date: 2026-06-27

## Context

Phase-0 bounds *per-run* resource use: a manifest's `:aiueos/limits {:memory-pages
N :fuel N}` caps RAM (a wasmtime `StoreLimits` memory ceiling) and CPU
instructions (a wasmtime fuel budget), and a runaway component traps instead of
hanging the host (SECURITY.md defense layer 4). `boot_rounds` then runs every
coded component **in dependency order, once per round**, threading one topic bus
across rounds — a periodic control loop where `clock()` returns the bus tick
(`bus.tick()`, incremented by `bus.advance()` between rounds).

What this loop has **no notion of** is *scheduling discipline*. Every component
runs every round, in the same topological order, regardless of how urgent or how
frequent it should be — there are no priorities, no periods, no deadlines. And
nothing rate-limits host calls: a component holding `log/write` or `topic/publish`
can issue unbounded `log`/`publish` calls within its fuel budget, flooding the
audit log or the bus. SECURITY.md admits this directly: *"Wall-clock / IO DoS …
a component can still issue many host calls; rate/quota limits on IO and a
real-time scheduler are future work."*

This ADR closes the **declaration + enforcement** half of that gap — a
deterministic cooperative scheduler and per-component IO quotas over the existing
loop — while being honest that *preemptive, hard real-time* scheduling needs the
microkernel (Phase 6) and is explicitly out of scope here.

## Decision

Add two new optional manifest blocks — `:aiueos/schedule` and `:aiueos/quota` —
parsed by the same fail-loud EDN schema as `:aiueos/limits`, and enforce them in
the two places that already own the relevant state: `boot_rounds` (the round loop)
and `HostCtx` (the host-call counter). Both stay **numeric and deterministic** in
the Phase-0 ethos: scheduling is over *cycles*, not wall-clock, and replays
bit-for-bit.

### The time base: cycles, not milliseconds (honestly)

The control loop has no wall clock. `clock()` returns `bus.tick()` — a monotonic
**cycle counter** that advances by exactly 1 per round. So a `:period-ms` field
would be aspirational, not enforced: there is no scheduler-driven wall-clock timer
to make a round take a fixed duration today.

We therefore accept the `…-ms` field names for forward-compatibility (a future
wall-clock scheduler in Phase 6 will honor them literally), but **enforce them in
cycles** via an explicit, manifest-pinned conversion:

```edn
{:aiueos/schedule {:period-ms 20 :deadline-ms 10 :priority 10
                   :cycle-ms 10}}   ; this loop: 1 cycle ≈ 10 ms (declared, not measured)
```

`:cycle-ms` (default 1) is the declared nominal duration of one cycle for *this
system*. The scheduler computes `period_cycles = ceil(period_ms / cycle_ms)` and
`deadline_cycles = ceil(deadline_ms / cycle_ms)` **once, deterministically**, at
boot. With the default `:cycle-ms 1`, ms values *are* cycles — the simplest
honest mapping. Nothing claims a cycle takes a real 10 ms today; `:cycle-ms` only
fixes the ratio so periods stay sane when a real clock lands.

### `:aiueos/schedule` — per-component scheduling declaration

```edn
{:aiueos/schedule {:period-ms   20    ; run once per N cycles (after /cycle-ms)
                   :deadline-ms 10    ; must finish within M cycles of its release
                   :priority    10    ; lower = more urgent (rate-monotonic-ish)
                   :cycle-ms    10}}  ; system cycle→ms ratio (default 1)
```

Validated exactly like `:aiueos/limits` (a `read_limit`-style helper: integer,
in-range, fail loud on a non-integer / out-of-range / negative — which also stops
a negative wrapping to a huge `u32`). Defaults: `:period-ms` = `:cycle-ms` (every
cycle), `:priority` = 100 (a low-urgency middle), `:deadline-ms` = `:period-ms`
(implicit-deadline, the common real-time case). `:aiueos/schedule` joins
`MANIFEST_KEYS`; an unknown sub-key is rejected, like every other typo.

```rust
#[derive(Debug, Clone, Copy)]
pub struct Schedule {
    pub period_cycles: u64,   // derived: ceil(period_ms / cycle_ms), ≥1
    pub deadline_cycles: u64, // derived: ceil(deadline_ms / cycle_ms), ≥1
    pub priority: u32,        // lower = more urgent
}
```

### The deterministic cooperative scheduler

`boot_rounds` keeps its topological `order` (capability dependency: a provider
before a consumer — this is a correctness constraint, **never** reordered by
priority). Within that constraint, each round the scheduler:

1. **Releases** the components whose period is due this cycle:
   `cycle % sched.period_cycles == 0`. A component with `period_cycles = 3` runs
   on cycles 0, 3, 6, … and is **skipped** otherwise (skips are audited at a low
   level so a missed *expected* run is visible).
2. **Orders the released set by `(priority, topo_index)`** — priority first
   (lower = earlier), topo index as the deterministic tie-break. Crucially this is
   a *stable refinement within the topo order's freedom*: we only reorder
   components that are not in a producer→consumer relationship, so dataflow stays
   correct. (Phase 4 ships the simple, safe rule: priority orders only among
   components at the same dependency depth; cross-depth order stays topological.)
3. **Runs** each released component via `materialize_and_run` as today, on the
   shared bus, accounting fuel/quota per run.

```rust
for cycle in 0..rounds {
    let mut released: Vec<usize> = order.iter().copied()
        .filter(|&i| cycle as u64 % sched_of(i).period_cycles == 0)
        .collect();
    released.sort_by_key(|&i| (sched_of(i).priority, depth_of(i), i));
    for &i in &released { /* materialize_and_run … check deadline … */ }
    bus.advance();
}
```

### What "deadline" means under cooperative + fuel-bounded execution

There is no preemption: a component runs to completion (or to a fuel/quota trap)
before the next one starts. So a deadline is not enforced by *interrupting* a
slow component — it is **detected and audited**:

- A component that **exhausts its fuel budget** (the existing fuel trap) is a
  **missed deadline** by definition: it could not finish its slice of work within
  its allotted instruction budget. The trap is already
  `Event::Reject`-audited in `materialize_and_run`; Phase 4 tags it
  `deadline-miss: fuel exhausted`.
- A component whose **cumulative release-to-completion span exceeds
  `deadline_cycles`** (it was released on cycle C but, because higher-priority
  work ran first across rounds, did not complete by C + deadline_cycles) is an
  audited `deadline-miss: overrun` — *informational*, since cooperatively we
  never had the option to preempt the work that delayed it.

Deadline is thus an **audited service-level signal**, not a hard guarantee. That
is the honest shape of a cooperative scheduler, and it is still useful: forensics
can answer "which component blew its budget, and when."

### `:aiueos/quota` — per-component host-call rate caps

The host counter already exists: `HostCtx.calls` increments on every gated host
call. Phase 4 turns that counter into an enforced **per-cycle budget**, declared
per component:

```edn
{:aiueos/quota {:host-calls 64    ; total gated host calls allowed per cycle
                :publishes  8}}   ; of those, at most N may be `publish`
```

Enforced **in the host ABI gating in `src/host.rs`**, right where the call is
already counted — so an over-quota call **traps**, exactly like an ungranted
capability or an undeclared topic:

```rust
struct Quota { host_calls: u64, publishes: u64 }

fn charge(ctx: &mut HostCtx, kind: Charge) -> anyhow::Result<()> {
    ctx.calls += 1;                          // existing counter
    if ctx.calls as u64 > ctx.quota.host_calls {
        anyhow::bail!("host-call quota exceeded ({} per cycle)", ctx.quota.host_calls);
    }
    if matches!(kind, Charge::Publish) {
        ctx.publishes += 1;
        if ctx.publishes > ctx.quota.publishes {
            anyhow::bail!("publish quota exceeded ({} per cycle)", ctx.quota.publishes);
        }
    }
    Ok(())
}
```

`charge` replaces the bare `d.calls += 1` in each `func_wrap` closure, threading a
`quota: Quota` and a `publishes: u64` counter into `HostCtx`. The budget is
**per-cycle**: `HostCtx` is freshly constructed for each `materialize_and_run`
call, which already happens once per component per round — so the counters reset
each cycle for free. Absent `:aiueos/quota`, the defaults are generous (e.g.
`:host-calls` = 1024, `:publishes` = 256) so existing components are unaffected;
deny-by-default applies to *capabilities*, not to call counts, which would
otherwise break every current example.

A quota trap is security-relevant and surfaces through the same
`Event::Reject` path `materialize_and_run` already uses for fuel/memory/topic
traps — IO-DoS attempts become first-class audit entries.

## Increments

1. **Schedule data model + this ADR** — parse `:aiueos/schedule`
   (`{:period-ms :deadline-ms :priority :cycle-ms}`) via a `read_limit`-style
   fail-loud helper; derive `period_cycles` / `deadline_cycles`; add `schedule`
   to `MANIFEST_KEYS`. *(no behavior change yet)*
2. **Period skipping** — `boot_rounds` releases only components due this cycle
   (`cycle % period_cycles == 0`); audit skips of expected runs.
3. **Priority ordering** — order the released set by `(priority, depth, topo)`
   within the dependency constraint; document that topo order is never violated.
4. **Quota data model** — parse `:aiueos/quota {:host-calls :publishes}`; add to
   `MANIFEST_KEYS`; carry a `Quota` into `HostCtx`.
5. **Quota enforcement** — `charge()` in `src/host.rs` traps on over-quota
   host-call / publish counts; audit via the existing `Event::Reject` trap path.
6. **Deadline auditing** — tag a fuel trap as `deadline-miss: fuel exhausted`;
   record a release-to-completion overrun as `deadline-miss: overrun`.
7. **Tooling / examples** — a periodic-control example pinning `:cycle-ms`,
   priorities, and quotas; `aiueos up` reports per-cycle release order and any
   deadline misses.

## Consequences

- Closes the *enforcement* half of SECURITY.md's "Wall-clock / IO DoS"
  limitation: host-call/publish floods now **trap and are audited**, and
  components run on declared periods and priorities instead of all-every-round.
- **Deterministic and replayable.** Periods, priority order, and quota budgets are
  all functions of the cycle counter and manifest data — no wall clock, no
  nondeterminism, so a boot replays bit-for-bit (consistent with the
  deterministic `random()` and the cycle-based `clock()`).
- **Cooperative, not preemptive — by design.** A component still runs to
  completion (or to a fuel/quota trap) before the next; the scheduler chooses
  *what runs and in what order*, never interrupting work in flight. A deadline is
  an **audited signal**, not a hard guarantee.
- **`:period-ms` / `:deadline-ms` are cycle-enforced today** via the declared
  `:cycle-ms` ratio (default 1 → ms = cycles). The names are forward-compatible
  with a Phase-6 wall-clock scheduler that will honor them literally; nothing here
  pretends a cycle takes a real millisecond.
- **True real-time / preemption needs the microkernel (Phase 6).** Hard servo
  loops stay native (as ADR-0002 already notes); wasm suits the supervisory /
  planning layers this cooperative scheduler targets. This ADR deliberately ships
  the tractable, deterministic subset and leaves preemptive RT, priority
  inheritance, and admission-control / WCET analysis to that phase.
- Quotas are **per-cycle and per-component**, resetting with each fresh
  `HostCtx`; they bound IO *rate*, not lifetime totals — a long-running system can
  still do a lot of IO over many cycles, just never bursting past its per-cycle
  budget within a single component's slice.
