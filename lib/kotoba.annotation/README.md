# kotoba-lang/annotation

Safety-bounded W3C Web Annotation constructors written in `.kotoba`.

The public representation is Kotoba `:document`, a canonical immutable tagged
tree. The library compiles to restricted JavaScript and typed Wasm ABI v11; it
does not use Clojure or a JVM at runtime. Input maps omit absent optional
properties instead of passing host `nil` values.

`annotation` and `text-body` preserve extension properties with a bounded,
right-biased merge. The W3C `@context` key is produced through the admitted
`keyword-from-string` primitive rather than ambient keyword construction.

## Test

```bash
kbb -M:test
```

The test JVM is a compiler/build host only. Tests execute reference semantics
and instantiate the generated restricted-JavaScript and Wasm artifacts.
