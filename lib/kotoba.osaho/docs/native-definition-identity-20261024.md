# Canonical native definition identity

The native implementation consumes the explicit Amu Form domain and retains
payload version 2. The six required sealed inputs, semantic named-effect
rows, type tags, recursive tagged-value ordering and UTF-16 text order are
unchanged. Name aliases do not participate. SHA-256 hashes exact CBOR bytes
in pure Kotoba; no ambient digest provider participates.

All ten unmodified frozen vectors pass canonical-byte and CID comparison.
Additional native checks cover exact i64 boundaries, f64 negative zero,
binary data, keyword/string distinction, semantic wire-row bridging,
malformed inputs and lock admission. Entry verification precedes coverage;
empty resolved input cannot satisfy a pinned dependency.

Native i64 values are exact across the full signed range. They normalize to
the same decimal-text tag as an explicit i64 wrapper, without the former
JavaScript 53-bit prerequisite. Historical wrapper keys retain their original
namespaces so existing definitions are not reinterpreted as ordinary maps.

`alpha_normalization.kotoba` owns positional renaming of params, let,
result-match-of, variant-match and option-match. A single counter crosses all
scopes; let values use the outer scope, branch scopes restore it, and ref
type vectors retain schema names. Scalar conversion is an explicit typed
function argument. Refusal verification reports the caller's chosen keyword.
The original unhandled-binder limitation is not a claim that this walk knows
the compiler's operator table; adding a binding operator requires updating
the owning compiler and this walk together.

Native ARM Linux tests pass using the existing measured Amu main root and
the FS2 compiler candidate. They do not establish compiler KIR/SCC wiring,
all downstream callers, package-lock integration or x86/public CLI admission.
The original host source, suites and frozen vectors remain migration evidence.

## Reproduction

On native ARM Linux, run `python3 test/native_identity_gate.py --compiler PATH
--compiler-sha256 SHA256 --amu AMU_CHECKOUT --cbor CBOR_CHECKOUT --multiformats
MULTIFORMATS_CHECKOUT --output NEW_DIRECTORY`. The observer stages exact KSL1
inputs and native processes. Kotoba implements the frozen vector checks,
semantic effect bridge, admission/coverage, alpha renaming and refusals.
The receipt identifies the measured Amu main root and every input digest.
