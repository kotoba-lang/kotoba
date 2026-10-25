# ADR 0079: a budget that is discarded, and a budget that cannot be raised

Status: accepted. Date: 2026-09-03.

## Context

ADR 0078 widened the object replenish because a 32-bit immediate was capping
every per-call budget at 2,147,483,647. While that was landing, the LOADER
stream reported the other half of the same class from the far end of the
toolchain: **`--fuel` is validated and then discarded on the UEFI image route.**

Their evidence: the emitted artifact's sha256 is byte-identical for
`--fuel 512` and `--fuel 1048576` — a 2048× difference that changes nothing —
while `--fuel 250000000` *is* refused, so the flag is parsed and reaches the
verifier. It simply never reaches the image. The cost is concrete:
`sha256-region` costs 1,772 fuel per 64-byte block, so **one SHA-256 block does
not fit in 512**, and the loader's `integrity` module had never returned. They
bisected it in-guest over four boots before the cause was known — scratch write
and read-back, a 64-byte `kernel-subregion` of a `bytes-literal`,
`store32`/`load32` and `sha-init` all pass; only `sha-block` fails.

That defect is in amu's PE32+ packager (amu ADR 0332). This ADR is about what
measuring for it here turned up.

## Decision

**Every image route reads the sealed budget. `package-user` did not, and now
does.**

Rather than read the route that was reported, all four packaging routes were
compiled at three budgets through `bin/amu` and the bytes compared:

| route | 512 | 1,048,576 | 4,300,000,000 |
|---|---|---|---|
| `x86_64-aiueos-kernel-v1` image | `4a6d097d…` | `c22a27db…` | `b728faeb…` |
| `aarch64-aiueos-kernel-v1` image | `5171f353…` | `3d2fa2cd…` | `6416440b…` |
| **`x86_64-aiueos-user-v1` image** | **`d958af72…`** | **`d958af72…`** | **`d958af72…`** |
| `x86_64-aiueos-uefi-v1` image (amu) | `fc742834…` | `fc742834…` | `fc742834…` |
| `x86_64-aiueos-kernel-v1` object | `80d7ee1f…` | `80d7ee1f…` | — |

Two routes, not one. Nobody had reported the user route because nothing has
shipped a ring-3 image that needs more than 512 — which is the shape of the
class rather than an excuse: a budget the caller sets and the packager discards
is wrong whether or not a program has yet outgrown the default.

**The object route's `(le 512 8)` stays, and is not the same line.** An
object's wrapper replenishes unconditionally on every call, so the word in
`.data` is overwritten before the entry is reached and its value is
unobservable. What bounds an object is the per-call tier from the table.

That distinction is asserted rather than left to a comment:
`the-object-route-is-insensitive-and-that-is-correct` pins the two digests as
EQUAL. Omitting the route would let this suite read as "every packager is
fuel-sensitive", which is false; listing it with its reason means a future edit
that makes the object route sensitive has to come here and say why.

## The test is differential, not positional

Reading the fuel word at a fixed file offset would need a different offset per
route and would go stale the first time a context or a section moved. *Two
budgets must not produce the same bytes* needs no offset at all — and it is
exactly the observation that found the defect.

`every-image-route-carries-the-declared-budget` compiles each of the three ELF
image routes at four budgets (512, 2^20, 2^31, the ceiling) and requires four
distinct digests. With the constant restored it reports

```
x86-64 user image must produce a different image for every budget;
got 1 distinct for 4 budgets
```

## `artifact-fuel` checks agreement, not just range

`:limits :fuel` and `:fuel-abi :initial` are two statements of one number, and
the verifier re-derives one from the other. A packager that read only one of
them could ship an image whose running budget contradicts its own receipt.
`an-image-with-a-contradictory-fuel-seal-is-refused` covers both ELF image
routes; amu's ADR 0333 covers the PE32+ one.

## Consequences

- A ring-3 aiueos image can now be given a budget. Nothing in the tree needs
  one yet; the point is that asking for one now works.
- The JVM twin and the portable twin were edited identically, as ADR-0036
  requires. Full suite after: 373 tests / 5106 assertions on the JVM, 9 / 15
  on nbb, 0 failures.
