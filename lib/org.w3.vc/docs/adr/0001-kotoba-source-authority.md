# ADR 0001: Kotoba source authority for VC documents

Status: accepted

## Decision

`src/vc.kotoba` is the sole production source. Clojure remains only a compiler
and test host. The reference evaluator, restricted JavaScript, and instantiated
typed Wasm must agree on observable constructor, recognition, validation,
resource-bound, and rejection behavior.

Credentials and presentations use bounded canonical documents. The former
variadic `types` and `presentation-types` functions become one-vector APIs,
retaining ordered distinct type construction under the 32-entry limit. The
former open Clojure option maps become canonical document option maps. Every
credential optional field, context override, presentation field, recognizer,
and ordered validation error remains represented.

No networking, DID resolution, signature verification, proof generation, or
persistence is performed here. Those effects require separately admitted
capability providers.
