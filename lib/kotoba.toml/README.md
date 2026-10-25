# kotoba-lang/toml

TOML, from both directions.

| direction | where | language | status |
|---|---|---|---|
| data → TOML (emit) | `src/toml/core.cljk`, facade `src/kotoba/toml.cljk` | `.cljc` | in use |
| TOML → data (read) | `kotoba/toml_scan_core.kotoba` | **Kotoba** | in use — see Consumers |

## Emitting

`toml.core` turns a map into TOML: scalars and arrays become `key = value`,
nested maps become `[table]` sections, and a vector of maps becomes `[[name]]`.

```sh
kbb -M:test
```

## Reading — `kotoba/toml_scan_core.kotoba`

The decision half of a reader, written in Kotoba: every question with a
yes/no or which-one answer over one physical line — what kind of line is this,
where does the key end, is this key well-formed, what type is this scalar, what
does this escape mean.

Assembling the nested table is deliberately NOT here. That is collection work,
and this follows the boundary `kotoba-lang/murakumo`'s `infer_join_core` draws
("partition-work / enrollment map assembly stay cljc"): the decision core moves
to Kotoba, the collection assembly stays with its caller.

Every function is total — `[:result T :string]`, never a throw, per the
language's `:explicit-errors` invariant. **Anything the subset does not
implement is an error, never a guess.** A `1.0` comes back as
`[false "not an integer"]` rather than as `1`; a `\uXXXX` escape is refused
rather than approximated. A parser that silently mis-reads a config it does not
understand is worse than one that refuses it.

### Covered / refused

Covered: comments, blank lines, `[table]` and `[[array of tables]]` headers,
bare `key = value`, basic strings with `\n \t \r \" \\`, integers including `_`
separators and a leading sign, booleans, and the openers for arrays and
multi-line strings (so the caller can join continuation lines before asking
again).

Refused, explicitly: quoted keys, `\uXXXX`, `\b` and `\f` (the Kotoba reader
rejects those escapes in source, so this module cannot produce those bytes at
all — measured 2026-08-11), floats, dates, and anything else.

### Multi-byte text

`string-substring` and `string-code-point-at` both take **byte** offsets and
both **trap** on a non-boundary offset. So every scan advances by a width
derived from the codepoint, and substrings are only cut at offsets a scan has
already proved to be boundaries. Japanese values, emoji and Japanese comments
pass through intact; a non-ASCII *bare key* is refused (it is not legal TOML)
rather than trapping.

This is not hypothetical tidiness: the first draft walked byte by byte and
trapped on the first non-ASCII value it saw.

### Build and check

```sh
kotoba -M compile kotoba/toml_scan_core.kotoba --target js --output /tmp/core.mjs
kbb --backend sci scripts/verify-kotoba-core.cljk /tmp/core.mjs
```

43 cases. Compiling needs the Kotoba compiler (`kotoba-lang/amu`, which needs a
JVM); running the artifact needs only node.

Four of those cases are boundary regressions. Cutting at a FIXED offset — a
prefix test, a suffix test, a closing-bracket test — reads as cheap and is a
trap the moment the value holds multi-byte text; all three shapes were present
in the first version and all three were found by running this core over a real
config file rather than over its own examples.

The checker is known to fail when it should: making `integer-value` return the
truncation of `1.0` instead of an error turns two cases red.

### Consumers

`network-awai/net-kotobase` reads its `deps.toml` through this core
(`scripts/check-deps-toml.cljs`), replacing an embedded python3 block that
imported `tomllib` — stdlib only from Python 3.11, while four of the five
murakumo CI nodes run 3.9.6, so that check answered differently depending on
which node it landed on.

Two things a caller has to know:

- **Instantiate per value.** Fuel is charged per function entry and never
  replenished within an instance, so an instance is a budget, not a session.
- **Give node a bigger stack** (`node --stack-size=8000 …`). The core scans one
  codepoint per JS frame — the Kotoba→JS emitter does not do TCO (compiler
  ADR 0173 lists it as a follow-up) — so scan depth is bounded by the host
  stack, and a 2,935-character line overflows nbb's default.

### Fuel

A Kotoba module carries **512 function-entry charges for the whole life of an
instance and never replenishes them**. That is the runtime's design, not a
configuration: `kotoba-lang/compiler`'s `backend/cljs.clj` states it as
"permanently exhausted after 512 total function calls across its whole lifetime
— not 512 per top-level call", and WASM uses the same module-global counter.

Measured 2026-08-11: one instance sustained **seven** `line-kind` calls on an
8-byte line. A single 400-character line exhausts the budget inside one call,
because a scan charges per codepoint.

That bound is now the caller's to declare: `kotoba -M compile … --policy` with
`{:budgets {:fuel n}}` sizes the artifact's budget, and the default is still
512 (kotoba-lang/compiler + kotoba-script, 2026-08-11). The vendored artifact in
net-kotobase is built at 200,000.

Raising it does not widen what the module may DO — it requests no capabilities,
so it can observe nothing at any budget, and memory stays bounded by the
separate node/byte limits. It exposes the NEXT bound instead: the host stack,
which is why callers pass `--stack-size`.
