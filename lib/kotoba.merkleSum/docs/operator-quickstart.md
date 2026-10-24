# Operator quickstart

You have `merkle-sum` and you need to run a **proof-of-liabilities**
round: publish one commitment to everything you owe, hand each customer
a proof of their own slice, and let anyone recheck it. This page is the
shortest honest path from a clean checkout to that, plus the gates that
tell you the library still works.

Everything below was executed against `84dc14b` before it was written.
Where a command's exit code is the whole point, it was measured in
**both** directions — clean and with the thing it checks deliberately
broken. The one command that does *not* discriminate is called out, not
quietly omitted.

---

## 1. Prove the library works — 3 seconds, no JVM

```sh
kbb --backend sci --classpath src docs/proof-of-liabilities-walkthrough.cljk
```

This is the fastest gate and the one to reach for first. It walks the
whole operator story — publish, prove, verify, reject — and its exit
code is the verdict (`0` all nine checks held, `1` any did not).

```
1. PUBLISH — the exchange commits to its whole liability set
   root hash: 532c7aa9efe91f0d33b73dd10971fea6d168c2b92e8ce0ccdd3248cbfa6267c4
  ok   root sum IS the total owed => 700
...
9 checks, 0 failed
WALKTHROUGH OK
```

That root hash is the same value the test suite pins as its
cross-runtime determinism lock, so a matching line here is also a
third runtime (nbb) agreeing with the JVM and with Closure-compiled
ClojureScript.

Read `docs/proof-of-liabilities-walkthrough.cljk` next to this page —
it is ~90 lines and it *is* the integration guide. The four things it
shows are the four things you have to get right:

| step | what you own | what `merkle-sum` owns |
|---|---|---|
| **publish** | the leaf preimage (`"leaf\|alice\|300"` here) and the hasher | the node preimage, the tree, the root |
| **prove** | picking the customer | the sibling path |
| **verify** | nothing — a third party needs only `(leaf, proof, root)` | the recomputation |
| **reject** | nothing | the sign check that makes the sum meaningful |

### Why step 4 is not decoration

An exchange that owes 500 can build a tree containing a **negative
"ghost" liability** and publish a total of 100. That tree is internally
consistent: root hash and root sum agree with each other, and every
honest customer's inclusion proof still re-derives it. A verifier that
only recomputes hashes accepts it.

The sign check in `verify` is the only thing standing there, and step 4
is written so that removing it flips the result. Measured both ways:

| `verify`'s `(neg? (:sum step))` guard | step 4 says | exit |
|---|---|---|
| present (as shipped) | `verify REFUSES the understated root => false` | `0` |
| removed | `FAIL verify REFUSES the understated root => true` | `1` |

With the guard removed the fraudulent attestation **passes**. That is
the failure this library exists to prevent, and it is why step 4 is
built on a self-consistent shrunk tree rather than on the easier
"claim a negative balance" case — a negative *claimed* balance is
already rejected by the root mismatch, so it would go green either way
and prove nothing about the guard.

---

## 2. The full suites

Two runtimes, one portable `.cljc` suite.

```sh
kbb -M:test            # JVM compat gate — Ran 6 tests, 193 assertions
kbb -M:lint            # clj-kondo, errors fail — errors: 0, warnings: 0
```

Both were checked in the failing direction as well: breaking
`root-sum-is-the-total`'s expected total makes `-M:test` exit `1`, and
an unresolved symbol in `src/` makes `-M:lint` exit `3`.

ClojureScript is the primary gate, and it takes **two steps**:

```sh
kbb -Sdeps '{:paths ["src" "test"]}' -M:cljs \
  -m cljs.main --target node --output-dir target/node-out \
  --output-to target/tests.cjs -c merkle-sum.cljs-runner
echo '{"type":"commonjs"}' > target/node-out/package.json
node target/tests.cjs      # <- this is the process whose exit code counts
```

> **Do not use the one-step `-m merkle-sum.cljs-runner` form as a gate.**
> It runs the tests and prints their result, but `cljs.main` evaluates
> `-main` inside a node REPL environment and the driver a caller waits
> on exits `0` regardless. Measured 2026-09-03 on this repo with one
> assertion broken: the one-step form printed `1 failures` and **exited
> 0**; the two-step form printed the same failure and exited `1`.
> `merkle-sum.cljs-runner`'s docstring records the same result from
> 2026-08-25 in another repo.
>
> Anything that only reads the exit code — a shell `&&`, a script, CI —
> cannot tell a passing run from a failing one through the one-step
> form. The `package.json` line is load-bearing too: these repos declare
> `"type": "module"`, which makes node read Closure's emitted `.js` as
> ESM and die on `require`.

---

## 3. Using it from your own code

```clojure
(require '[merkle-sum.core :as ms])

(def tree  (ms/build-tree hash-hex leaves))      ; leaves: [{:id .. :hash .. :sum ..}]
(def proof (ms/inclusion-proof tree "alice"))    ; nil if that id has no leaf
(ms/verify hash-hex leaf-hash leaf-sum proof (:root tree))
```

Three things to get right, none of which the library can do for you:

1. **You inject the hasher.** `hash-hex : String -> hex String`. The
   library carries no crypto. Both runtimes in the walkthrough use
   SHA-256 (`java.security.MessageDigest` / node `crypto`).
2. **You own the leaf preimage.** `merkle-sum` reads a leaf's `:hash`
   and trusts it. Commit the id *and* the amount together — a preimage
   of just the amount lets a leaf be re-pointed at another account.
3. **`:sum` must be a non-negative integer.** `verify` refuses negative
   leaf and sibling sums; `build-tree` does not, so a tree built from
   unvalidated input can contain a liability no proof will verify
   against. Validate at the boundary where amounts enter.

Determinism, so an independent rebuild lands on the same root: leaves
are sorted by `:id` (pass `:id->str` to shape the key), and an odd node
is carried **up** unchanged rather than duplicated — duplicating it
would double-count its sum.

---

## Note on `.github/workflows/ci.yml`

CI invokes the one-step CLJS form described above, so its "primary
gate" step cannot fail. It is inert in this workspace anyway — CI/CD
here is the murakumo fleet, and GitHub Actions is disabled per repo
(superproject ADR-2607300900) — but do not read a green check there as
evidence the ClojureScript suite passed. Run step 1 or the two-step
form above.
