# Native physical working-directory provider

Tracking: [JUN-236](https://linear.app/kotobalabs/issue/JUN-236),
[JUN-201](https://linear.app/kotobalabs/issue/JUN-201), Kotoba Labs.

This source candidate completes the `:sys/cwd` operation (catalog wire 40)
inside the canonical C1/C3 gate. It returns the physical directory captured
at process startup. The existing `linux_static_paths.kotoba` startup uses raw
Linux `getcwd` (x86_64 syscall 79, aarch64 syscall 17), checks the absolute
path, strips its terminating NUL and stores the length at data+1032. It does
this before the temporary `fchdir` used to discover a filesystem scope root.
The original cwd buffer remains separate from that root's buffer.

The new handler consumes that existing buffer; it does not read `PWD`, run
`pwd`, ask callers to precompute a directory or introduce a C/hosted helper.
The buffer address is taken from the same admitted layout whose private
4096-byte span is checked by the path component. Source acquisition through
Git and filesystem scope admission retain their own roles.

## Gate, result and refusal contract

- C1's existing grant/kind checks run before dispatch. Its provider 0 for
  wire 40 is routed to static handler 12 by the paired owning Amu decision.
  Provider 0 still distinguishes entropy 23 and spawn 20; other wires refuse.
- The only request is the empty string. A nonempty request traps, and a
  failed/nonabsolute startup capture (zero length) also traps. There is no
  empty-string success or environment fallback.
- A valid captured length is 1..4095 bytes, excluding NUL. The handler asks
  the sealed owning decision's op 6 to admit the complete pool charge, then
  copies the exact span through the existing intern/pair allocation code.
- The common finish path resolves the returned handle and validates UTF-8.
  Invalid UTF-8 paths, exhausted bytes/cells and malformed handles retain
  the shared refusal/trap paths. A Linux filename is not assumed valid text.
- The cwd intern fragment has its own label prefix, separate from hash's
  fragment. Dispatch reaches handler 12 even when hash's conditional handler
  11 is absent. Existing handler ids 1..11 keep their meanings.
- Startup runs once before the guest. Calls sharing the context remain
  serialized. This operation discloses only the captured process directory;
  it neither grants arbitrary filesystem access nor changes the directory.

The Amu candidate adds `kotoba.compiler.working-directory/current`, which
calls wire 40 directly in canonical Kotoba. The old NBB sys namespace's
other process facts and consumers are separate migration inventory; this
operation does not claim that entire namespace or the input resolver has
been replaced.

## Integration state

Implementation source is in [native #205](https://github.com/kotoba-lang/kotoba-native/pull/205).
The matching route is in [Amu #1440](https://github.com/kotoba-lang/amu/pull/1440),
and the profile declaration is in [kotoba-lang #805](https://github.com/kotoba-lang/kotoba-lang/pull/805).
All remain draft candidates. Owning main still lacks the route/declaration.
Do not activate a declaration before admitted native implementation, actual
Amu-produced sealed decisions and exact reviewed source/lock integration.

Only source forms, API/record/call structure and source digests were read.
No project implementation, compiler, assembler, emitted artifact, native
admission, syscall/runtime or test was executed. Actual cwd/refusal/resource
behavior, full native lock authoring/replay, required ABI/helper coverage,
whole self-rebuild and the two native CDCI gates remain open.
