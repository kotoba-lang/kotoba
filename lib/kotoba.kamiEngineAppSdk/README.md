> **2026-07-10 (ADR-2607102200 addendum 2):** `kami-engine-hud` (`kotoba.ui`
> hiccup HUD) is merged into this package. Depend on `kami-engine-app-sdk` only;
> `kami-engine-hud` is archived. Namespace `kotoba.ui` is unchanged.

# kotoba-lang/kami-engine-app-sdk

Zero-dep portable `.cljc` — ported from kami-engine's **live**
`kami-ui-sdk/*.js` files (still present today in
`kotoba-lang/kami-engine`, never deleted) as part of the
**clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

Renamed from `kotoba-lang/kami-ui-sdk` (see
`90-docs/adr/2607051200-kotoba-lang-ui-family-rename.md` in
`com-junkawasaki/root`): the six SDKs below cover UI, animation, particle
effects, procedural audio synthesis, and WebRTC — not UI alone — so
`kami-engine-app-sdk` names the actual scope (a shared SDK for kami-engine
consumer apps) and avoids collision with the unrelated `kotoba-ui`/`appkit`/
`uikit` app design-system family. Internal namespaces (`kami-ui-sdk.*`,
`src/kami_ui_sdk/`) are unchanged by this rename.

Unlike most of this migration (which restores *deleted* Rust crates),
this is a **JS -> CLJC port of live source** — six zero-dependency
browser SDKs for kami-engine WebGPU applications: DOM-overlay UI
components, animation primitives, DOM particle effects, procedural UI
sound synthesis, a car-engine audio synthesizer, and a WebRTC bridge.

Each source file's *pure, portable* logic (data transforms, easing/
spring/envelope math, state derivation, parametric animation curves)
was ported to idiomatic CLJC; DOM manipulation, Web Audio graph
construction, and WebRTC/`getUserMedia` plumbing have no CLJC
equivalent and were excluded — documented per-namespace below.

**Deliberate, scoped exception (`kami-ui-sdk.widgets`, ADR-2607031200
Phase 4):** `Slider`/`ColorSwatch`/`Carousel` — three new picker
components kami-engine's live JS SDK gained for the VRM character-
creator app — were ported with their DOM construction *included*,
behind `#?(:cljs ... :clj (throw (ex-info ...)))` guards (the same
shape `kotoba-lang/kami-app-character-creator`'s
`character-creator.persistence` already uses for `localStorage`/file
download). The "exclude DOM" call above was right for a 1:1
restoration of many small, DOM-heavy components with no cross-platform
reader; it does not hold for widgets that are browser-only *by
nature* — keeping them JS-only would only buy a second implementation
to keep in sync with this repo's own spring/easing math
(`kami-ui-sdk.motion`), not any cross-platform benefit. See
`src/kami_ui_sdk/widgets.cljk`'s namespace docstring for the full
rationale, and `dev/widgets_demo.{cljs,html}` for a real, browser-
verified usage example (compile with `kbb -M:cljs -m cljs.main
--optimizations simple --output-dir dev/out --output-to dev/out/main.js
-c widgets-demo`, then open `dev/widgets_demo.html`).

## Modules

| Namespace | Ported from | What's portable |
|---|---|---|
| `src/kami_ui_sdk/ui.cljk` | `kami-ui.js` | Theme data, position->style mapping, `LabelOverlay`'s camera/viewport projection + LOD font-size + culling math, `Button` style derivation, `Toast` color/sound lookups |
| `src/kami_ui_sdk/motion.cljk` | `kami-motion.js` | All 9 easing functions, tween value-at-t, spring-physics integration step, transform-string building, preset animation prop builders, shake/pulse per-frame math, stagger delay schedule |
| `src/kami_ui_sdk/effect.cljk` | `kami-effect.js` | Per-particle trajectory math for confetti/sparkle/ripple/floatText/flash/trail (position/scale/opacity as pure functions of normalized time) |
| `src/kami_ui_sdk/sound.cljk` | `kami-sound.js` | All 15 sound presets as declarative note data, gain-envelope math, frequency-sweep math |
| `src/kami_ui_sdk/engine_audio.cljk` | `kami-engine-audio.js` | HUD -> synthesis-parameter formulas (fundamental frequency, harmonic gains, lowpass cutoff, engine loudness, induction/tire noise params), impact envelope math |
| `src/kami_ui_sdk/rtc.cljk` | `kami-rtc.js` | ICE server config data, ~30fps spatial-loop throttle predicate, `rtc_spatialize()` result -> Web Audio `PannerNode` param mapping |
| `src/kami_ui_sdk/widgets.cljk` | `kami-ui.js`'s `Slider`/`ColorSwatch`/`Carousel` | Full DOM implementation (deliberate exception, see above) — the only namespace in this repo that isn't "pure logic only" |

Most of the original JS is DOM/browser-API glue (`document.createElement`,
`addEventListener`, `AudioContext`/`OscillatorNode`/`PannerNode`
construction, `RTCPeerConnection`/`getUserMedia`) with no CLJC
equivalent; each namespace's docstring lists exactly what was excluded
and why.

## Relationship to `kotoba-lang/rtc` and `kotoba-lang/audio`

Two of the six source files substantially overlap in *domain* (not
code) with sibling restorations already done in this migration:

- **`kami-rtc.js` vs `kotoba-lang/rtc`** — `kotoba-lang/rtc` already
  restored the WebRTC domain logic from the Rust `kami-rtc` crate:
  room/peer/signaling state machines and, critically, `rtc.spatial`'s
  pan/volume calculation (equal-power pan + inverse-distance rolloff).
  `kami-rtc.js` is JS-side glue that *calls into* that same logic (via
  `wasm.rtc_spatialize()`, i.e. the WASM build of the now-CLJC
  `kotoba-lang/rtc`) and applies the results to `RTCPeerConnection`/
  `PannerNode` objects. Once the WASM calls and WebRTC/DOM plumbing are
  excluded, almost nothing independent is left — `kami-ui-sdk.rtc`
  ports only the ICE config data, the spatial-loop's ~30fps throttle
  check, and the small unit-conversion step from `rtc.spatial`'s
  `[left-vol right-vol pan]` output to `PannerNode` gain/`positionX`.
  The spatial math itself is **not** re-implemented here; it lives in
  `kotoba-lang/rtc`'s `rtc.spatial`.

- **`kami-sound.js` / `kami-engine-audio.js` vs `kotoba-lang/audio`** —
  `kotoba-lang/audio` is a 3D *positional audio mixer* (source/
  listener/rolloff, binaural ITD/ILD, WAV encoding) restored from the
  Rust `kami-audio` crate. `kami-sound.js` and `kami-engine-audio.js`
  are a different domain entirely: procedural *UI-sound-effect* and
  *car-engine* synthesis (oscillator envelopes, frequency sweeps, RPM-
  driven parameter formulas) — no 3D positioning or mixing involved.
  There is no shared math to reuse; both restorations are independent
  and this note exists only to make the domain boundary explicit.

`kami-ui.js`, `kami-motion.js`, and `kami-effect.js` are genuinely new
UI/animation/visual-effect domain logic with no existing CLJC
counterpart in this migration and were ported in full (the portable
subset of each).

## Tests

50 tests / 195 assertions, 0 failures, 0 errors, covering every ported
public function across all six pure-logic namespaces plus
`kami-ui-sdk.widgets`'s `:clj`-side throw behavior. `kami-ui-sdk.widgets`'s
actual DOM behavior is verified separately in a real browser (headless
Chrome `--dump-dom`/`--screenshot` — 12/12 assertions passed against
`dev/widgets_demo.html`, since `clojure.test` runs on the JVM and can't
exercise ClojureScript-compiled DOM code).

## Develop

```bash
kbb -M:test
```

### `kami-ui-sdk.widgets` (ClojureScript + browser)

```bash
kbb -M:cljs -m cljs.main --optimizations simple \
  --output-dir dev/out --output-to dev/out/main.js -c widgets-demo
open dev/widgets_demo.html   # or serve dev/ and open in a browser
```
