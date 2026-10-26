# ADR-0111 — PLC is a native RT user profile

- Status: accepted
- Date: 2026-08-26

## Decision

Implement PLC support as `aiueos-plc-v1`, a statically admitted native user
task above the AIUEOS hard-real-time kernel profile. It is not a second OS and
does not add a source interpreter to the deployed machine. The engineering
tool compiles the admitted IEC 61131-3 Structured Text subset to Kotoba and AMU
then emits a static `x86_64-aiueos-user-v1` ELF. Linux, JVM, GC, foreign objects
and dynamic allocation are absent from the runtime path.

The first language slice provides BOOL and wrapping signed 32-bit DINT values,
assignments, bounded arithmetic, comparison and Boolean expressions. Loops,
recursion, calls, pointers and runtime online interpretation are refused. LD,
FBD and SFC may later lower into the same bounded PLC IR; they do not get an
independent runtime.

## Scan transaction

At release, the kernel-side PLC provider latches the physical inputs into an
immutable input image. Capability 16 reads that image. Capability 17 stages an
output in a shadow image; it never touches physical output. Capability 19
advances the watchdog checkpoint after every stage succeeds. Capability 18 is
the final operation and asks the provider to atomically commit every declared
output; it succeeds only after budget/deadline checks and complete staging.

A trap, invalid stage, incomplete result, budget exhaustion, deadline miss or
watchdog timeout discards the shadow image, latches a fault and applies the
configured physical safe state. The PLC program cannot bypass this transaction
because its user ELF capability bitmap contains exactly 16 through 19.

## Release boundary

A deterministic program build receipt binds ST source, generated Kotoba,
native ELF and compiler commit. That receipt remains `deployment_ready=false`
until it also binds a qualified RT-kernel receipt, the exact I/O map and the
response-time admission analysis. Source-level online change is outside the RT
runtime. A newly signed native ELF may activate only at a scan boundary after
the same admission and binding checks, with the prior admitted artifact kept
as rollback state.

This profile is a standard PLC claim, not a safety-PLC claim. Functional-safety
certification, redundant diagnostics and safety I/O require a separate safety
lifecycle and evidence set.
