# kotoba-lang/ocio

OpenColorIO config builders and YAML emitter.

Namespaces:

- `ocio.core` — config builders and the .ocio YAML emitter
- `kotoba.ocio` — the same, under the kotoba namespace
- `ocio.transform` — **the colour arithmetic**: primaries, chromatic
  adaptation, transfer functions, and conversion between spaces

`ocio.core` writes a config that NAMES colorspaces and the transforms between
them. `ocio.transform` performs them, so a pipeline cannot declare `ACEScg`
and hand a downstream tool sRGB values with an ACES label on them.

```clojure
(t/convert :srgb :acescg [1.0 1.0 1.0])       ;=> [1.0 1.0 1.0]  (D65 -> D60 adapted)
(t/transform-matrix :acescg :aces2065-1)      ; the AP1 -> AP0 3x3
(o/xf "MatrixTransform" {:matrix (t/matrix-transform :acescg :aces2065-1)})
```

Every matrix is derived from published chromaticities, not transcribed: a
transcribed matrix is a number that no longer knows where it came from. The
derived sRGB and ACEScg matrices reproduce the published ones to every digit
those standards print.

## Test

```sh
kbb -M:test
```
