# Shared native text-edit component

`src/browser/text_edit.kotoba` is the canonical native editing reducer. It
retains all13 public editing operations, with explicit state/options schemas.
The native state uses selection-start/selection-end fields and a composing
boolean; caret and selection positions retain the hosted UTF-16 convention.
Native strings remain UTF-8. The boundary helpers map UTF-16 positions to UTF-8
boundaries and snap positions inside a real surrogate pair before editing.

The fixture `test/native/text-edit.kotoba` exercises Japanese/emoji insertion,
left/right movement, direct caret placement inside a surrogate pair, selection
replacement, forward/backward deletion, select-all, extended selection and
composition start/update/commit. Its native verdict is zero. These are explicit
golden vectors, not a claim that the former hosted parity suite has run.

`scripts/check-shared-native.py` discovers and hashes the actual dependency
graphs, writes exact KSL1 locks, checks every declaration, compiles with Amu,
then executes the emitted artifact on a native Linux kernel. Python stages
bytes and observes the Kotoba verdict; it does not emit machine code or execute
the reducer. ARM uses a native packed artifact. x86 uses the native KX64 runner.

The complete shared CSSOM/layout and Browser surface/input graph is still a
separate gate. The existing AIUEOS Browser-frame2 desktop remains a behavioral
adapter until that graph and the kernel value runtime are qualified. Itonami
agent-first dapps and persistent restart/crash restoration depend on this gate.
