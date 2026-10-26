N2 tranche-one measured blocker (2026-09-04, compiler 13d2f5df):

The x86_64-aiueos-kernel-v1 native target admits exactly ONE :bool-result
call site per compiled graph. Measured minimal repros (all at pinned amu):

  1 call site  (contiguous? once, reused twice)  -> compiles, exit 0
  2 call sites (contiguous? x2, or acceptable?+contiguous?,
                or duplicate?+contiguous?)        -> :kotoba/target-rejected

tcp_stream.kotoba (ADR-0134 tranche one) needs 6 :bool call sites
(acceptable? x1, duplicate?/trimmed-away?/contiguous? x3/queue-full?),
so the module cannot compile until the compiler admits N typed boundaries
or provides a :bool->i64 boundary coercion.

Also measured:
- dma + :bool fn (1 call site) compiles — privileged ops and ONE typed
  boundary coexist (contradicts the earlier bisN read).
- requiring tcp.state-core into a kernel graph still fails (amu#611)
  — separate blocker, restatement approach stands.

Unblock options (owner decision):
  A) upstream amu/kotoba-kir: admit multiple typed boundaries on native
     targets (the real fix; unblocks N2 and the SSH T2+ tranches which
     have the same shape)
  B) extend org-ietf-tcp with :i64-returning twins of the five decision
     fns (upstream change, keeps parity suite as oracle)
  C) rewrite tcp_stream to route all six decisions through one dispatcher
     with a single :bool call (tight, but the dispatcher must hardcode the
     decision table — conflicts with cores-as-authority)

Evidence artifacts: /tmp/n2-bisN-repro/bist*.kotoba, /tmp/n2-bis*.ELF
