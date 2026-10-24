# kotoba-hir

Checked high-level IR contract for Kotoba.

`kotoba-hir` owns the versioned envelope passed from semantic analysis to KIR
lowering. It validates the closed module/function shape and cross-field
invariants without repeating source-language type inference.

```clojure
(require '[kotoba.hir :as hir])

(hir/validate!
 {:format :kotoba.hir/v2
  :namespace 'example.core
  :schemas {}
  :schema-identities {}
  :entry 'main
  :exports ['main]
  :result :i64
  :effects #{}
  :named-operations #{}
  :language-profile nil
  :functions [{:name 'main :params [] :result :i64
               :effects #{} :body 42}]})
```

Namespace-bearing empty libraries use an empty function/export vector and
no entry/result. They retain the closed-envelope and empty effect-union
checks; this HIR admission does not prove source admission or backend support.

## Boundary

- owned here: HIR versions, canonical keys, checked function envelope,
  entry/export/result consistency, effect aggregation, closure refinement
  annotations, and portable expression-value representation
- owned by `kotoba-sema`/the current compiler frontend: parsing, name
  resolution, desugaring, type/effect checking, capability elaboration, and
  proof that expression operations are semantically valid
- owned by `osaho` (formerly `kotoba-kir`): HIR-to-KIR lowering and canonical semantic IR

## Development

```sh
kbb -M:test
```
