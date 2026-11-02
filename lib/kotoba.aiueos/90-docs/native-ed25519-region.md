# Raw-message Ed25519 and streaming SHA-512 — JUN-757

`aiueos.ed25519-region/verify` can now verify the exact raw-message transcript
needed by existing Kekkai signed-netmap envelopes. The previous OS signing
and verification API uses a fixed64-byte message layout; hashing a larger
payload to a new message would change its signature format. This profile
instead streams `R || A || message` into SHA-512 and applies the existing
canonical OS point/scalar engine. It is ordinary Ed25519, not Ed25519ph or
verification of a signature over an externally supplied digest.

This is an opt-in OS kernel component. It does not decode/verify the complete
envelope, choose or enroll an authority, consume a signed roster, admit a
device, check netmap versions/revocation, install a Mac/OS app or qualify a
production connection. Native envelope/payload parsing and caller authority
binding are still required before the result can authorize a peer.

The8-argument interface is
`verify(work,actual-work-bytes,public,32,signature,64,message,actual-bytes)`.
The caller owns at least16384 bytes; only the first16384 profile bytes are
used. The message is0..65536 bytes, including an exact empty region. Inputs
must be immutable and disjoint from that working region; read-only inputs may
share storage. Return1 accepts and0 refuses. Invalid shapes return before any
work write. Cryptographic paths erase all16384 profile bytes, including on a
bad key or signature. There is no heap, IO, external identity or trusted clock.
Larger messages and streaming artifact admission remain separate interfaces
and qualification work, not a newly imposed netmap protocol limit.

The opt-in authority policy requires a canonical nonidentity prime-order
public key (`[L]A = identity`), matching the existing native static Ed25519
authority policy. `aiueos.ed25519-verify` composes the existing point/scalar
operations and normalizes its1024-byte byte workspace and4096-byte field
workspace. Its `verify-hash` is a low-level transcript building block, not a
generic signature oracle for caller-provided hashes. The bounded public
`verify` entry owns transcript construction and erasure. The legacy public
key/sign/verify APIs and their point/hash math bodies are retained.

`aiueos.sha512-stream` owns4608 bytes: existing4096-byte round work, a128-byte
block at4096, byte count4224, used4232, phase4240, digest4256..4319 and
magic4320. `stream-init`, `stream-byte`, `stream-finish`,
`stream-digest-byte` and `stream-wipe` normalize actual capacities. Invalid
bytes, short state, overflow or wrong phase refuse without state changes;
digest access is restricted to a completed state. The upper and lower halves
of the128-bit bit-length field are emitted separately. The API accepts only
API-created states, serialized calls and immutable inputs; a supplied tag is
not proof of trusted state or persistence.

The round engine remains in `aiueos.sha512`; the point/scalar engine remains
in `aiueos.ed25519`/`aiueos.gf25519`. Only explicit shared math interfaces and
imports are added to the old modules. Legacy consumers use `:refer` for the
functions they actually call. This matters because the adopted compiler
generates an import stub for every export of an `:as` dependency. Expanding
the interfaces under old broad imports crossed the existing2MiB generated
code cap. Four such native refusals are retained. Moving the profiles and
using explicit imports keeps the44-module desktop admitted, with raw RX
2106368B instead of2107392B. No module or callable feature is removed. The kernel/user ABI, memory
grants and compiler cap are unchanged, as is the compiler image.

The source-locked19-module component retains the actual11 ValueRuntime
sources and two PT_LOAD segments (RX528768B/RW2359296B). Native kernel, EFI,
diagnostic user ELF and slot reproduce; the user ELF is packaged but not
executed. Public diagnostic data occupies only41443 bytes of the font's
previously empty tail; glyph/header bytes and the rest of that payload remain
unchanged. The existing256KiB request grant contains all work and records.

The local source-pin inventory previously omitted five already tracked files:
`ed25519.kotoba`, `sha512.kotoba`, `keyseal.kotoba`, `ed-entry.kotoba` and
`sha512-entry.kotoba`. They are now explicitly recorded as local additions,
with their previous HEAD hashes retained in the reasons and equivalence
receipt. No imported snapshot hash is invented. Checking every declared pin
does not establish that the entire library catalog is covered by that inventory.

Native execution checks all263 signature cases:210 pinned Wycheproof cases,
26 generated valid messages through65536 bytes,25 last-byte alterations,
the existing1206-byte Kekkai signed-netmap payload and an identity-authority
forgery. The117 Wycheproof valid cases pass and64 invalid cases refuse.
Its29 acceptable cases (8 small-order and21 mixed-order keys) deliberately
refuse under the authority policy; they are not relabeled as universally
invalid RFC signatures. The identity-key example satisfies the unguarded
signature equation but must not be admitted as an authority.

All264 streaming SHA-512 digests (lengths0..257,1023,1024,4096,12288,65536,
1048576) and262 legacy one-shot digests match independent expected bytes.
The three published RFC8032 public keys/signatures still match byte for byte
and their altered-R signatures refuse. Exact short views, oversized/aliased
input, invalid bytes/phases and refusal preservation are exercised. All input
bytes are compared after each signature call. Native per-call checks prove
profile erasure or shape-refusal preservation; a separate final readback
confirms the fixture's work is zero after its guard cleanup. The latter alone
is not evidence of per-call erasure. Counter2^61+1 length bytes and i64-max
overflow checks use synthetic private state, not huge real-message hashes.

All11 injected faults were detected after normal completion. They cover
transcript order, final message byte,
authority subgroup admission, S range, work erasure/aliasing, SHA rotations,
padding, high length, phase and overflow. Only normal terminal executions of
all cases/guards with intact outer canaries count as detected controls. The
receipt records native assertion failures and independently observed byte
mismatches; compile failure or timeout is not fault detection.

The legacy44-module images are independently regenerated and booted as a
pair. The checked-in `check-native-usb-desktop-pair-qemu.py` repeats the
qualified input-profile setup: Q35, PS/2 disabled,37-bit physical addressing,
xHCI root keyboard and hub-child mouse. Both consume synthetic Goal `aba`
and pointer delta20/10, present the resulting frames and produce identical
pixels. The private media remain unchanged. This is a technical QEMU
regression, not physical input acceptance or trusted operation consent.

Failures are preserved: an unexported-helper import correctly refused with
E6004; four desktop code-budget probes refused with E7104. An initial paired
observer incorrectly required idle redraws, and another omitted the adopted
37-bit/PS2-disabled USB fixture settings. Neither failed observation is
qualified. The corrected native pair and checked-in observer succeed. Earlier
successful crypto probes predate the final module separation and are kept as
superseded evidence rather than used as its qualification.

Evidence: [source-bound receipt](../docs/evidence/kekkai-native-ed25519-region-20261102/receipt.json).
Reproduce the component with `scripts/check-kekkai-region-os.py --component
ed25519` and its recorded compiler/packager/lock/font/QEMU/firmware pins.
The `--mutation` definitions and public corpus are in the same receipt.
Python stages/hashes/observes and supplies independent public expected bytes;
Amu compiles/packages and the native guest performs the cryptographic checks.

The complete signed-netmap consumer, immutable verified payload before parse,
configured authority pin, digest/envelope codec, signed roster/version/revoke,
fresh entropy/protected keys/monotonic clock, native app sockets and install,
actual Mac/6600H peer lifecycle/native SSH, PQ broker and whole L1/distributed
OS production release remain open. Constant-time and full cryptographic
package/release qualification are not claimed. PXE and management services
are not cut over by these local tests.

References: [RFC8032](https://www.rfc-editor.org/rfc/rfc8032),
[pinned Wycheproof data](https://github.com/C2SP/wycheproof/blob/d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9/testvectors_v1/ed25519_test.json).
