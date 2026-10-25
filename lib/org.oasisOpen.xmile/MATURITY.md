# Maturity and conformance

`100%` is reported only against an explicit external denominator.

| Dimension | Denominator | Current result |
|---|---|---|
| Emitted XML schema validity | OASIS XMILE 1.0 official XSD | 100% for the canonical executable document |
| Canonical XML text round-trip | EDN → XML → EDN equality | 100% |
| Unknown standard element preservation | module/group/views/macro extension fixtures | 100% token-tree preservation |
| Full XSD element semantic modeling | All 189 named XSD elements | Not yet 100% |
| Core scalar execution | Supported stock/flow/aux equation subset | Euler/RK4 implemented |
| Full execution | Arrays, conveyors, queues, submodels, all built-ins/integrators | Not yet 100% |
| Host-independent evaluation | `xmile.expr` -- the equation language: sec 3.5.1 math, `^`, `MOD`, relational/logical operators, sec 3.5.4 test inputs, and the tree walk | Ported to `kotoba/xmile_expr_core.kotoba` and held to `xmile.expr` by two parity gates. The tokenizer/parser, `xmile.xml`, `xmile.validate` and `xmile.execute` are NOT ported and are not claimed. |

Run the externally grounded gate:

```bash
kbb -M:conformance
```

The command validates emitted XML against the official OASIS XSD and requires
EDN/XML round-trip equality. CI runs it on JDK 21.

Raw extensions preserve unimplemented standard elements, but they are not
counted as semantic or executable support.

## Host-independent evaluation

The Kotoba port covers `xmile.expr/eval-expr` in full -- the scalar operations
that carry XMILE semantics, and the walk over the expression tree that applies
them -- plus every number in a simulation step. What it does NOT cover is
stated rather than implied: the tokenizer and parser, `xmile.xml`,
`xmile.validate`, and the parts of `xmile.execute` that reason about the model
rather than about numbers (dependency ordering, delay desugaring, the time
loop) are all still `.cljc` and still require a JVM or a JavaScript engine.
**"A model can be simulated without one" is not claimed here and is not true
today.**

There is also a measured ceiling on what can cross the boundary at once:
`adt-node-limit` 64, `adt-depth-limit` 12 and `typed-map-entry-limit` 31 mean a
six-element name list is refused, so the port is called once per quantity and a
stock with six or more inflows cannot have them summed in one call.

| | ported | denominator |
|---|---|---|
| `xmile.expr` operations | yes | sec 3.5.1 math, `^`, `MOD`, relational/logical, sec 3.5.4 |
| `xmile.expr` walk | yes | `:num` `:ref` unary binary `:if` `:call` |
| `xmile.execute` step arithmetic | yes | clamp (3.1.2), inflows−outflows (3.1.1), Euler and RK4 (3.7.1) |
| `xmile.execute` ordering and loop | no | `topo-order`, `desugar-delays`, `constant-names`, the time loop |
| `xmile.expr` tokenizer/parser | no | sec 3.3.1 grammar |
| `xmile.validate` | no | structural checks |
| `xmile.xml` | no | XML text and element trees |

Numeric agreement with the host is exact for selections, IEEE operations and
every equation containing no transcendental -- including whole RK4 trajectories,
step for step; within 1e-12 relative for the transcendentals and `^` (worst
observed 1.276e-13 in the operation gate, 2.538e-16 through the walk,
2.728e-16 through a 40-step RK4 simulation). The port's domain is narrower than
the host's for wide angles, and that is recorded as a gap rather than a feature.

All three gates print their measured errors on every run, and every property
they claim -- laziness, refusal order, environment/constant lookup order, exact
`f64` round-tripping through the environment, the non-negative clamps, and the
floating-point association order of the RK4 weighting -- has been shown to turn
its gate red on its own. One of those checks did not discriminate when first
written (`max(0, x)` and `abs(x)` agree on every value the model happened to
produce); the model was changed until it did.
