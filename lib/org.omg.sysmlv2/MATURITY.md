# Maturity and conformance

`100%` is reported only against an explicit external denominator.

| Dimension | Denominator | Current result |
|---|---|---|
| Official example acceptance | OMG `ptc/25-04-31.sysml` | 100% |
| Official example token-AST round-trip | parse → emit → parse equality | 100% |
| Official example semantic element modeling | Elements not represented as `:opaque-syntax` | 420 / 623 (67.4%) |
| Full normative grammar semantic coverage | SysML.xtext + inherited KerML expression grammar | Not yet 100% |
| Behavior execution | Normative behavioral semantics | Not implemented |
| Constraint/requirement reasoning | Normative semantic rules | Not implemented |

Run the externally grounded gate:

```bash
kbb -M:conformance
```

The command downloads OMG's published informative Simple Vehicle Model,
requires complete parse acceptance and parse/emit/parse equality, and reports
the semantic/opaque split. CI runs it on JDK 21.

An opaque element is not discarded text: it is an ordered token AST with
scope ownership that round-trips. It is nevertheless counted as semantically
unimplemented until it has a typed `sysml.model` representation and validation
rules.
