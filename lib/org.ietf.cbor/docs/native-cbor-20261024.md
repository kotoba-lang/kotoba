# Canonical native CBOR

`cbor.core` exposes the typed fragment API and generic encode/decode over
the explicit `cbor.value` domain. `cbor.form` is an optional compiler Form
adapter; the codec has no dependency on a compiler or a host runtime.
All bytes, integer and tag arguments retain their exact bit patterns.
Failures use the typed keyword abort channel and checked result APIs.
The public tag accessors are retained; `tag-number` returns the complete
unsigned 64-bit argument as its native i64 bit pattern.

The native suite covers fragments, generic arrays/maps, ordered maps, tags,
64-bit signed and unsigned boundaries, negative zero, UTF-8, malformed
input, finite-number refusal and depth 512 acceptance / 513 refusal.

## Complete historical corpus

The original generator and `test/cbor/golden.edn` remain unchanged.
`native_golden_values.kotoba` transcribes all 367 edge values and all 2000
Park–Miller values, preserving the generator's index progression, recursive
shapes, finite drop/take behavior and last-value map replacement. No legacy
encoder or host numeric conversion executes.

The full native encode run checks exactly 2367 values. There are eight
explicit changes from the historical double-based input representation:

| Index | Native meaning |
| --- | --- |
| 13, 295 | Exact integer 9007199254740993 |
| 26, 27 | Exact signed i64 maximum and minimum |
| 297 | Exact integer -9007199254740993 |
| 302 | f64 negative zero, retaining its sign and type |
| 314 | f64 9007199254740994, retaining its type |
| 363 | Exact unsigned tag 18446744073709551615 |

Each change has an explicit expected byte literal in the native test. The
four lone-surrogate source cases have no native UTF-8 string equivalent;
the generator states their original replacement UTF-8 bytes explicitly.
No corpus entry is skipped, shortened or silently regenerated.

The independent decode/re-encode run also consumes all 2367 original frozen
byte strings through Amu's canonical repository reader. It pins the two
historical noncanonical cases: OrderedMap index 360 canonicalizes its key
order, and the double-rounded overwide zero tag at index 363 becomes `c001`.
The new exact maximum tag has a separate positive case.

Both full runs passed native ARM Linux using the existing measured Amu main
root as well as the FS2 candidate compiler. Source-locked build, execution,
owning-main integration, package locks and public CLI admission are separate
states. x86 execution, complete downstream caller migration and package-lock
integration remain open.

## Reproduction

On native ARM Linux, run `python3 test/native_gate.py --compiler PATH
--compiler-sha256 SHA256 --amu AMU_CHECKOUT --multiformats MULTIFORMATS_CHECKOUT
--output NEW_DIRECTORY`. Python stages exact input locks and observes native
processes. The four Kotoba fixtures own fragment/generic assertions, Form
adapter bounds, all frozen byte roundtrips and all source-value encodings.
