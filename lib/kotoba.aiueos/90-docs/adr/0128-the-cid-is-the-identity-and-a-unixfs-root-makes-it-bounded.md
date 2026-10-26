# ADR-0128 — The CID is the identity, and a UnixFS root makes it bounded

Date: 2026-08-31

## Status

Accepted for the two objects and their executed contracts. NOT linked into
`KERNEL.ELF`, and the first version of this line understated why: it said the
gap was amu's `kotoba-native` pin. It is not. See *What this does not claim*.
No boot, QEMU or physical, has run either object, and nothing here claims a
physical result.

## Context

Two things were true at the same time and did not fit together.

**The device already fetches content-addressed artifacts.** ADR-0118 pulls
models from `https://ipfs.kotobase.net/ipfs/{cid}` and ADR-0122 pulls loader,
kernel and initramfs the same way, each with an exact byte count and SHA-256.

**Nothing on the device reads a CID.** `aiueos.value-runtime-cas-verify`
compares a block against 32 bytes, and its contract declares
`:identity {:cid-version 1 :codec :dag-cbor :multihash :sha2-256
:digest-bytes 32}` beside it. That declaration is not a check. The caller
asserts all four fields; the machine decides only that some digest it was
handed matches some bytes. A CID is therefore a name that lives entirely
outside the machine — a URL with a hash next to it.

There was also a bound nobody could cross. SHA-256 here caps a block at 12,288
bytes. The artifacts are a 10.9 GB GGUF (ADR-0116) and a multi-megabyte
`KERNEL.ELF`. More memory does not help: the C-free profile maps the first GiB
and records at most 256 allocated pages (ADR-0039/0040).

And under both, a third: **no byte-walking object here had an off-target
oracle at all.** `kir/execute` refused `kernel-load-u8` outright, so
`contracts/dhcp-reply-valid-v1.edn` writes `:verification {:off-target
:impossible}` in its own words, and
`scripts/aiueos/verify_value_runtime_cas_verify.clj` does something worse:
with no way to run the object it re-implements SHA-256 in Java and compares
*that* against the contract's own expected values. Its six vectors pass
whatever the compiled object does. Deleting the object's body and leaving a
correctly-named export would not have failed it.

## Decision

### 1. `aiueos.cid-v1-admit` — the machine decides which CID it holds

`(cid, cid-length, block, block-length, scratch) -> reason code`. Zero admits;
1..8 name the clause, ascending with depth into the CID and then the block. It
reads the four prefix bytes — version 1, a permitted codec (`0x55` raw,
`0x70` dag-pb, `0x71` dag-cbor), multihash `0x12`, digest length `0x20` — and
then hashes the block and compares against CID bytes 4..35 in fixed work.

There is no `required-codec` parameter. The codec a caller wants is the codec
in the CID the caller passes; a requirement that comes from structure instead
— *the links of a UnixFS file node must be raw leaves* — belongs to the object
that knows the structure. The ABI admits five parameters, and this is not one
of them; `output` and `workspace` are derived from one `scratch` region
through `kernel-subregion`, so the narrowing is checked rather than assumed.

Reason 7, `sha256-refused`, is declared and **not** exercised, and the contract
says why: the object passes the literal 352 workspace length and reason 6 has
already bounded the input, so `aiueos-sha256` cannot return 0 there. The
branch stays so a later change to either bound cannot silently compare against
an output buffer nothing wrote. Writing a vector that claimed to reach it
would be the theatre this work exists to end.

### 2. `aiueos.unixfs-file-admit` — the bound stops mattering

`(node, node-length, expected-links, expected-filesize) -> reason code`, 0..17.
A UnixFS file root names its children by CID, so an unbounded artifact becomes
bounded blocks verified one at a time against one name. This object decides
the root: canonical dag-pb links (Hash 36 bytes, empty Name, Tsize), a UnixFS
header saying File, and the two arithmetic identities that bind the header to
the manifest — one blocksize per link, and their sum equal to the declared
filesize. The caller then admits each leaf with `cid-v1-admit`.

Only the canonical go-unixfs encoding is admitted. Being permissive would cost
parser surface and buy nothing: the block is content-addressed, so its bytes
are already fixed by the CID that named it, and a second encoding of the same
node is bytes no CID here will ever name.

Every load it performs is behind a length it checked first — in particular a
link's declared inner length is compared against the canonical minimum of 42
*before* any inner byte is read, because a load past the window is UD2, and
that is the kernel dying on bytes an attacker chose rather than refusing them.

### 3. Both are verified by executing them

kotoba-kir `10fa46ce` takes an optional memory image, so `kir/execute` can now
run an object against caller-supplied bytes. The runners ask the object --
since 2026-08-31 all three are one nbb script,
`os/aiueos/scripts/verify-admissions.cljk`, with no JVM anywhere in the
chain. They carry floors: a
minimum vector count, and a requirement that every reachable reason code was
actually produced by some vector. A run that executed nothing cannot return
what a run that executed everything returns, and a `:kernel-memory-unavailable`
trap — an old kotoba-kir — makes the runner print *REFUSING TO REPORT A PASS*
rather than a green line.

## Evidence

Measured 2026-08-31 on this workstation, load average 117 (the number is next
to the measurement because it explains the wall clock, and because it is not a
property of the code).

| | Result |
|---|---|
| `cid-v1-admit` | 14 vectors, 1 trap vector, reasons 0,1,2,3,4,5,6,8 all observed, reason 7 declared unreachable and not observed, `:imports []`. 4m41s wall / 143s CPU on the JVM runner; 360s on the nbb one that replaced it — almost all of it the two 12,288-byte vectors in a tree-walking interpreter |
| `unixfs-file-admit` | 22 vectors, all 18 reason codes observed, `:imports []`. 0.9s on nbb |
| kotoba-kir | 18 new tests / 33 assertions on both runtimes; full suites 168 tests / 642 assertions (JVM) and 29 / 60 (nbb) |
| kotoba-native | 220 tests / 2533 assertions |

Both suites were shown to discriminate, and each mutation failed the vector
that names it — not merely some vector:

| Broken | Failed |
|---|---|
| every codec permitted | `:unassigned-codec`, expected 3, got 0 |
| any non-zero CID version accepted | `:cid-version-two`, expected 2, got 0 |
| a 35-byte CID accepted | `:cid-thirty-five-bytes`, expected 1, got 8 |
| any link Name length accepted | `:name-not-empty`, expected 4, got 0 |
| blocksizes need not sum to filesize | `:filesize-nine-blocksizes-eight`, expected 17, got 0 |
| link bound raised from 32 to 1000 | `:thirty-three-links`, expected 7, got 16 |

The UnixFS vectors are not invented. `unixfs.file/build` in
`tech-ipfs-specs-unixfs` produced the two admitted nodes, that implementation
is pinned against kubo 0.41 CIDs, and every refusal vector is one of those two
nodes with one named byte changed. The admitted roots are
`bafybeidi3txkchykjupk3j4wfbwbzgj3skzhk2ey6hbmkgviaj7vrx4p64` and
`bafybeicfgk73jc55jyh5wtzebapnog537ijtwzhesiwvntivij56tblw5a`; the CID
vectors include `bafkreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku`,
the raw CID of zero bytes that ADR-0082 already fetches over TLS.

## What this does not claim

- **Neither object is in `KERNEL.ELF`, and the gap is not a pin bump.** The
  checked-in `os/aiueos/kotoba/*.o` are produced by amu `9cf3a0a` -- **502
  commits behind amu main** -- which pins kotoba-native `a60da444`, itself 222
  commits and ~3,000 lines of codegen behind the revision carrying the two new
  export rows. `reproduce-kotoba-kernel-object.sh` already records why that
  pin has not moved: five objects were compiled at the tip and compared
  against the committed bytes, and **all five differ**, so taking the advance
  means regenerating all 37 objects and every pinned digest in
  `build-uefi.sh`. That is a change to the shipped kernel and needs its own
  boot evidence; it is not a side effect of adding a decision. Measured again
  2026-08-31 -- the distances above are this session's, not quoted from the
  script's comment.
- **Neither object is in `qualification/tcb-inventory.edn`,** and that is
  correct today: they are not yet in the trusted computing base because they
  are not yet in the kernel. They belong there the moment they are linked.
- ~~**`value-runtime-cas-verify` is untouched.**~~ Converted on 2026-08-31: its
  verifier executes the object. The conversion's first finding was that
  `:digest-length-rejected` is named for a check that does not exist -- the
  object passes the literal 32 to `aiueos-digest-equal`, so the vector is
  refused for a digest mismatch and the Java model had agreed by coincidence.

- **All three verifiers left the JVM on 2026-08-31.** They are one nbb runner,
  `os/aiueos/scripts/verify-admissions.cljk`. Everything under
  `kotoba.compiler.core/compile-project` was already portable -- the linker
  (`kotoba.compiler.project`), the frontend (`kotoba.sema`), the lowering and
  the interpreter (`kotoba.kir`) are all `.cljc` -- so the JVM was carried by
  one `.clj` wrapper and one printer. The printer is amu#714: `source-text`
  rendered ClojureScript BigInts as `#object[BigInt 42]`, which the reader then
  refused, so the portable linker failed for every project containing a number.
  The cost is in the receipt and is not hidden: 0.9 s for the UnixFS contract,
  360 s and 302 s for the two that hash 12 KiB blocks, against roughly 200 s
  each on the JVM.
- **The OTA and model-channel paths still verify by manifest digest.** Making
  `os-update` and the model channel *use* these objects is the next step, and
  it is what turns a URL with a hash beside it into a name the device checks.
- **`cid-v1-admit` in the interpreter is slow** — minutes for a 12 KiB block.
  That is the oracle's cost, not the kernel's; the native object is a few
  hundred instructions per SHA-256 round.

## Related

- aiueos ADR-0013 (C-free ledger), ADR-0082 (the empty raw CID over TLS),
  ADR-0118 (kotobase IPFS model channel), ADR-0122 (signed A/B OS update)
- kotoba-native ADR-0036 (the JVM packager is `elf64.clj`, and it is an
  allowlist — both twins carry the new rows)
- root ADR-2608160100 (block → pack → object), ADR-2608153500 (the maturity
  gap ledger, whose *content-addressed OS image distribution: 無* row this is
  the first half of)
