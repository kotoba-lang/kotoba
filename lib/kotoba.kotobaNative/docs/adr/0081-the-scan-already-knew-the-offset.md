# 0081 — the scan already knew the offset

Status: accepted
Date: 2026-09-09
Base: `origin/main` `7cbed51`

## Context

`string-index-of` had no native lowering. From source it failed as

```
{:error :aggregate-abi, :message "aggregate ABI rejected: call-abi-not-admitted"}
```

— `reject-unextracted-call!`, because an unlowered head is call-shaped and
neither backend had a case for it. That is one gate earlier than the two ADR
0002 had to open for `string-contains?` and `string-replace-all`, and it is
worth naming: the operation never reached `kotoba.kir/non-string-typed-ops`
or `kotoba.verifier/string-operations` at all, so neither of those tables
could have been tested for it.

The cost of the gap is not the operation. It is line splitting. Without an
offset a guest cannot cut a string at a separator, so `kbb.browse` — which
walks its `"NAME\tD"` listing with `string-index-of` — could not compile for
native even though `kexe_loader.c` has hosted its wire-34 provider all along
(`kotoba-lang/kotoba` `bin/kbb_shim.cljs` records exactly this, measured
2026-09-07). Every line-oriented program is in the same position.

## Decision

Lower it as `lower-contains` already does, stopped one step earlier.

`kotoba$string-find` — the helper ADR 0002 introduced — **answers the first
matching haystack offset, or -1**. That is `string-index-of`'s entire
contract. `lower-contains` throws the offset away down to 0/1; `lower-index-of`
hands it back:

```clojure
(let [h haystack n needle]
  (do (string-code-point-at n 0)          ; traps iff the needle is empty
      (kotoba$string-find h n 0 (kotoba$string-span h n 0 0))))
```

So the operation costs no new helper, no new context callback, no new value
representation and no ABI bump. A program that searches both ways emits **one**
copy of the scan: `augment-functions` is keyed on the helper names, and the two
lowerings ask for the same ones.

The empty needle is refused by the same leading `string-code-point-at`, and
that is load-bearing here in a way it is not for the predicate: an empty needle
occurs at offset 0 in every string, so a lowering that answered would return a
plausible 0 that no caller could tell from a real match at the start.

## Measurement

`string_search_test.cljc` runs `string-index-of` over `contains-rows` plus the
rows where the OFFSET is the only thing in question — two occurrences (the
answer is the first), multi-byte haystacks where the byte offset and the code
point index differ, and a real match at offset 0. Each row is run twice through
`kotoba.kir/execute`, once as the operation and once as the rewrite; the
expected value is never written down.

That is how this change found a defect in the oracle rather than in itself.
The row `"𝄞ab" / "ab"` failed as `(not (= 7 4))`: the reference interpreter's
`utf8-index-of!` charged a surrogate pair 4 bytes at the high surrogate and 3
more at the low one. `kotoba-script`'s JS emitter, this lowering and CPython
all answer 4. Fixed in osaho `jv/utf8-index-of-surrogate` (its ADR 0271), and
the osaho pin in `deps.edn` is advanced to carry both the evaluator and that
fix — an oracle that refuses the operation would have made every row above
compare two refusals and pass while proving nothing.

## Consequences

- Both ISAs consume the identical rewrite, so they cannot drift in search
  semantics; per-ISA emission equality is asserted for every row.
- `kotoba.verifier/string-operations` gains `string-index-of 2` in the same
  wave (kotoba-verifier `jv/verifier-string-index-of`). Opening one gate and
  not the other unlocks nothing — ADR 0002 measured that as exactly zero.
- Machine-code EXECUTION is still not proved in this repository, which has no
  loader; it is proved through `amu` with this repo as a `:local/root`, as
  ADR 0002 did.
