# kotoba-lang/yaml

`kotoba.yaml` — YAML emission for EDN, with local tags.

```clojure
(yaml/yaml {:roles {:default "raw"}})            ;=> "roles:\n  default: raw"
(yaml/ytag "ColorSpace" {:name "ACEScg"})        ;=> !<ColorSpace> when emitted
```

The block subset that configuration files are written in: nested mappings,
block sequences, scalars, and **local tags** (`!<ColorSpace>`), which OCIO
uses and most emitters do not offer. Anchors, aliases, flow style,
multi-document streams and folded scalars are not supported, and `yaml`
throws on a value it cannot write rather than emitting one that parses to a
different value.

Strings that would parse back as something else (`"2"`, `"true"`, `"null"`,
`"yes: no"`, `""`) are quoted. That is the whole reason to have an emitter
rather than string concatenation.

Tests parse the output back with clj-yaml — a parser this library shares no
code with. An emitter checked only against its own expected strings agrees
with itself, not with YAML.

## Test

```sh
kbb -M:test
```
