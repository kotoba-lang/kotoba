# ADR-0068 — The gate ran, and reachability was not authorization

Date: 2026-08-19

## Status

Accepted and executable. The fleet gate registered in ADR-0063 **ran, and
failed**. This is why, and the fix — with the coverage it costs stated in
numbers.

## Registration became execution

ADR-0061 said registration is not execution and ADR-0063 registered the gate
anyway, noting nothing had run yet. It has:

```
2026-08-18T14:44Z batch 0 : [["aiueos" "df2413a" "levi"] ["aiueos" "b821311" "simeon"] …]
2026-08-18T14:51Z fail test-aiueos-df2413a-murakumo-levi exit 1
                  — no test summary in output — refusing to report a pass (93)
2026-08-18T14:51Z fail test-aiueos#pr147-b821311-murakumo-simeon exit 1
                  — no :test-fleet alias in deps.edn (91)
```

**Both refusals are the gate working.** Exit 93 is the floor ADR-2608136000
asks for — *refusing to report a pass* rather than reading an empty run as
clean. Exit 91 is a PR branch whose tip predates the alias, refused rather than
silently skipped.

## Why levi produced no summary

Reproduced on the node:

```
Cloning: https://github.com/kotoba-lang/org-ietf-tcp.git
Error building classpath. Unable to clone …
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

**`kotoba-lang/org-ietf-tcp` is private.** Every other dependency of the alias
is public. A fleet node holds no credentials by invariant, so the classpath
never resolves and no test runs — which is exactly the shape the gate's floor
caught, and could not have explained.

**The egress probe that cleared this alias asked the wrong question.**
ADR-0063 measured `curl https://github.com` → 200 on two nodes and recorded it
as "the dependency resolution a `:jvm-test` gate needs works". Reachability is
not authorization. That is the defect this series keeps finding, here in its own
preparation, and the measurement was mine.

## Decision

**`:test-fleet` names no private dependency**, and does not select the test that
needs one. Metadata exclusion is not enough: the parity namespace requires
`tcp.seq` at load time, so the runner must not scan it —
`-r "^aiueos\.(?!tcp-seq-acceptable-parity-test).*$"`.

`aiueos.fleet-alias-test` holds the line: every git dependency in `:test-fleet`
must be on a named anonymous-fetch list, the selector must exclude the parity
namespace, and `:test` must still carry the dependency — **the fleet alias is
narrower than the suite, not a replacement for it.**

## The cost, in numbers

| | tests | assertions |
|---|---|---|
| `kbb -M:test` | 647 | 9,440 |
| `kbb -M:test-fleet` | 643 | **1,920** |

The parity test is four tests carrying **7,520 assertions** — a matrix over
every input the TCP window-acceptability decision takes, checked against
`org-ietf-tcp`'s reference implementation. **The fleet now covers 20% of this
repository's assertions**, and the missing 80% is one private repository.

Making `kotoba-lang/org-ietf-tcp` public would restore all of it in one change.
That is a repository visibility change, which this workspace's standing
authorization explicitly excludes and which requires the owner. **Named here as
the single highest-leverage item available to the fleet**, and not done.

## Executable evidence

`aiueos.fleet-alias-test`: **4 tests, 7 assertions, 0 failures.**
`-M:test-fleet` **643 / 1,920 / 0**; `-M:test` **647 / 9,440 / 12**;
`-M:tcb-check` valid; lint unchanged.

**Both directions**: putting the private dependency back into the alias fails
`every-fleet-dependency-can-be-fetched-without-credentials` **by name**, with
the reason a node cannot say for itself; removing the namespace selector fails
`the-private-parity-test-is-not-selected`.

## Remaining boundary

- **The gate has not yet been observed green on a node.** The next tick is the
  first chance, and this ADR is written before it — the honest state is "the
  cause was found and the fix is landed", not "the fleet is green".
- **20% coverage is a number, not a verdict.** Which assertions those are
  matters more than how many, and nothing here measures that.
- The `#pr147` failure is untouched: a PR branch predating the alias will keep
  failing until it rebases, which is correct and will read as noise.
