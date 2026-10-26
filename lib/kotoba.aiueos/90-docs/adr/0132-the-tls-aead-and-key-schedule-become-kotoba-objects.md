# ADR-0132: The TLS AEAD and key schedule become Kotoba objects

## Status

Accepted (2026-09-02)

## Context

`kernel/tls13.c` (827 lines) and `kernel/tls_aes_gcm.c` (275 lines) hold every
TLS 1.3 decision this OS makes.  Three primitives had already left C --
`kotoba_aiueos_sha256`, `kotoba_aiueos_x25519` and
`kotoba_aiueos_ecdsa_p256_sha256_verify` are called from tls13.c at :226, :362,
:535, :677 and :787 -- and what remained around them was not plumbing.  It was
the AEAD, the key schedule, the record layer and the handshake state machine:
the confidentiality decision, the integrity decision, and the decision about
which bytes become the key.

ADR-0015 draws the C boundary at MECHANISM.  "Are these the bytes the peer
sent, under the key we agreed" is not mechanism.

This ADR records the first two of five stages.  It does NOT claim the C is
gone: `tls13.c` and `tls_aes_gcm.c` are unchanged on disk and the kernel still
links and calls them.  What exists now is two compiled, executed,
vector-checked Kotoba objects that the C call sites can be moved onto.

## Decision

Two objects, both `--jvm-free` compiled for `x86_64-aiueos-kernel-v1`, one
export each, zero imports, one relocation.

**`aiueos-aes128-gcm`** (`kotoba_aiueos_aes128_gcm`, arity 5, 14,088 bytes,
sha256 `a3d22ecd5761e0273015267a7c3a59823fce94f545c9ee8b725b3728da665465`).
AES-128 and GHASH, FIPS 197 + SP 800-38D.  Contract:
`os/aiueos/contracts/aes128-gcm-v1.edn`.

**`aiueos-hkdf-sha256`** (`kotoba_aiueos_hkdf_sha256`, arity 3, 13,056 bytes,
sha256 `d1330d6fef9cd217c0d14c46788c83d041c65ebead30f15bb9cc2713a646a7e2`).
HMAC-SHA256 and HKDF-Expand-Label, RFC 5869 + RFC 8446 7.1.  Contract:
`os/aiueos/contracts/hkdf-sha256-v1.edn`.

Four decisions inside them are worth stating here rather than only in their
headers, because each one changes behaviour the C had.

### Zero is the success value, and that is deliberate

Both objects return a REASON CODE like `aiueos-dhcp-reply-valid` and
`aiueos-cid-v1-admit`, not a boolean.  The C returned 1 for success.  A call
site transcribed unchanged -- `if (aes128_gcm(...))` -- therefore accepts
exactly the records the object refuses.  The convention flip is loud on
purpose: stage 5 has to touch every call site anyway, and a silent flip is the
only thing worse than a loud one.

### Open authenticates before it decrypts

`aiueos_aes128_gcm_decrypt` ran `gcm_run`, which writes the plaintext, and
compared the tag afterwards.  Every caller checked the return value, so nothing
was exploited -- but the buffer held attacker-chosen plaintext for as long as
the caller took to look, and "no caller reads it" is a property of today's
callers, not of the code.  The object GHASHes and compares first and does not
reach `crypt-all` at all unless the tag matched.  The contract asserts the
BYTES, not just the reason code: `open-refuses-a-flipped-tag-bit` expects the
buffer to still hold ciphertext.

### The output of Expand-Label is exactly out-len bytes

`hkdf_expand_label` in C wrote a 32-byte `full` and copied `out_len` of it,
leaving 20 bytes of unrequested key stream in its stack frame for a 12-byte IV
derivation.  The object zeroes the tail, and the `expand-label-write-iv-twelve-bytes`
vector asserts the whole 32-byte slot rather than a prefix.

### HKDF-Extract is not a mode, and a long key is refused

RFC 5869's Extract is `HMAC(salt, ikm)` with the salt as the key, so it is mode
0.  The C's "an empty salt means 32 zero bytes" is not a rule either: HMAC
zero-pads its key to the 64-byte block, so an empty salt and a 32-zero salt
produce the same block.  Two vectors assert that from different inputs rather
than asserting it in prose.

RFC 2104's "a key longer than the block is replaced by its own hash" branch is
REFUSED (reason 3) rather than implemented.  No TLS 1.3 derivation reaches it;
an untested second path through a MAC is worse than a refusal.

### Sizes and derivations

The 256-byte FIPS 197 S-box is DERIVED, not transcribed: log/antilog for
generator 3, inverse as `alog[255 - log[x]]`, then the affine map.  Two
reasons.  A 256-arm nested `if` is the only other way to write a constant table
in this subset and `value-runtime-sha256`'s 64-arm one already needs
`--stack-size=4000` to analyse; and a derived table is CHECKED -- a wrong
construction fails every vector, where one mistyped byte in a transcribed table
fails only the inputs that touch it.

SHA-256 is inlined into `hkdf-sha256.kotoba` rather than required from
`aiueos.sha256`, and the copy is bounded at 192 message bytes rather than
12,288.  See "measured" below: a multi-module kernel object cannot be packaged
at all today.

## Measured

Everything below was run on 2026-09-02 against amu at `b1fdaad2` plus the
kotoba-native bump described under "Pins".  The machine was at load average
~150 throughout; the elapsed times are the interpreter's, not the object's.

### The objects

```
amu compile os/aiueos/kotoba/aes128-gcm.kotoba \
  --target x86_64-aiueos-kernel-v1 --output aes128-gcm.o --jvm-free
  -> :ok true, artifact-bytes 14088
python3 os/aiueos/scripts/verify-kotoba-kernel-object.py aes128-gcm.o <sha> \
  kotoba_aiueos_aes128_gcm
  -> AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1
     export=kotoba_aiueos_aes128_gcm imports=0 relocations=1
```

and the same for `hkdf-sha256.o` (13,056 bytes,
`export=kotoba_aiueos_hkdf_sha256 imports=0 relocations=1`).

`aes128-gcm.o` was compiled twice, once at kotoba-native `9e6eb46` and again
at `77d4f98` after the second allowlist row landed, and the two files are
byte-identical -- the added row and fuel arm do not move an object that does
not use them.

### The vectors

```
node --stack-size=60000 kbb --backend sci --classpath ... \
  os/aiueos/scripts/verify-admissions.cljk os/aiueos/contracts/aes128-gcm-v1.edn
CONTRACT :aiueos.aes128-gcm/v1 vectors=15 traps=1 memory=16
         observed=0,1,2,3,4,5 ms=586752
```

Every ciphertext and tag in that contract agrees byte for byte with THREE
independent implementations: `aes.gcm/seal` from kotoba-lang/org-nist-aes (pure
cljc), OpenSSL through node's `crypto.createCipheriv('aes-128-gcm', ...)`, and
the C being replaced.  The published SP 800-38D empty-input tag
`58e2fcce...455a` is among them.

That third agreement is worth naming precisely, because it is the parity
evidence stage 5 will need for the AEAD: **the object passes
`aiueos_aes128_gcm_selftest`'s own expectations.**  The C's `expect_tag`
(`58e2fcce…455a`), `expect_ct` (`4faa3ccb…bde7`), `expect_t2`
(`97f7b291…003e`) and `expect_t3` (`2b956e81…21ee`) are, byte for byte, the
first three vectors of `aes128-gcm-v1.edn`.  The old and the new implementation
are not merely both correct; they are checked against the same numbers.

A remark on those numbers, since they read like published GCM test vectors and
are not quite: the C's comment says its 64-byte expectations were "measured
against cryptography.hazmat" rather than transcribed, because the published
SP 800-38D appendix vector for that key and IV carries 20 bytes of AAD and a
60-byte plaintext.  The 64-byte empty-AAD companion is a derived vector.  Two
further independent implementations now agree with it, which is what this ADR
adds to the C's word for it.

The HKDF contract's values are RFC 4231 section 4 (the two HMAC vectors) and
RFC 8448 section 3 for everything else, taken from the extraction
kotoba-lang/org-ietf-tls keeps at `resources/rfc8448_section3.edn`, whose header
records the source RFC's SHA-256.  The RFC prints the PRK, the context hash,
the info string and the expanded output of each step separately, so each vector
fixes the input and the output of one step of the real key schedule rather than
a round trip through this implementation.

### The gates were shown to fail

A reduced two-vector copy of the AES contract (floors lowered to match, so a
floor cannot be what fires) passes unchanged:

```
CONTRACT :aiueos.aes128-gcm/v1 vectors=2 traps=0 memory=2 observed=0,5
```

With `tag-diff` in the object changed to compare ONE byte instead of sixteen:

```
FAILED: vector mismatch
   {:vector :open-refuses-a-flipped-tag-bit, :expected 5, :actual 0}
```

which is the right failure for that break -- the vector flips the LAST tag
byte, so a first-byte-only comparison admits it.

With the object restored and one nibble of the contract's expected tag changed:

```
FAILED: memory mismatch
   {:vector :sp800-38d-empty-seal, :region :tag, :offset 32,
    :expected [... 164 231 69 91], :actual [... 164 231 69 90]}
```

which is the right failure for the OTHER axis, and shows the memory assertions
this ADR adds to the runner discriminate rather than decorate.

## Two upstream facts measured on the way, both worth recording

**No `.kotoba` object using an i64 shift can be compiled JVM-free.**
`i64-shift-left`, `i64-shift-right` and `u64-shift-right` -- landed by
ADR-2607254600 for Keccak-f[1600] and u256 limbs -- are refused on the
JDK-free route with `runtime KIR i64 shift count rejected`.  The cause is
`kotoba.verifier`, which re-derives the frontend's "count must be an integer
literal in [0,63]" rule with `integer?`; ClojureScript lowers the KIR literal
to a BigInt, and `(integer? 4n)` is false.  Measured with a three-line probe
whose only operation is `(u64-shift-right 256 4)`; the KIR node prints as
`(u64-shift-right #object[BigInt 256] #object[BigInt 4])`.  The verifier's own
comment says "`integer?` is the right predicate on both runtimes here".  It is
not.  Both objects here use `quot` and `*` by powers of two instead, which is
what `sha256.kotoba` already did.

**A multi-module kernel object cannot be packaged.**
`amu compile <src> --source-path <dir> --target x86_64-aiueos-kernel-v1`
refuses a namespace that declares `(:require ...)` with
`:kotoba.error/namespace-require-needs-project`, and `--unpinned` does not
change it.  That is why `cid-v1-admit.kotoba` has no committed `.o` beside it,
and it is why SHA-256 is inlined into `hkdf-sha256.kotoba` rather than
required.  The duplication is the one ADR-0021 already pays for between
`ipv4-checksum` and `ipv4-icmp-reply-valid`.

## What the runner gained, and why

`verify-admissions.cljs` could only assert a RETURN VALUE.  Every contract it
carried until now belongs to an object that DECIDES; these two TRANSFORM, and
for a transforming object a reason code of 0 says only that the object thought
it succeeded.  So `prepare` may now return `:expect-memory` and `run-single`
compares it against the image the object actually wrote, with a
`:minimum-memory-assertions` floor so that a contract declaring the floor and
then running vectors that assert nothing is a failure rather than a pass.

It also learned to name one refusal it was silently mis-reporting.  The
ClojureScript interpreter recurses once per Kotoba call, and this object's
GHASH is 4,565 calls deep per field multiplication; `kir/execute` reports host
stack exhaustion as `:fuel-exhausted` with `:host-stack-exhausted true`.  At
`--stack-size=4000` that is TIMING-DEPENDENT: measured here, the first vectors
of a cold run trapped and later ones passed, because V8 shrinks the
interpreter's frames once it tiers up.  The runner now refuses with a message
naming node's stack, and each contract states the size it needs in
`:verification :node-stack-size` (60000, with `ulimit -s 65520`, for both of
these).

## Two entries this repaired on the way

`aiueos.kotoba-object-reachability-test` was RED on main before any of this,
for `cid-v1-admit` and `unixfs-file-admit`: both sources exist, no script
builds either, and neither was listed in `not-built-here` -- which is exactly
the state that list exists to make impossible.  Verified against
`kotoba-lang/main` rather than assumed: both `.kotoba` files are present there,
`git grep kotoba/<name>. -- os/aiueos/scripts` finds nothing, and the list
contains neither name.

They are declared now, because the measurement this ADR had to make answers
them.  `cid-v1-admit` CANNOT be built here at all -- it declares a `:require`,
so it is a multi-module project, and no multi-module object can be packaged for
this target.  `unixfs-file-admit` is single-module with no committed object and
nothing calling it; what executes both is `verify-admissions.cljs`, which links
and runs them.

Adding entries for the two objects this ADR introduces without fixing those two
would have left the suite red and made "the reachability test passes" a claim
about a subset.

## Pins

kotoba-native `kernel-object-entries` is a closed allowlist, so both exports
had to be admitted there first.  Two commits, both in BOTH twins (`elf64.clj`
and `elf64.cljc`, because the JVM loads the first and nbb the second):

* `9e6eb46e7f45d5cb079912b34da9f2aa4012e326` -- `aiueos-aes128-gcm`, and an
  `aead-fuel?` arm at 250,000,000.
* `77d4f9801cb4d0b5c68588a1efc48f837f5e6e53` -- `aiueos-hkdf-sha256`, and an
  `hkdf-fuel?` arm at 10,000,000.
* `81d6644eead9f6a6900cd35736ef94f1f22a1218` -- `aiueos-tls13-record`, which
  ADR-0133 introduces and which joins the `aead-fuel?` arm.

Both fuel arms are SEPARATE arms rather than names added to an existing set,
for the reason `elf64.cljc` already gives about `dhcp-fuel?` and
`context-fuel?`: measuring one must not silently move the other.  Both state
their computation and say it is computed rather than executed.
`kotoba.native.elf64-twin-parity-test` ran green after each (168 then 170
assertions).

The amu that produced these objects is `b1fdaad2` with its kotoba-native pin
advanced to `81d6644` and `deps-lock.edn` regenerated.  That amu is NOT landed;
it exists as a worktree.  Reproducing these `.o` files requires the same bump.

Both objects were compiled again after the third row landed and are
byte-identical to the ones committed here.  An allowlist row does not move an
object that does not use it -- which is the same property the kotoba-native
side asserted when it added the DHCP rows, and it is checked rather than
assumed.

## What is NOT done

* **The C is unchanged.**  `tls13.c` is still 827 lines and `tls_aes_gcm.c`
  still 275.  Nothing links these objects; `build-uefi.sh` is untouched and
  the kernel still calls the C.  Stages 3 (record layer + key schedule),
  4 (handshake state machine + certificate policy) and 5 (delete the C bodies
  and move the call sites) are not started.
* **Neither object has ever run on a CPU.**  Every result above comes from the
  KIR reference interpreter with a supplied memory image.  The machine code was
  produced and structurally verified; it was not executed.
* **The parity roster is not whole.**  `qualification/jvm-free-object-parity.edn`
  still describes 66 objects under compiler tree
  `1ec79803dfc45c041391c1f2865f32c74179455266d312434562a0e8e9ec8cf4`, and these
  two are not in it.  Regenerating it means compiling 67 sources twice each,
  and the JVM route measured ~8 minutes per object on this machine at this load
  -- about nine hours, during which the script's own `tree-digest` guard would
  refuse the whole run if anything touched the compiler.  A scoped receipt for
  exactly these two, produced by the same script against a root containing only
  them, is at `qualification/jvm-free-object-parity-tls13.edn`; it names its own
  `:scanned 2` and its own compiler tree digest rather than being merged into a
  file whose header names a different one.  It covers all three objects,
  including ADR-0133's, and reports MATCH 3 DIFFERS 0.

  It also records something the main roster does not, and the difference
  matters.  The script compares the JVM-free ROUTE against the JVM ROUTE, so
  `:match` says the two routes agree -- not that the agreed bytes are the ones
  committed beside the source.  For these three they are, and that was checked:
  each `:sha256` in the scoped receipt is the sha256 of the committed `.o`.  In
  `jvm-free-object-parity.edn` they are not.  It records `sha256` as 9,912
  bytes / `db5effa8…`, while the committed `sha256.o` is 17,792 bytes /
  `af378b06…` -- which is what `provenance.edn`, generated from the files
  themselves, reports.  That roster is a receipt about a compilation run; it is
  not an attestation of the tree, and the two are easy to read as the same
  thing.
* **Most committed objects do not reproduce at this compiler**, which is the
  ADR-0129/0130 drift seen again at a newer amu.  Of seven recompiled here, ONE
  (`ime-romaji`) reproduces byte-for-byte and six do not -- `sha256`, `x25519`,
  `dhcp-reply-valid`, `ipv4-checksum`, `tcp-segment-valid` and `pic-disable`
  all come out smaller than the committed artifact.  An eighth, `ecdsa-p256`,
  did not finish inside a 900-second timeout and is UNMEASURED rather than
  either.  Nothing in this ADR depends on that -- the three objects it
  introduces were compiled here and committed here -- but a reader who assumes
  the tree is reproducible at the tip would be wrong.
* **The largest record executed is 64 bytes.**  The object's bound is 12,288.
  The cost is linear in blocks and the code path is uniform -- `crypt-all`
  narrows ONE CIPHER BLOCK at a time through `kernel-subregion`, so the first
  block of a 32-byte record takes the same path as the 768th block of a full
  one -- but a full record was not run, and the contract says so in
  `:largest-executed-record-bytes`.
* **Nothing here says K16 HTTPS works natively.**  It does not; the HTTPS path
  is still the C.
