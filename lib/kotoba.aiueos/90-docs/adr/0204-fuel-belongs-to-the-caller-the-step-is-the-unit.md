# ADR 0204: fuel belongs to the caller, and the step is the unit

Status: accepted. Date: 2026-09-08. Extends: ADR-0203, ADR-0034. Owner question:
*"fuel をちゃんと boot から整えるならどうするのがいい? kotoba, unison 的に"*

## The answer is already written in this workspace, for the other tier

`kotoba-native/elf64.cljc`, on the object wrapper's unconditional replenish:

> That makes the budget per CALL, so an object's fuel bound constrains one
> invocation and nothing wider — which is **the only reading under which a fuel
> bound is a bound on work rather than a quota on how many times the kernel may
> ever ask**.
>
> **A lifetime call cap is not a fuel bound; it is a delayed trap.**

ADR-0034 made that replenish universal for objects. The same comment names the
one place it was never applied: *"The single shared context belongs to the
bootable-IMAGE path."* The K16 kernel is a bootable image, and it is therefore
**the last delayed trap in this system, by this project's own definition.**

Everything ADR-0203 recorded follows from it. The run ends at
`debug-run-cycles` because the budget is a lifetime cap, the board resets to
get a fresh one, and that reset is why the node is reachable ~1% of the time,
why `ready?` flaps, and why a job dispatched at a hello meets a machine that is
already gone.

## The shape, in Unison's terms

In Unison a resource bound is an **ability**, and an ability is discharged by a
**handler the caller installs**. A computation says `{Fuel}`; it does not say
how much. `Fuel.provide` lives outside the computation, because a program that
can top up its own meter is not metered.

Two consequences follow directly, and they decide this design:

**1. The budget belongs to the caller, not to the artifact.** Today the number
is sealed into the image and the guest is built around it — `debug-run-cycles`
is literally chosen to fit the budget. That is the inversion: the *program* is
shaped by a constant that should have been the *host's* policy.

**2. The guest must not replenish itself.** The kernel could write its own fuel
qword from Kotoba — the context address is known and `kernel-store-u64-*`
reaches it — and it would work, and it would be wrong. The object tier does the
same write from the *wrapper*, emitted glue the guest cannot alter. Moving that
write inside the guest turns a bound into a self-administered suggestion. **A
handler inside the computation is not a handler.**

In Kotoba the same shape already has a name: the budget is `policy` in the
Execution IR (`{program, input, state, runtime, policy, effects} -> CID`,
ADR-2608160200), not `program`. Sealing it into the image is what makes it look
like part of the program.

## Therefore: the step is the unit, and the host runs the loop

**A resident node is not one long computation. It is an unbounded sequence of
bounded steps.** `state + event -> state' + effects` — the shape ADR-2607201300
already prescribes for `kotoba/app`.

- **Per-step fuel is a bound on work.** No step can wedge the machine. That is
  the property worth having, and it is the one this kernel needs.
- **Per-boot fuel is a quota on how many steps the machine may ever take.**
  That is not a safety property anyone chose; the board is *supposed* to run
  forever.

So the guest's `main` should perform ONE step and return, and the host should
replenish and re-enter. That is the object wrapper's `replenish; call; ret`
lifted to the image: `loop: replenish; call entry; test; jmp loop`. The loop
lives where the budget lives.

**What this buys beyond uptime:** the reset stops being fuel management and
becomes what it should always have been — a deploy mechanism, taken when a new
image is wanted or when asked, not as a consequence of the counter.

**What is given up:** "this machine cannot run forever" stops being enforced by
fuel. It was never the property being sought, and it is not currently enforced
either — the guard's outcome today is a halt that needs a person at the power
button, which is strictly worse than a machine that keeps running.

## Order of work

1. **The image entry becomes a host loop** (`kotoba-native`, image path):
   replenish the context fuel word, call the entry, and re-enter until the
   guest says stop. Byte-compare every other route to prove nothing else moved
   — the object path's `(le 512 8)` in particular must not change.
2. **`main` becomes one step** (aiueos): the resident recursion moves out of
   the guest and the return value carries continue/stop.
3. **The budget is then derived per step**, which is estimable in a way the
   whole run never was — with one exception named below.
4. **`debug-run-cycles` disappears.** It exists only to make a run fit a
   lifetime cap.

## What blocks step 3, named

`receive-established` has two self-calls and `kotoba.compiler.fuel-estimate`
reports it `:unbounded`. Until one step is estimable, a per-step budget is
still a measured-with-margin number rather than a derived one — better than
today, because a step is small and repeatable, but not yet a bound anyone
computed. Bounding that recursion is the prerequisite for ever calling this
number derived.

## Until then

The budget is no longer the binding constraint on run length: at 2^30 the
cycle count is a free parameter, where at 2^20 it was chosen to fit. Raising it
buys duty cycle at no risk to the margin as long as the arithmetic is stated,
and it is the only thing available before step 1 lands.

The worst-case per-cycle cost that is actually *known* is 262,144 — the old
configuration completed 4 cycles inside 2^20. 1024 cycles is therefore at most
268 million against a budget of 1,073 million: **a fourfold margin on the only
per-cycle bound anyone has measured**, for roughly 3 seconds of uptime per
reboot instead of 0.19. That is the interim, and it is arithmetic rather than a
hope.
