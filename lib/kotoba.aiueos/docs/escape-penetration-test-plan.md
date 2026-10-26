# Escape-oriented penetration test plan (A-02) — v1

Status: adopted plan; first run recorded below (no guest-escape probe executed yet)
Date: 2026-10-19

## Purpose, and what this document does not do

`docs/tcb-inventory.md` keeps A-02 open until the hypervisor/runtime boundary
receives an escape-oriented penetration test **and retest**. This document is
the plan and the running record for that work. It does not close A-02: A-02
also requires the independent TCB inventory review and the selected formal
models for the broker/grant/link invariants.

Nothing here is a claim that any boundary is escape-proof. A row that has not
been executed is `planned`, and `planned` is not `passed`. Unknown is not
success.

## Boundaries in scope

Named as the TCB inventory names them (`docs/tcb-inventory.md`, Included
boundaries); the escape question is what a compromised or malicious guest
could gain.

| # | Boundary | Where the mechanism lives | Escape question |
|---|---|---|---|
| B1 | HVT / KVM mechanism (guest RAM, vcpu loop, ioctls) | `aiueos.hvt` (`/dev/kvm` via `java.lang.foreign`) | can a guest read or write host memory, or reach ioctl surface, beyond its granted GPA range? |
| B2 | VFIO / IOMMU / virtio (device model, virtqueue path) | `aiueos.hvt` virtio-mmio model; exit classification in `kotoba-lang/vmm` | can a guest DMA outside its buffers, forge interrupt state, or straddle an MMIO window? |
| B3 | VM launch and boot-image construction | loader + builder (bounded segment admission) | can a crafted image smuggle a segment, exceed the low-region budget, or be admitted twice? |
| B4 | Wasm host ABI and bounded runner | `kototama` `open-session` / `run-main-bounded` | can guest code escape fuel/memory accounting, defeat cancellation, or exceed provider output bounds? |
| B5 | broker / grant / link invariants | `grant` + `kototama.linear-journal` | can an admission be forged, replayed, or consumed for a different principal? |
| B6 | content addressing admission | `cid-v1-admit`, `unixfs-file-admit` | can a crafted CID name a block that is not its content, or smuggle a file past blockwise verification? |

Out of scope for this plan: power, electromagnetic, probe and
malicious-firmware attackers (already outside the software-only profile in
`docs/threat-models/side-channels-v1.md`), and P5 real-machine boot (JUN-91;
every run here is QEMU/OVMF and is labelled as such).

## Method

Each scenario is one row with: precondition, attempt, expected refusal, and
the evidence artifact an executed run must leave behind. Rules:

- execute against the QEMU/OVMF reference profile, and record the build
  profile (the default smoke build compiles the TSC calibration out —
  AGENTS.md § Measuring things here);
- every attempt records input, expected, observed; a crash, hang or unknown
  outcome is a finding, never a pass;
- a finding becomes an issue with a fix, and the fix gets a retest row that
  re-executes the original scenario (A-02 needs the retest, not the fix alone);
- unexecuted rows stay `planned` in this table. Do not "update" them to
  `passed` from code reading.

## Scenario table v1

| ID | Boundary | Attempt | Expected refusal | Evidence | Status |
|---|---|---|---|---|---|
| E-01 | B1 | guest DMA descriptor naming a GPA outside its granted range | IOMMU/EPT refusal; no host page touched | QEMU trace + receipt naming the refused descriptor | planned |
| E-02 | B2 | virtio-mmio access straddling a device window boundary | exit classification refuses (vmm asserts window straddling) | vmm assertion receipt + guest-visible error | planned |
| E-03 | B2 | forged used-ring index / chain pointing outside the queue | virtqueue path rejects; no write outside the buffer | QEMU trace + receipt | planned |
| E-04 | B3 | image carrying a third PT_LOAD segment, or one crossing `aiueos_low_end` | loader refuses (exactly two PT_LOAD; low-region budget ADR-0222) | refusal receipt from the image admission path | planned |
| E-05 | B3 | re-admission of an already-admitted boot image under a new name | at-most-once admission refuses the second consumption | linear-journal entry refusal (`verify-chain` view) | planned |
| E-06 | B4 | guest infinite loop at the default fuel tier | instruction budget traps the guest (`ud2` measured at 1,024 fuel, ADR-0220) | trap receipt naming fuel tier | planned |
| E-07 | B4 | two guests saturating the shared fair semaphore concurrently | non-queuing admission rejects saturation | admission receipt (this is T-04's malicious multi-guest stress) | planned |
| E-08 | B4 | guest blocking inside a provider host call past the wall-clock deadline | `run-main-bounded` cancels; provider obeys cancellation | cancellation receipt per provider (T-04: proof still required) | planned |
| E-09 | B4 | provider returning output above the declared size bound | output is rejected, not truncated silently | refusal receipt (T-04: proof still required) | planned |
| E-10 | B5 | replay of a consumed grant (second execution of a receipted capability) | linear journal refuses the second consumption (at-most-once) | journal refusal receipt | planned |
| E-11 | B5 | edited or removed journal middle entry | `verify-chain` names where the chain breaks | `verify-chain` output | planned |
| E-12 | B6 | `cid-v1-admit` given a caller-chosen 32-byte digest with a mismatching codec/length | admit decides against the bytes, not the caller's claim | refusal receipt (ADR-0128) | planned |
| E-13 | B4 | kernel object calling a host-call context slot with no host (the `string-code-point-at` class, ADR-0220) | the call traps; it must not silently succeed | boot receipt or trap receipt | planned |

## First run — 2026-10-19 (what was actually executed)

Executed in a clean worktree from `origin/main` (`ea25175`):

1. Scenario table v1 constructed from the TCB inventory and the boundary
   owners' own documents (vmm README, kototama `grade-a-resource-containment.md`,
   ADR-0128/0220/0222). This is the planning artifact, not a probe.
2. `kbb -M:tcb-check` — attempted as the drift-check precondition for any run.
   **It does not run, on `origin/main` as well as on this branch**: the nbb
   route dies at `src/aiueos/tcb.cljk:245` with
   `Unable to resolve symbol: java.util.regex.Pattern/quote`. Recorded as
   finding F-001; the check being red on main is not attributed to this branch.
3. No guest-escape probe (E-01 … E-13) was executed in this run. All rows
   remain `planned`. Execution rows begin with run 2.

## Findings

| ID | Finding | Status |
|---|---|---|
| F-001 | `kbb -M:tcb-check` fails to run (nbb route, `tcb.cljk:245`, `java.util.regex.Pattern/quote`) on `origin/main` and on this branch — the A-02 precondition check is unavailable | open |

## Residual risk

Until the table has executed rows with receipts, the hypervisor/runtime
boundary has **no** escape evidence, and no deployment profile may treat A-02
as mitigated. Per `docs/threat-models/side-channels-v1.md` and
`docs/deployment-profiles.md`, untested boundaries are named residual risk,
not absence of risk.
