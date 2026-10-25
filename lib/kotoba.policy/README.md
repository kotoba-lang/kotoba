# policy-clj (認可ポリシー)

[![CI](https://github.com/kotoba-lang/policy/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/policy/actions/workflows/ci.yml)

Handle **ABAC/RBAC authorization policy as EDN/Clojure data** in portable Clojure —
every namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the
JVM, ClojureScript, and Clojure-on-WASM hosts (SCI). A policy is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds structural validation,
a pure condition evaluator, and a combining-algorithm decision engine around it.

Sibling of the other reusable `*-clj` kernels in this org
([authenticator-clj](https://github.com/com-junkawasaki/authenticator-clj),
[bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** decision kernel lives in **com-junkawasaki**;
**public-benefit actors** that enforce concrete access policies (e.g. a content moderation
gate in etzhayyim, a ghosthacker resource guard) live in **etzhayyim**; any
**business/private deployment** with domain-specific roles and attributes lives in
**gftdcojp**. policy-clj is the dep — it carries no domain roles, no attribute store,
and no engine bindings (those are host-injected ports). Combined with authenticator-clj
(which verifies *who* the principal is), policy-clj decides *what* they may do.

## The model: Policy as EDN (`policy.model`)

Rules are kept in a vector (order matters for `:first-applicable`); roles are an
id-keyed map for O(1) RBAC lookup. A condition is recursive data — a leaf or combinator:

```clojure
{:policy/id "p1"
 :policy/algorithm :deny-overrides
 :policy/rules [{:policy/id "r-admin" :policy/effect :allow
                 :policy/when {:policy/attr "user.role" :policy/op := :policy/value "admin"}}
                {:policy/id "r-banned" :policy/effect :deny
                 :policy/when {:policy/attr "user.banned" :policy/op := :policy/value true}}]
 :policy/roles {"admin" #{"read" "write" "delete"} "user" #{"read"}}}
```

A threading-friendly builder, plus condition constructors:

```clojure
(require '[policy.model :as m])

(def acl
  (-> (m/policy "acl" {:algorithm :deny-overrides})
      (m/allow "r-staff"
               (m/and-cond (m/or-cond (m/leaf "user.role" := "admin")
                                      (m/leaf "user.role" := "editor"))
                           (m/not-cond (m/leaf "user.banned" := true))))
      (m/deny  "r-ip-block" (m/leaf "req.ip" :in ["192.0.2.1" "192.0.2.2"]))
      (m/role  "admin"  #{"read" "write" "delete"})
      (m/role  "editor" #{"read" "write"})))
```

Supported ops: `:=` `:!=` `:<` `:>` `:<=` `:>=` `:in` (value in collection) `:contains`
(collection contains value). Combinators: `:policy/and`, `:policy/or`, `:policy/not`.

## Validation (`policy.validate`)

`problems` returns a vector of `{:policy/severity :error|:warn :policy/code :policy/id :policy/msg}`;
`valid?` is true iff there are no `:error`s:

```clojure
(require '[policy.validate :as v])
(v/valid? acl)      ;=> true
(v/problems bad)    ;=> [{:policy/severity :error :policy/code :rule/unknown-op …}]
```

Errors: unknown combining algorithm, unknown rule effect, unknown op in a leaf condition.

## Ports (`policy.ports`)

```
IAttribute   resolve  [attr-path request] → value   — look up a dotted path in the request
```

`attr-path` is a dotted string (`"user.role"`, `"req.ip"`). The host maps this to a JWT
claims map, an LDAP attribute, a database row — anything that can return a value.

## Execution (`policy.execute` + `policy.ports`)

A **pure decision engine**. State is plain data — inspectable, testable offline.
The host injects one port (`policy.ports`):

```clojure
(require '[policy.execute :as e])

;; ABAC: decide from request attributes
(e/decide (e/default-ports) acl {:user {:role "admin" :banned false}})
;=> {:policy/decision :allow :policy/by "r-staff"}

;; RBAC: check a role's static permissions
(e/permits? acl "admin" "delete")   ;=> true
(e/permits? acl "editor" "delete")  ;=> false
```

Combining algorithms:
- **`:deny-overrides`** — any applicable deny beats any allow; else allow if any; else
  `:not-applicable`.
- **`:allow-overrides`** — symmetric: any applicable allow beats any deny.
- **`:first-applicable`** — the first rule (in declaration order) whose condition holds wins.

`default-ports` resolves dotted paths against the request map with keyword-then-string
key lookup at each segment (`"user.role"` on `{:user {:role "admin"}}` → `"admin"`).
Replace with a real attribute store or JWT claim resolver for production.

For real work, inject ports that call your identity provider and attribute service; the
decision engine stays pure orchestration. The same pattern is used in bpmn-clj
(`IActivity`/`ICondition`) and dmn-clj (`IExpression`/`IUnary`).

## Test

```
kbb -X:test
```
