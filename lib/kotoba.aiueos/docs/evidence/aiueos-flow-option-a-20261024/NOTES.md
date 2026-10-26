# Gate Option A measured: FLOW census pinned at pct=100, single pin 3593/a19f95a8 holds (JUN-31, 2026-10-24)

Question this cell answers: does Option A (measure the FLOW census at a fixed
pct — restore pct=100 before the FLOW stage, put the user's scale back after —
and keep the single gate pin `3593/a19f95a8`, ADR-0234 `90f8b03`) actually hold
on the full guest-browser profile, and does the new `#108` process-phase
instrumentation fire correctly?

Implementation: commit `b78b33a` ("kernel: pin the FLOW census at pct=100 and
name the #108 wait-loop silence point"), `os/aiueos/kernel/main.c` (+14),
`os/aiueos/kernel/process.c` (+98), `os/aiueos/scripts/smoke-qemu-uefi.sh`
(+5/-…): `AIUEOS_GUEST_BROWSER_FLOW_SCALE pinned=100 prev=<user scale>`
followed by the census, plus bounded `AIUEOS_PROCESS_PHASE_{ENTER,WAIT,
REAP_WAIT}` snapshots (wakes, timer, flush, exit predicates) whose prefix the
smoke harness treats as the `#108` signature.

## Measured (all runs at head `b78b33a`, `IMAGE-FRESH artifacts=3
tree=f12e0a399360`, except run1)

* **run2 — full profile (`AIUEOS_GUEST_BROWSER=1`, real virtio-keyboard +
  virtio-tablet via QMP), probe off.** The SCALE/SETTINGS stages end at the
  persisted user scale pct=125 as before; the FLOW stage now pins first:
  `AIUEOS_GUEST_BROWSER_FLOW_SCALE pinned=100 prev=125`, then
  `AIUEOS_GUEST_BROWSER_FLOW_OK windows=4 ops=182 text-px=3593
  hash=a19f95a8` — **the single gate pin matches exactly** (the same
  `9564/b2fad8a7` census-miss from the pct=125 spill is gone). The
  `FLOW_OPS n=182 words=…` stream (8,736 hex chars) has sha1
  `42fd9ed630edc8c031119c0106a4a0c9ba510dd5` — **byte-identical to cells
  A/B/B2/E** of the attribution receipt, so the drawn content is unchanged;
  only the magnification was fixed. Excerpt: `option-a-run2-flow-process-phase.log`.
* **run2 — `#108` instrumentation verified working.**
  `AIUEOS_PROCESS_PHASE_ENTER first=0 second=1 kotoba=2 worker=3` →
  `AIUEOS_PROCESS_PHASE_WAIT wakes=1 timer=13 flush=2 result=1 sched=0
  kotoba=42 worker=42 ipc=0 objwrite=1` (every exit predicate — result, both
  kotoba task values, ipc, objwrite 1→1 — resolves on a single wake) →
  `AIUEOS_PROCESS_PHASE_REAP_WAIT wakes=0 timer=19` (immediate reap). The run
  then reaches `AIUEOS_DESKTOP_LOOP_OK persistent input service` and ends
  `GUEST-NO-EXIT after 505s` — quiescence watchdog after 154 s with no byte on
  either transport (limit 150 s; last byte T+351 s) = the persistent loop's
  normal terminal, and explicitly **not** `#108` (that hang stops at
  `AIUEOS_KOTOBA_ELF_PROCESS_OK`; here the run is past PROCESS_PHASE and
  DESKTOP_LOOP). `SMOKE-EXIT=1` is the watchdog timeout, not a gate failure.
  The `#108` stall itself was **not reproduced** in run2/run3; the silence
  point is named in the harness and stays parked until the next stall.
* **run3 — final probe smoke (`AIUEOS_SMOKE_FINAL_PROBE=1`), green.**
  `SCANNED 3` → `AIUEOS_UEFI_SMOKE_OK`, `SMOKE-EXIT=0`. Full log:
  `option-a-run3-final-probe-smoke.log`.
* **run1 (not used as evidence).** At the pre-fix head `c29f42e`
  (`tree=52ba0d59e509`); the harness wall budget (420 s) cut the run at the
  EDIT stage (`EDIT n=48`); partial logs kept in `build/option-a-run1*.log`.

## Verdict

Option A is **green on the full profile**: one canonical pin `3593/a19f95a8`
is held by the pinned-pct measurement across runs whose user scale ends at
pct=125, the op stream is byte-identical to every prior cell, and the `#108`
phase instrumentation is live (all predicates observed, immediate reap). The
full-profile gate no longer depends on what the SETTINGS stage left behind.

## Boundary (say this, do not round it up)

* `kernel/*.c` is still compiled by zig cc; the C-free claim covers the
  compiler lineage and the kotoba object route only.
* The `#108` process-phase stall is **not** reproduced here — what is verified
  is the instrumentation and the named silence point, not a fix for `#108`.
* run2's `SMOKE-EXIT=1` is the quiescence watchdog ending a persistent-loop
  run after 505 s; the guest completed the whole suite (last marker
  `AIUEOS_DESKTOP_LOOP_OK`).
