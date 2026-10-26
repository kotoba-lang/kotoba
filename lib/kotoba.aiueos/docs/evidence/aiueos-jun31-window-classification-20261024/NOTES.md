# JUN-31: the boot window's ownership — kernel build contract or loader contract? (2026-10-24)

論点整理 (decision framing) for the wall the entry-contract measurement hit
(`aiueos-jun31-image-route-kernel-boot-20261024`): a kernel that passes **every**
ADR-0180 admit clause can be refused entry by three literals in the boot
stage. This note classifies each literal, splits the acceptance into the two
milestones that are actually reachable at different costs, and names the
decisions that belong to ADR-0180/ADR-0131 (owner), not to a tick's patch.
No bytes were booted for this note; every number below is from the cited
measurements.

## 1. The two contracts, measured against three artifacts

`aiueos.uefi.elf/admit` (ADR-0180) is the **kernel contract** — and ADR-0180
says why: "the admission rules are amu's, not `main.c`'s … so that the loader
admits exactly what the packager emits". The boot stage's `tfacts`/`uflags`
(`loader-probe.kotoba:314-338`) are a second, undocumented contract: the
placement **literals of one fixture** (TESTKERN.ELF, 110,872 B, seg0 160 B
@4096 / seg1 77,824 B @32768 — `loader-probe.kotoba:20-31`).

| clause | fixture `e7ee95b9…` | probe kernel `e940f36e…` (110,872 B) | desktop kernel `0a6fef42…` (127,256 B) | contract? |
|---|---|---|---|---|
| ADR-0180 admit (8 clauses) | pass | pass | **pass, reason 0 measured** | yes — kernel-side |
| `s0off == 4096` | pass | pass (4096) | pass (4096) | yes — packager places seg0 at 4096 by construction |
| `s1off == 32768` | pass | pass (32768) | **FAIL (49152)** | **no** — a function of seg0 size (below) |
| `kentry == s0addr` | pass | pass | pass | yes — already ADR-0180 "entry inside segment 0" |
| `s0size==s0mem`, `s1size==s1mem` | pass | pass | pass | yes — already ADR-0180 `filesz==memsz` |
| `s0mem <= 4096` | pass (160) | pass (397) | **FAIL (42,368)** | **no** — ADR-0180 allows `memsz <= 1 MiB` |
| `s1mem <= 77824` | pass (77,824) | pass (77,824) | pass (77,824, exactly) | **no** — the fixture's seg1 size |
| `klen <= 114688` | pass | pass | **FAIL (127,256)** | loader resource (28-page `kbuf`), and its own guard is overrun (§3) |

Measured layout pattern across the three artifacts: seg1 sits at
`max(32768, page-align(4096 + seg0size))` — 160 B and 397 B seg0 both land at
32768; 42,368 B seg0 lands at 49,152. So `s1off == 32768` holds **iff
seg0 ≤ 28,672 B**, independently of the even tighter `s0mem ≤ 4096`.
(The pattern is observed on the three measured ELFs; the emitter line that
sets it was not located this tick — recorded, not rounded up.)

## 2. Decision D1 — window ownership

**Option (a) — the window becomes the kernel's build contract.** A kernel must
then be built with code seg0 ≤ 4 KiB, data seg1 ≤ 77,824 B, file ≤ 114,688 B.
Measured consequence: probe-scale kernels fit (the `main → 42` kernel entered
and ran at the jump, `bootall=4`), but **the desktop kernel cannot be built to
this window** — its code segment alone is 42,368 B, 10x over, and its file is
127,256 B. Since JUN-31's acceptance text requires "the native GOP desktop
responds to input", option (a) alone cannot satisfy JUN-31; it can only satisfy
an interim boot-proof milestone (§4, M1).

**Option (b) — the loader grows to the contract it already claims** (ADR-0180:
"the loader admits exactly what the packager emits"). Narrow change: the T/U
clauses read the placement from the parsed phdrs (the placement stage already
does — `s0`/`s1` come from `p_paddr`) instead of comparing to fixture literals;
`kbuf` grows or the read streams; the handoff gets decided (D3). This is a
loader-contract change — ADR-0180/ADR-0131 territory and the owner's call, not
a tick's patch. This is the only option that reaches the desktop criterion.

Recommendation, for the record: (b) for the acceptance, with M1 (§4) taken
first under (a) so the selfhost chain is proven end-to-end before the loader
contract is touched.

## 3. Decisions D2 and D3 (independent of D1)

* **D2 — the read is a gate-less guard.** `fs/read-into` copies `klen` bytes
  into the 28-page `kbuf` **before** `uflags`' `at-most klen 114688` verdict
  looks at the number. Measured: run 1 overran `kbuf` by **12,568 B** and the
  run completed. Whatever D1 decides, the read must be bounded by the buffer
  and the verdict must gate (refuse), not merely report.
* **D3 — the handoff.** `os/aiueos/uefi/main.c:179` hands **boot-info v5** in
  RDI; the Kotoba loader's `(kernel-jump-to kentry image-handle)` hands the
  EFI **image handle** and no return path (`loader-probe.kotoba:399`). A
  desktop kernel enters mis-reading RDI as a `aiueos_boot_info*`. Either the
  loader builds boot-info v5 at the jump (route B work), or the kernel
  contract is "no boot-info, no return, kernel owns its exit (`out 0xf4, 21`
  → 43)" — which is exactly the contract the window-fitting probe kernels
  already satisfy.

## 4. Milestone split for JUN-31's acceptance text

* **M1 — reachable now, no contract change**: a **selfhost-built**
  window-fitting kernel (seg0 ≤ 4 KiB / seg1 ≤ 77,824 / file ≤ 114,688) +
  selfhost packaging + QEMU/OVMF boot with T/U marks, `kernel-jump-to`, and a
  kernel-owned exit 43, receipts binding compiler/kernel/packaging routes and
  hashes. This proves compiler → kernel → image → boot under the C-free route
  and closes "no emitted object has run in a kernel".
* **M2 — needs D1(b) + D3**: the acceptance's "native GOP desktop responds to
  input" (desktop kernel 127,256 B: window growth + boot-info v5 at the jump).

JUN-31's acceptance **as written** requires M2; it is unreachable until D1/D3
are decided. Say that, do not round it up.

## 5. Boundary

* Nothing here was booted; the numbers are the cited runs' (`aiueos-jun31-
  kernel-swap-judgment-20261024`, `aiueos-jun31-image-route-kernel-boot-
  20261024`, their `*.elf-facts.txt`).
* The seg1-offset pattern (§1) is a three-artifact observation; the emitter
  source was not located this tick.
* The C-free gate that this framing depends on ("no C path in the accepted
  build") is started in `docs/evidence/aiueos-jun31-cfree-gate-20261024/`.
