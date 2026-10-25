# source-chain

A per-agent, signed, append-only **source chain**, verified inside a Kotoba
guest compiled by [amu](https://github.com/kotoba-lang/amu) to native code
and run through amu's kexe loader. It is stage A of root ADR-2609261900
(agent-centric write plane): the write path where an agent writes only its
own chain, and no global consensus, gas or native token is involved.

The retired Rust `kotoba-dht` crate
(`kotoba-server/workspace/crates/kotoba-dht/src/source_chain.rs`) is the
reference for what is checked. It is a specification here, not a wire format
to stay compatible with.

## What the guest answers

`kotoba/source_chain.kotoba` exports six functions. All take granted
regions (base address and length handed in by the loader) and answer an i64.

| export | answers |
|---|---|
| `verify-chain base len` | number of entries in a valid chain (0 for an empty region), or a negative reason |
| `head-tag base len` | first 15 hex digits of the head entry's hash as a non-negative i64; `-7` for an empty chain; a negative reason when the chain does not verify |
| `fork-evidence a-base a-len b-base b-len` | `1` when two validly signed entries by the same agent share a seq but differ; `0` when they do not; a negative reason when either does not verify |
| `verify-warrant base len` | `1` when a warrant verifies together with the fork it carries as evidence, or a negative reason |
| `replay-balance base len n credit-limit` | an agent's mutual-credit balance **plus 2^50** (so every balance is a non-negative answer), or a negative reason |
| `validate-dna base len n mlen` | number of entries in a chain that lives under the DNA and whose every document is resolved and admitted, or a negative reason |

Negative reasons:

| code | reason |
|---|---|
| -1 | seq mismatch |
| -2 | prev mismatch (including a genesis entry that names a prev) |
| -3 | invalid signature |
| -4 | malformed message (not printable ASCII, or not the v1 layout) |
| -5 | agent mismatch (key bytes, the message's agent line, and the chain's first agent must agree) |
| -6 | region is not a whole number of entries (or records) |
| -8 | a warrant's evidence is not a fork |
| -9 | a warrant does not name its evidence (accused, seq, or either hash) |
| -10 | the balance fell below `-credit-limit` at some transfer |
| -11 | a transfer is referenced by no entry of the chain |
| -12 | a transfer is referenced by more than one entry (it would count twice) |
| -13 | the chain's agent is neither the spender nor the receiver |
| -14 | transfers are not in the order of the entries that reference them |
| -15 | a content document is missing, or its sha256 is not the entry's content |
| -16 | a content document is longer than the DNA's `max-content` |
| -17 | a content document's schema is not allowed by the DNA |
| -18 | the genesis entry's content is not the DNA id |
| -19 | the DNA manifest is malformed or not canonical |

Checks run in this order: malformed, agent, signature, seq, prev. An
untrusted entry is authenticated before its position is believed.

## Wire format (v1)

Entries are laid out back to back, 454 bytes each:

```
[agent Ed25519 key 32][signature 64][signed message 358]
```

The signed message is fixed-width ASCII, with every line ending in LF:

```
kotoba.source-chain/v1
agent:<64 hex: the same 32-byte key>
seq:<20 decimal digits, first two 0>
prev:<64 hex: sha256 of the previous message>   (64 '-' at seq 0)
ts:<20 decimal digits, first two 0>
policy:<64 hex: sha256 of the data-policy document>
content:<64 hex: sha256 of the content>
```

The entry hash, which the next entry's `prev` names, is the SHA-256 of the
message.

The message is text for a measured reason. On the kexe loader,
`:hash/sha256` digests a string, a string must be valid UTF-8, and
`:identity/verify` reads a granted byte span. An ASCII message is the one
byte sequence both can take unchanged, so the bytes that are verified are
exactly the bytes that are hashed.

Every identifying field is inside the signed message. `policy` is one of
them, so downgrading an entry's data policy without re-signing it is
detected. `seq` and `ts` are fixed width, so they cannot collide at a digit
boundary (the collision the Rust `entry_cid` fixed).

## Warrant (v1)

A warrant is an issuer's signed accusation, and it carries its own evidence
in one region of 1336 bytes:

```
[issuer key 32][signature 64][warrant message 332][entry A 454][entry B 454]
```

```
kotoba.warrant/v1
issuer:<64 hex: the same 32-byte key>
accused:<64 hex>
rule:fork
seq:<20 decimal digits, first two 0>
a:<64 hex: sha256 of entry A's message>
b:<64 hex: sha256 of entry B's message>
```

A warrant verifies only when all three of these hold:

- the issuer signed it;
- the two entries are a fork (the `fork-evidence` judgement);
- it names exactly that fork: the accused, the seq, and both hashes in order.

So a warrant cannot accuse on hearsay, and a valid signature cannot be
re-pointed at different evidence. Spreading warrants to neighbours is stage
D; this only judges one.

## Mutual-credit transfer (v1)

A transfer is countersigned by both parties, 462 bytes:

```
[spender key 32][receiver key 32][spender sig 64][receiver sig 64][message 270]
```

```
kotoba.engi.transfer/v1
spender:<64 hex>
receiver:<64 hex>
amount:<20 decimal digits, first eight 0, not all 0>
nonce:<64 hex>
```

Each party appends an entry whose `content` is the transfer id (the sha256
of the message) to its own chain. `replay-balance` takes one region: the
agent's chain of `n` entries, followed by the transfers it references, in
chain order. It verifies the chain first, then folds the transfers:

- the spender loses the amount and the receiver gains it;
- the credit limit is checked at every step, not only at the end.

There is no global ledger and nothing is issued, so balances are net zero
across agents; the qualification checks this on two chains. Two limits
apply:

- A double spend is not visible inside one chain. It shows up as a fork,
  which is what `fork-evidence` and `verify-warrant` are for.
- Completeness is the caller's job: the replay counts only the transfers
  it is given.

## DNA (v1)

A DNA is the rule set a chain lives under. It is named by its content: the
DNA id is the sha256 of its manifest. The manifest is ASCII, one field per
LF-terminated line:

```
kotoba.dna/v1
name:<1..64 printable characters>
version:<1..64 printable characters>
max-content:<1..6 decimal digits>
allow:<schema>          (one or more, strictly ascending)
end
```

Ascending `allow` lines make the manifest canonical, so one rule set has one
id. An unsorted or repeated line is refused, not re-sorted. A chain lives
under a DNA when both of these hold:

- its genesis entry's content is the DNA id (Holochain's genesis records the
  DNA hash the same way);
- every later entry's content is resolved: the caller supplies the document
  whose sha256 the entry names, and that document is
  - printable ASCII,
  - no longer than `max-content`,
  - of a schema the DNA allows. The schema is the document's first line.

`validate-dna` takes one region:

```
[manifest][chain n*454][record for entry 1]...[record for entry n-1]
record = [length: 2 bytes big-endian][document]
```

With every document resolved, no content can sit in the chain as an opaque
hash that the DNA never admitted. A validator holding the documents sees
every transfer the chain names. That is the completeness `replay-balance`
leaves to its caller: a transfer's message is itself a document of schema
`kotoba.engi.transfer/v1`.

## Qualification

```bash
kbb --backend sci qualification/native.cljk [--amu ../amu] \
    [--platform host|linux-podman] [--isa aarch64|x86_64]
```

This compiles the guest for the host's native target, extracts the exports,
builds `amu/tools/kexe_loader.c`, and signs vectors on the host. Signing is
the key holder's job, so the guest only verifies. Every row pins the exact
answer. Two rows pin that the guest traps without the verify or sha256
grant, rather than answering. The trap is SIGTRAP on aarch64 and SIGILL on
x86_64. Guests with any of these checks removed fail exactly the row that
names the check:

- the prev check;
- the warrant's evidence-hash check;
- the double-count guard;
- the genesis DNA check;
- the schema check.

`--platform linux-podman` compiles for `<isa>-linux` and runs inside the
podman machine. The loaders are built static in the `localhost/c3-gcc`
container, as amu's `scripts/test-linux-static-handlers.cljk` does. The run
sets `vm.overcommit_memory=1` for the loader's shared-state mmap and puts
the old value back afterwards.

Measured 2026-09-27, all 70 rows passing on each of these:

| platform | loader |
|---|---|
| macOS aarch64 | host build |
| Linux aarch64 (Fedora CoreOS 6.15) | production build, seccomp filter in force |
| Linux x86_64 | `qemu-x86_64-static`, built `-DKEXE_SANITIZER_TEST`, because qemu-user cannot install a guest-arch seccomp filter |

x86_64 has not been run on real hardware.

Exit codes:

- `0`: every row passed.
- `1`: a row failed.
- `3`: the qualification could not run. This covers a missing toolchain, a
  failed build, and bad arguments. It is never reported as a pass.

Inside the superproject, run it through `scripts/resource-guard.mjs run build
--wait -- …`.

## Not here yet

The following parts of ADR-2609261900 are not done yet:

- Richer DNA rules than schema, size and resolution. For example, a rule
  per schema over the document's fields, which the Rust `RuleSpec` expressed
  over datoms.
- One call that joins `validate-dna` and `replay-balance`. Today a caller
  composes them: first check that every transfer document is resolved, then
  replay exactly those transfers.
- Warrant tally across distinct issuers (K/2), and gossip. These are stage
  D.
- Networking, which is stage B.
- The Linux static ELF target (`<isa>-linux-static`). amu refuses it for
  two measured reasons: a static image must be a program with a
  zero-arity `main` (these are library exports taking granted regions), and
  a static image has no handler for wire 3, `:hash/sha256`. The same
  missing-handler reason is expected for wire 2, `:identity/verify`. Until
  those handlers exist, the kexe loader is the Linux path.
