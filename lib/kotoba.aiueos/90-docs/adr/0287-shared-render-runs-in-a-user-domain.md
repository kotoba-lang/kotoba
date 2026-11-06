# ADR-0287 — The shared Browser/CSSOM render runs in a user domain, not in the kernel image

Date: 2026-11-06

## Status

Accepted 2026-11-06 (owner: render outside the kernel image, "描画をカーネル外に出す"; the open questions below were answered
"おすすめで決定" with the recommended options, listed under Decisions on the open questions). Nothing here is implemented.

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
- **Floats: f64 in the user domain, conditional.** `cssom` uses doubles in 58 places and the hosted oracle is f64, so fixed point would add a parity risk. This holds only if the kernel saves and restores floating-point state on a CPL3 process switch; checking that (and fixing it if absent) is the first task of JUN-855. If it cannot be done, fixed point is the fallback and this line is reopened.

## Still open

- Measured size and speed of cssom in the user target (needs the first slice of JUN-855).
- Whether the kernel preserves floating-point state across a CPL3 process switch (read-only check first).
- The exact byte layout of the three regions and the event/draw-list encodings.

## Not verified

No renderer domain exists. The existence of the user target and CPL3 processes is read from ADR-0111, ADR-0175 and ADR-0211,
not re-run for this ADR.
