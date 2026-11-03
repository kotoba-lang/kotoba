# kotoba CAD

Open-source CAD/CAM workbench as EDN geometry data + portable CLJC model.

The published workbench is now **Kami Scene Studio**: a Twinmotion-inspired,
browser-native scene-authoring UI for the CAD/Rhino side of the stack. It is
not a proprietary-product clone. It makes the portable scene model visible
and editable in the browser, then exports EDN for a `kami-engine` adapter to
render or execute.

This repository follows the kotoba industrial-app pattern:

- `resources/cad/domain.edn` is the data registry.
- `src/kotoba/cad/core.cljk` is the pure portable domain engine.
- `src/kotoba/cad/runner.cljk` is a conservative host dry-run runner.
- `docs/index.html` is the GitHub Pages workbench.
- `docs/scene-studio.md` records the UI contract and delivery boundary.

Pages: https://kotoba-lang.github.io/cad/

## Kami Scene Studio

The page provides the high-frequency authoring loop that makes a CAD scene
pleasant to review without claiming to replace a native CAD kernel:

- scene graph and selection;
- perspective / top / walk camera modes;
- time-of-day and weather art direction;
- click-to-place environment, lighting, furniture, and geometry assets;
- presentation mode; and
- `scene.edn` export of only portable authoring state.

The view is an intentionally dependency-light SVG scene preview. It remains
useful on GitHub Pages and does not pretend that browser UI owns the native
renderer. `kami-engine` adapters consume the exported scene contract for a
WebGPU/WASM or native render path.

## Scope

This is an OSS workbench skeleton for 産業 CAD/CAM. It does not claim proprietary compatibility with commercial systems. It focuses on open artifact registries, policy-gated runners, coverage/maturity scoring, and EDN handoff.

## Verify

```sh
kbb -M -e '(load-file "src/kotoba/cad/core.cljk") (println :ok)'
python3 -m http.server 8765 --directory docs
```

## Test

```sh
kbb -M:test
```

`test/kotoba/cad/core_test.cljk` and `test/kotoba/cad/runner_test.cljk` cover
artifact classification, coverage/maturity scoring, the runner-plan
policy-gate builder, and the dry-run runner (14 tests / 49 assertions, 0
failures).

**Fixed 2026-07-07**: `score`/`coverage-assessment` used to throw
`IllegalArgumentException` on the JVM for realistic inputs — `Math/round`
was fed exact `Ratio`/`Long` values from plain integer division rather than
doubles, which it has no overload for. This was JVM-only (the
ClojureScript/browser build has no separate Ratio/Long numeric types, so it
was never affected). Fixed by coercing to `double` before rounding.
