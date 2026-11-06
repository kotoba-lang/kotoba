# ADR-0287 — The shared Browser/CSSOM render runs in a user domain, not in the kernel image

Date: 2026-11-06

## Status

Accepted 2026-11-06 (owner: render outside the kernel image, "描画をカーネル外に出す"; the open questions below were answered
"おすすめで決定" with the recommended options, listed under Decisions on the open questions). No renderer domain is implemented. Amendments 1 (floats), 2 (user targets cannot host a renderer yet; measured addendum; owner confirmation) and 3 (the interim kernel-image placement is a deviation with a stated exit; the kernel/user partition; a separate renderer object, proposal) follow the decisions below. Amendment 3 records measurements and PROPOSALS; its owner decisions are pending (listed at its end).

## Context

JUN-810 makes the native desktop render dapp UI documents through the same Browser/CSSOM code the hosted page uses. JUN-854
measured the size (evidence: `90-docs/evidence/render-closure-size-20261105/README.md`, kotoba#1235):

- The render closure (`browser.surface` down through `cssom.layout`, `cssom.core`, `kotoba.wasm.dom`, host colour,
  bounded regex, text) is about 32.4k lines, 1.78 MB of source (1.89 MB with htmldom).
- The kernel-v3 text cap is 3 MiB less a 64 KiB reserve after amu#1840, because v3 data starts at 0x400000. The margin is
  about 0.82 MB. At the whole-graph ratio (0.76 text bytes per source byte) the closure needs 1.35-1.44 MB; at the ratio of
  dense kernel code (3.4-4.1) it needs 6-8 MB. It does not fit in any measured case, and raising the cap further means moving
  the data offset and the boot image rules, which is a layout change.
- The ratio for cssom itself is unmeasured: it has not been compiled in the kernel dialect.

## Decision

1. **The renderer is not part of the kernel image.** It runs as a separate object in its own address space, in a user
   domain, built for the user target (`x86_64-aiueos-user-v1`, CPL3). The kernel keeps what it has: the compositor, the
   draw-list consumer, input, and the capability checks. The kernel text cap stops being the budget for rendering.
2. **The renderer consumes documents and produces a draw list.** Its input is a UI document (Hiccup-shaped tree and
   stylesheet, JUN-856) and input events; its output is the draw-list the kernel already draws (ops of the existing
   259-op budget, to be checked: 253 are used with four windows and a full page). Document in, draw list out is the contract;
   how the two cross the domain boundary is open below.
3. **Hosts stay equivalent for dapps.** A dapp is host-neutral (owner, 2026-11-06): the same document renders in a browser
   or natively, and capabilities differ by host. This decision only fixes where the native host runs the render.
4. **The renderer holds no authority of its own.** Its grants are the ones the kernel gives its domain (reading documents,
   writing its draw-list region); it does not fetch, sign or install. A renderer fault must not take the compositor down.

## Consequences

- The size problem moves from the kernel text cap to the user image. The user-domain object has its own limits (the
  user-target compile limits seen in ADR-0019 for heap-shaped code) and its own size, both unmeasured.
- The cssom ports (JUN-134/135) and their qualification (JUN-136) are still required: the code must compile for the user
  target. This decision does not make them smaller.
- JUN-855 (C2) changes shape: it is the runtime contract for strings, documents and floats in the user domain, and the
  kernel only needs the draw-list and event interface. Whether the user domain may use f64 (FPU state per domain) instead of
  fixed point is part of that work and is not decided.
- The 4-window draw budget (ADR-0285) still bounds what the kernel draws; the renderer must fit its output in it.

## Decisions on the open questions (owner: recommended options, 2026-11-06)

- **Boundary: shared regions, not per-operation syscalls.** The kernel maps three regions into the renderer domain: the UI document (read-only to the renderer), an input event ring (read-only), and the draw-list region (read-write to the renderer, read-only to the compositor). Syscalls are used only to signal "frame ready" and to yield. Per-op syscalls would cost a ring crossing for each of up to 259 ops per frame.
- **Loading: embedded first, signed later.** The renderer object is embedded in the boot image, so it is covered by the existing image signature. Once ADR-0286's multi-signer scheme ships, it is updated as a signed system object under the same rule. It is never fetched unsigned.
- **One renderer domain, per-window arenas.** One domain serves all windows with a separate arena per window, and the kernel restarts the domain if it faults while the compositor keeps drawing the last frame. Per-app domains give stronger isolation against a hostile document, but multiply the renderer's memory by the window count; revisit once the memory of the renderer is measured.
- **Floats: fixed point in the user domain (amended 2026-11-06, see Amendment 1).** The first answer here was f64 in the user domain on the condition that the kernel saves floating-point state across a CPL3 switch. Measurement showed that condition cannot hold today, for two independent reasons, so the renderer uses fixed point.

## Still open

- Measured size and speed of cssom in the user target (needs the first slice of JUN-855).
- Whether the kernel preserves floating-point state across a CPL3 process switch (read-only check first).
- The exact byte layout of the three regions and the event/draw-list encodings.

## Not verified

No renderer domain exists. The existence of the user target and CPL3 processes is read from ADR-0111, ADR-0175 and ADR-0211,
not re-run for this ADR.

## Amendment 1 (2026-11-06, owner delegation: recommended options): floats

The owner left the choice to the recommended option. What was measured (evidence pull request kotoba-lang/kotoba#1246, JUN-855), and what was only read:

- **Measured, compiler.** Every `x86_64-aiueos-user-v1` to `user-v5` target refuses `f64` (E7101 detail 33) and `f32` (detail 36); `kernel-v1` admits f32 and f64 comparison. A user-domain renderer therefore cannot be written with floats at all today.
- **Measured, context switch (C UEFI kernel).** Under QEMU TCG, two CPL3 processes holding different values in xmm0/xmm7, x87 st0, the x87 control word and MXCSR each found the other's values in their own registers about 47-70 times per class over 414 timer-driven task switches; an FXSAVE64/FXRSTOR64 pair around the timer ISR removed every event in the run. This was measured on the C kernel, not on the Kotoba-native kernel the desktop uses.
- **Read, not run (Kotoba-native kernel, amu seed/95).** One `FXRSTOR64` at user entry and no `FXSAVE` anywhere in seeds 74/86/88/92/95/96; `uv-enable` refuses CR4.OSXSAVE.

**Decision.** The renderer uses fixed point (integer arithmetic with a documented scale), with a hosted-oracle error bound per operation, as JUN-855 item 2(b) proposed. Reasons: adding `f64` to the user targets means new code generation, a new ABI for float arguments, and FXSAVE/FXRSTOR in the context switch of the compiler's own kernel, each of which changes the compiler that builds itself (a new fixed point and pin regeneration), where fixed point changes only the cssom port that has to be rewritten for the canonical dialect anyway (JUN-134/135).
**Cost, stated plainly.** JUN-854 counted 58 float sites in cssom (`double`, `Math/`) and 4 in dom-gpu; each needs a scale and a bound, and parity with the f64 hosted oracle becomes "within the bound", not "equal". Layout results that depend on exact float behaviour (percent and calc rounding) need cases.
**Reopen when** the compiler gains `f64` for the user targets and the context switch saves FP state; this ADR then gets a further amendment.

## Amendment 2 (2026-11-06, owner delegation: recommended options): the user targets cannot host a renderer yet

The cssom census (kotoba#1252, JUN-134/135) found two things that change how this ADR is realized, not where it is headed.

**1. The size premise was overstated.** The render-closure evidence (kotoba#1235) sized the closure by source bytes (1.78 MB). 76% of those bytes are docstrings and comments; the closure's code is about 14.8k non-blank lines, 458 KB. At the whole-graph ratio (0.76 text bytes per code byte) that is about 350 KB, inside the ~0.82 MB margin the 3 MiB cap leaves; at 2.6 text bytes per code byte (one fixed-point solver measured on kernel-v1) it is about 1.2 MB, outside it. So the closure may or may not fit in the kernel image, and the figures bound a different program than the one that will exist, because the port is a rewrite into scalar code.

**2. The user targets cannot host it (measured; two probes re-run by the orchestrator).** With the pinned compiler, `x86_64-aiueos-user-v1` to `user-v5` emit one 4096-byte text page (E7104) and refuse strings (E7101 detail 16), records and vector parameters (E7102), floats (E7101 detail 9/33/36), `/`, `rem`, `mod` (E2101) and functions with 6 or more parameters; there is no store primitive (`kernel-store-u32` is E2101), only `kernel-load-u32` on the 64-byte request from v2. A 34-line fixed-point block-width solver needs 5874 bytes on user-v1 (E7104) and compiles on kernel-v1 at 6226 text bytes. The cap is therefore not the first blocker for a CPL3 renderer; the target's capabilities are (JUN-919).

**Decision (recommended option; the destination in decision 1 stands).**
- The renderer stays a separate module group behind the interface of this ADR (document and events in, draw list out; shared regions). Until the user targets gain what JUN-919 lists (a text segment above 4 KiB, a store primitive on a region the process owns, bounded strings and records), its modules are written in the kernel dialect and measured with the kernel targets (JUN-920).
- Where those modules run in the interim is decided by measurement, not by this ADR: if the measured text of the whole renderer fits the kernel-v3 margin it may live in the kernel image as an interim placement behind the same interface; if not, it is a separate privileged object. Moving it to a CPL3 domain stays the goal and costs only the interface already fixed here.
- First slice: JUN-920 (Q6 lengths, percent, block-width, margin-collapse, block-style) as scalar-i64 modules with a native oracle gate.

**Owner confirmation still wanted, not blocking.** (a) The rounding rule at exact ties: the f64 oracle is inexact there (29% of 50 px gives 14 where exact arithmetic gives 14.5; 1114 of 1,233,197 integer-percent x basis pairs differ and all differences are exact .5 ties). The Q6 spec will be exact arithmetic with a stated rounding rule and the oracle disagreements will be reported, not copied; Blink's behaviour at ties was not measured. (b) Whether an interim placement inside the kernel image is acceptable if it fits, given decision 1.

### Amendment 2, measured addendum (2026-11-06, JUN-920, kotoba#1255)

The first fixed-point slice (Q6 lengths, percent, block-width, margin-collapse, block-style; scalar i64 modules, gate `PASS_NATIVE_CSSOM_BLOCK_Q6`, reproduced by the orchestrator) gives the first measured cost of a scalar rewrite:

- The arithmetic core without the parser is 143 code lines and **22,837 text bytes on kernel-v1, about 160 bytes per code line** (length 5,642; block_width 9,753; margin_collapse 2,344; block_style 20,009 including the first two). On `user-v1` it is refused: E7104 (4,096-byte text page, 5.6 times over) for a 0-argument entry, E7102 detail 56 for a 2-argument entry.
- **Indication, not a forecast.** The original closure is about 14.8k code lines. At 160 bytes per line a scalar rewrite of that size would be about 2.4 MB, about three times the ~0.82 MB margin of the kernel-v3 image. Unless the rewrite is much denser than this slice (the slice is arithmetic-heavy; layout code with more control flow may be denser or sparser), the interim placement "inside the kernel image if it fits" of this amendment is unlikely to hold, and the renderer is a separate object, loaded outside the kernel text cap, behind the interface of this ADR. The measurement is repeated on each slice (JUN-920 and its successors) and the placement is decided on the total, not on this extrapolation.
- Tie rule used by the slice: exact arithmetic, round half up (`floor(x + 1/2)`), digits past the sixth truncated. The hosted f64 oracle disagrees only at exact .5 ties (846, 1,114 and 7,391 pairs in the three dense sweeps; none away from ties). The owner is asked to confirm the rule; Blink's behaviour at ties was not measured.
- Host runtime note: it traps (SIGTRAP) on i64 overflow and on f64 to i64 of a huge value, contrary to the census's "wraps silently"; the slice's modules guard against it.

### Amendment 2, owner confirmation (2026-11-06)

The owner answered the open points of this amendment with "proceed with the recommended options":

- **Tie rule: confirmed.** Q6 arithmetic is exact with round half up (`floor(x + 1/2)`); decimal digits past the sixth are truncated. The hosted f64 oracle's disagreements at exact ties are reported, not copied. Blink's behaviour at ties is still unmeasured.
- **Placement: confirmed as recommended.** The renderer is written in the kernel dialect behind the document-in / draw-list-out interface; whether it lives in the kernel image or in a separate object is decided on the measured total (about 160 bytes per code line so far), and the CPL3 domain remains the destination (JUN-919).
- **Flex rounding.** The flex slice (JUN-920 slice 3, kotoba#1260) rounds each item on its own, as the hosted code does; a line's sizes may then differ from the free space by at most n/2 raw (n/128 px). Largest-remainder rounding, proposed by the census, is not adopted until Blink's behaviour is measured. The same slice caps a flex line at 4 items because scalar parameters leave no room for more; larger lines are refused, never truncated (JUN-932).

## Amendment 3 (2026-11-07, JUN-805 / JUN-856 slices): the interim kernel-image placement is a deviation with a stated exit

Tags: **[M]** measured (evidence README in this repository), **[R]** read from source, **PROPOSAL** not decided, **OWNER** decision pending. Nothing below changes decisions 1 to 4 of this ADR; it records where the work stands against them and what the exit needs.

### 1. Measured state: the kernel image is nearly full

* **[M]** Compiler cap for `x86_64-aiueos-kernel-v3` text: 3,080,192 bytes, which is 3 MiB less a 64 KiB reserve (amu `seed/85-aiueos-project.kotoba:16-17`, read on amu main; the reserve holds the user shim, the ISR table and alignment; E7104 is raised at line 73 when base plus size passes the cap).
* **[M]** Whole-image text of the two render slices, same run, kernel-v3: `draw` profile 2,974,208 B (`evidence/cssom-draw-slice-20261107`), `uidoc` profile 3,007,744 B, 64 modules (`evidence/cssom-uidoc-slice-20261107`, Size). The uidoc slice added 33,536 B for a 79-code-line module plus its entry glue.
* **Headroom.** Cap minus image is **72,448 B** (uidoc) and **105,984 B** (draw). The two READMEs state "estimated margin" 82,848 and 116,384; both are exactly 10,400 B larger than the plain subtraction, and the READMEs do not say why. This amendment uses the plain subtraction; the range "about 73 to 83 KB" for the current image is the plain figure to the README figure. The draw image is also not a shipping image: the `desktop` profile does not link cssom, so the headroom of the shipping desktop was not measured.
* **[M]** Cost per slice so far: `draw_k` 22,837 kernel-v1 text B (92 code lines, 248 B per line); `uidoc_k` 19,297 B (79 lines, 244 B per line). The Q6 slice was about 160 B per line (Amendment 2, addendum). The closure the renderer must reach was about 14.8k code lines (Amendment 2); the slices written so far total a few hundred lines.
* **Consequence.** At roughly 160 to 250 text B per code line, the 72 to 83 KB left holds on the order of 300 to 500 more code lines. Every further render slice (text, images, events, flex and grid in the chain, the compositor-side op encoding) lands in the same cap, and the cap cannot be raised without moving the data offset (`kp-data-offset`, line 18) and the boot-image rules, which is a layout change (Context above).
* **Deviation, stated.** Amendment 2 allowed an interim placement inside the kernel image "if the measured text fits" and gave the measurement as the test. The slices are in the kernel image today because they fit. That is the opposite of decision 1 (the renderer is not part of the kernel image). It is accepted as a measurement vehicle only. **Exit:** the first slice that would take the image past the cap, or the first slice that needs text or images, does not enter the kernel image; the renderer then becomes the separate object of section 3 (**PROPOSAL** for the trigger; **OWNER** may choose an earlier one).

### 2. The partition the renderer should end in

This section is a **PROPOSAL** consistent with decisions 1, 2 and 4.

* **Kernel:** memory, scheduling, IPC and the shared regions, signature verification (ADR-0286), drivers. It contains no UI, no CSS, no layout.
* **User domain (renderer):** UI document and input events in; draw list out, through the three shared regions already decided above (document read-only, event ring read-only, draw list read-write to the renderer and read-only to the compositor). It holds no authority beyond those regions (decision 4).
* **Compositor:** consumes the draw list and owns the frame. Where it runs is not decided here: today it is in the kernel (decision 1), and whether it moves to its own domain is **OWNER** open. A renderer fault must not stop it drawing the last frame (decision 4 and the restart rule above).
* **Design references only, not verified against any repo source.** The owner asked how iOS and ChromeOS divide kernel and user space. In general terms, and from general knowledge rather than from anything in this repository or a checked source: both keep the kernel free of UI; a compositor or render server process owns the screen, and the code that interprets untrusted documents or pages (web content) runs in sandboxed processes without privilege that hand drawing results to that compositor over IPC or shared memory. This is cited only as precedent for the shape above. No claim is made about their exact process names, IPC mechanisms or sandbox rules, and none of it was checked.
* **[R]** The slices already respect the interface direction: draw list in a region with 32-byte slots, header `DLv1`, ops 255 (`evidence/cssom-draw-slice-20261107`); document in a region with magic `UID1` (`evidence/cssom-uidoc-slice-20261107`). Both layouts are labelled proposals in their READMEs, and neither equals the compositor's existing encoding.

### 3. The separate-object loader (PROPOSAL)

* **Object.** The renderer is one object, loaded outside the kernel image, built for a user target (decision 1), with the interface above.
* **Signing.** Signed like the other artifacts of ADR-0286: both Ed25519 and ML-DSA-65, at least M of N distinct pinned signers (ADR-0286 Amendment 2: N = 3, M = 2), manifest of 64 bytes, up to four 3392-byte signature entries. A **new** context string is proposed, for example `"AIUEOBJ1"`, used as the object magic in the manifest and as the ML-DSA context, with `M' = 0 || 8 || "AIUEOBJ1" || manifest`, the same domain separation as `AIUECAT1` and `AIUEFRS1` (ADR-0286 Amendments 5 and 6), so that an image, catalog or freshness signature cannot be presented as a renderer object and the reverse. The name is a placeholder. Verification is the existing region-based verifier. **OWNER:** the name, and whether renderer objects share the image signer set or get their own.
* **Version and rollback.** Not designed. ADR-0286 Amendment 4's version floor covers images; whether renderer objects need their own floor is open.
* **Load path.** Embedded first, signed later was decided above. Under this proposal the first loadable form is still embedded in the boot image (covered by the image signature) but as a separate segment or file outside the capped kernel text; the signed form follows. It is never fetched unsigned.
* **What the object needs from user targets (JUN-919).** **[M]** (Amendment 2): `user-v1` to `user-v5` emit one 4096-byte text page (E7104) and refuse strings (E7101 detail 16), records and vector parameters (E7102), floats (E7101 detail 9, 33, 36), `/`, `rem`, `mod` (E2101) and functions with six or more parameters; there is no store primitive (`kernel-store-u32` is E2101), only `kernel-load-u32` on the 64-byte request from v2. For the renderer these become requirements: a text segment far above 4 KiB (the kernel-v1 text of `draw_k` alone is 22,837 B, 5.6 times the page); a store primitive on a region the process owns (the draw list is written); bounded strings and records (selectors, property names, tables); division and remainder (layout, Q6 rounding). The measured text of the whole renderer, not these slices, sets the final size.
* **Floats.** No change: fixed point (Amendment 1). The user targets still refuse floats, which is why the arithmetic is scalar i64 with a Q6 scale and the round-half-up rule confirmed in Amendment 2. Reopen conditions are those of Amendment 1; JUN-855's measurement of FP state on CPL3 preemption (`evidence/jun-855-fp-state-preemption-20261106`) is unchanged.

### 4. The interim path, and what is not done

Until section 3 exists, the render modules are written in the kernel dialect and gated natively under QEMU: style, layout (`flow_k`), draw (`draw_k`, `dk-run`) and the UI-document front end (`uidoc_k`, `ud-run`), chained document to style to layout to draw list, on the 18 dapp windows (uidoc README). Gates `PASS_NATIVE_CSSOM_DRAW_K` and `PASS_NATIVE_CSSOM_UIDOC_K` (receipts in the two evidence directories). Not done, as those READMEs state:

* Not wired into `browser.surface` or `layout.cljk`; the native chain does not run the hosted Browser/CSSOM code.
* No CPL3 region mapping; the "regions" are two free pages (13 and 14) of the owned window used as stand-ins. No renderer domain, no event ring.
* No text and no images: text nodes are placeholders that emit nothing; no gradients, opacity, clipping, positioned or floated boxes, stacking contexts. Flex and grid are not wired into the chain (`flow_k` is block flow only). Only `background-color` and `border-color`.
* No `style` attribute and no attributes but `id` and `class`; the sheet is limited to 16 distinct properties, and the sheet used for the dapp windows is a reduced one, so the result is not claimed to equal the page.
* The draw region holds 255 ops while this ADR's kernel budget is 259 (decision 2 says 253 are used with four windows); the 259-op budget is not checked by the draw slice.
* Draw-list and document layouts are proposals of the slices, not the compositor's encoding.
* Not wired to the desktop profile; the shipping desktop image was not measured with cssom linked.

### 5. Owner decisions pending

1. Accept the partition of section 2, in particular whether the compositor stays in the kernel or becomes its own domain.
2. The exit trigger of section 1 (cap reached, or text or images needed) or an earlier date; and whether any further slice may enter the kernel image before then.
3. The object context string and signer set (section 3: `"AIUEOBJ1"` is a placeholder), and whether renderer objects get a version floor.
4. The byte layouts of the three regions and the event and draw-list encodings (still open above); the two slice layouts are proposals.
5. The scope of JUN-919 (which user-target capabilities to build first: text segment above 4 KiB, store primitive, bounded strings and records, division) and who owns that compiler work.
6. The draw-op budget: 255 in the slice region against 259 in the kernel.
