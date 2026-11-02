# Native signed-envelope byte admission — JUN-757

`kekkai.envelope-region/verify` consumes the existing signed-netmap envelope
format. It does not replace the wire format with a digest signature or a new
binary roster. The signature covers the exact decoded payload bytes.

The8 arguments are `(work,actual-work-bytes,envelope,actual-envelope-bytes,
authority,authority-bytes,output,actual-output-capacity)`. Authority is an
independently configured32-byte Ed25519 public key. The caller must enforce
its configuration/approval provenance; bytes from the envelope cannot enroll
themselves as an authority. The verifier checks exact RFC8410 Ed25519 SPKI
DER and its raw key against that configured pin before authenticating data.

Return is the verified raw payload length0..65536, or-1. Zero is a valid
empty signed payload, not a refusal or a valid empty roster. A parsed roster
and its semantic admission are a later interface. The existing public fixture
contains pending/expired nodes; accepting its signature does not authorize
those nodes or establish present-day validity.

The bounded profile uses98304 bytes of caller-owned work and accepts an
envelope up to98304 bytes. That accommodates a canonical Base64 payload of
65536 bytes plus this producer's envelope fields. Larger artifacts/messages
need their own streaming admission; these numbers do not redefine the legacy
protocol's universal limits. Work contains metadata/public key/signature,
SHA state at512, padding at1024,16384 bytes of Ed25519 work at4096, and the
private decoded payload at32768. Output capacity is0..65536. Work and output
must be disjoint from one another and from both immutable inputs. Read-only
inputs may share storage. The caller provides real regions/actual lengths;
the arguments do not mint memory or permit forged capacities.

Shape refusals preserve all work and output. A processed call clears all98304
work bytes before and after processing. Every refusal preserves the output,
including a short output after successful authentication. Decoded bytes are
private until outer syntax, authority, SHA-256 and Ed25519 all pass. Only then
are they copied to output. The caller must retain exclusive ownership and
prevent mutation until subsequent payload parsing/admission; this API does
not turn a writable buffer into a permanent trusted object or capability.

The outer reader accepts precisely a flat EDN map of the four known keyword
keys, in any order, with ordinary unescaped ASCII string values, ASCII
whitespace and commas. It rejects duplicates, missing/unknown keys, escaped
strings, comments, namespace-map shorthand, reader forms, nested values,
non-ASCII/control bytes and trailing forms. This is the publisher's bounded
envelope profile, not a replacement for the general EDN reader. Strings hold
only canonical RFC4648 Base64 or64 lowercase digest characters. The decoder
rejects nonalphabet bytes, misplaced/excess padding and nonzero pad bits.
SHA-256 checks the decoded bytes; raw-message Ed25519 then applies the
canonical nonidentity prime-order authority policy from the shared OS owner.
No untrusted payload EDN is parsed by this component.

The SHA-256 round engine is the unchanged `aiueos.lib.sha256-stream`. Its
fixed64-byte blocks and existing `sha-blocks` are reused. The envelope owner
builds the bounded final padding as the existing ESP consumer does, because
the old `sha-final` tail entry requires a literal tail length in this compiler
profile. The legacy final entry remains exercised by a real full-digest
SHA-256("abc") known answer. Three published RFC8032 key/sign/verify examples
and altered-R refusals likewise exercise the retained legacy APIs. These are
actual checks, not dummy ABI stubs or removed exports. The diagnostic needs
these rooted legacy calls: an unused public helper with unknown caller
regions otherwise refuses during whole-project region checking. General
product/compiler closure remains a separate requirement.

Region lengths computed by a reader are passed through explicit function
parameters before deriving a view and passing its paired length. The adopted
compiler preserves that identity; repeated reader calls or an unknown local
return are not proof that two extents match. Failed E7106 probes are retained
rather than weakening region checks, replacing the compiler, increasing its
code cap or substituting a hosted verifier. The library's legacy
`AGENTS.md` statement that no module has a native gate predates the existing
wire-region NIC evidence; the code and source-bound receipts describe the
current bounded qualification, while whole control-plane coverage stays open.

`tools/envelope_region_reference.py` supplies public test bytes using only
published test seeds, the existing signed fixture, hashlib and the existing
independent RFC integer reference. The guest concatenates exact raw fragments
from a public blob; host-side parsing does not perform guest admission.
`tools/envelope_region_gate.kotoba` checks complete output/input/work bytes,
authority preservation, short-view/alias refusals and native return codes.
The final64KiB payload is separately read back by the private QMP observer.
The diagnostic packages but does not execute the existing user ELF, preserving
the actual ValueRuntime ABI/grants and two PT_LOAD segments.

The source-bound native run passes125 raw envelopes:55 accepted byte strings
and70 refusals. It includes every field order, empty/exact/short output,
Base64 padding and55/56/63/64-byte boundaries, the existing1206-byte signed
fixture, and65535/65536-byte payloads. Ten actual short/oversized/alias guards
complete. All ten separately booted authority/digest/signature/duplicate,
payload/SPKI pad-bit, wipe/alias, SHA-padding and output-on-refusal faults
complete all cases and are detected. The final125 return codes,98304-byte
cleared work and65536-byte payload also match independent QMP readback.

The21-module kernel has RX596992B/RW2359296B, with unchanged compiler2MiB
code cap, grants and actual11 ValueRuntime sources. Kernel, EFI, user ELF and
slot reproduce. All existing AIUEOS math/desktop sources remain byte-identical
to the previous qualification. The Kekkai NIC40 RX/11 response/27 refusal
regression also retains its previous source graph and native artifacts.

Failures stay visible: nine E7106 prototypes, one invalid negative-length
region constructor that halted before codec entry, and an initial authority
fault that removed a helper call and therefore failed compilation. None is
counted as a detected protocol refusal. Corrected bypass faults retain the
actual helper call while ignoring its answer. Two observer snapshots differ
only in those two mutation-data values; the receipt checks the exact
replacement and every control's native graph. Repeating the positive under
the final observer produces identical native graph/artifacts and results.

Evidence: [native envelope receipt](evidence/native-os-envelope-20261102/receipt.json).

Reproduce with `scripts/check-kekkai-region-os.py --component envelope` and
explicit compiler/packager/baseline/font/QEMU/firmware pins. Python stages,
hashes and observes; native Amu compiles/packages and the guest decides.
Runtime qualification and mutation results belong in the source-bound receipt;
source existence, a compiled image or this contract alone are not a passing
runtime result. Physical deployment and app installation are separate.

Still required: payload UTF-8/EDN schema parsing, roster identity/self/peer
bindings, monotonic versions/expiry/ACL/revoke and session teardown, trusted
clock/fresh entropy/protected keys, admitted app sockets/lifecycle, native Mac
and OS app installation, fresh operation consent, actual6600H/Mac peer
roundtrip/reconnect/native SSH/PQ and full L1/distributed OS release readiness.

References: [existing envelope publisher](../src/kekkai/envelope.cljk),
[RFC4648](https://www.rfc-editor.org/rfc/rfc4648),
[RFC8410](https://www.rfc-editor.org/rfc/rfc8410).
