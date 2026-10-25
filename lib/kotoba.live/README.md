# kotoba-live

[![CI](https://github.com/kotoba-lang/live/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/live/actions/workflows/ci.yml)

**KAMI live-show / VRM-and-Live2D dance-scene domain, in pure `.cljc`.**

The whole "LiveShow" is EDN: `:dance/{show,avatar,camera,stage,setlist,crowd,
lighting,vj,triggers,live2d,clips,post,audio}` → a deterministic show with a
beat grid + setlist + `DancePose` + crowd + lighting + VJ + a director/trigger
reaction system + a VRM `AvatarBinding` (and/or a Live2D Cubism performer
binding), projected to the render-IR shape `{:globals ... :instances [...]}`
that a native or web renderer already consumes.

This is a Clojure port of the Rust `kami-live` crate (part of
`kotoba-lang/kami-engine`, retired per ADR-2607010930 clj-wgsl migration
Phase 4). It is the **base crate** — beat-grid math, show composition, the
director/trigger reaction system, and the render-IR projection. The
`kami-live-scene` data files (the `:dance/audio` sound bank) were already
ported into `kotoba-lang/kami-scene-contracts`
(`resources/kami/scene/contracts/kami-live/audio.edn`); this repo mirrors
that authority at `resources/kotoba/live/audio.edn`.

## Namespaces

| Namespace | Ported from (Rust) | What it is |
|---|---|---|
| `kotoba.live.beat` | `beat.rs` | Beat grid: BPM → seconds/beat → bar/phrase phase, eighth/beat/bar/phrase crossing events, swing |
| `kotoba.live.setlist` | `setlist.rs` | Track timeline, cue points, open-closed cue dispatch |
| `kotoba.live.performer` | `performer.rs` | `DancePose` + the 11 dance-move pose functions |
| `kotoba.live.crowd` | `crowd.rs` | Fan agents: deterministic placement, mood, per-frame snapshot |
| `kotoba.live.lighting` | `lighting.rs` | Fixture cues, envelopes (hold/pulse/breathe/strobe/ramp), laser sweep |
| `kotoba.live.vj` | `vj.rs` | LED-wall pattern/palette deck, per-phrase advance |
| `kotoba.live.cheer` | `cheer.rs` | Sliding-window cheer aggregate |
| `kotoba.live.stage` | `stage.rs` | Venue geometry presets (club/hall/festival), zones, fixture mounts |
| `kotoba.live.audio` | `audio.rs` | Drum/bass pattern presets, `midi->hz`, sound-recipe shape |
| `kotoba.live.director` | `director.rs` | EDN-declared `:dance/triggers` reaction resolution |
| `kotoba.live.avatar` | `scene.rs` (`AvatarBinding` + friends) | VRM binding intent, expression-weight drives, vocal lip-sync (`VoiceLine`) |
| `kotoba.live.camera` | `scene.rs` (`CameraRig`) | Camera framing + `:shots` choreography (dollied, smoothstepped) |
| `kotoba.live.live2d` | `live2d.rs` | Live2D/Cubism param driver + inline motion keyframe sampling |
| `kotoba.live.show` | `show.rs` | `LiveShow` composition: tick (grid→audio/cues) + snapshot |
| `kotoba.live.render` | `render.rs` | `show->render-ir` projection (`show->render-ir`) |
| `kotoba.live.scene` | `scene.rs` | `:dance/*` EDN loader, `DanceScene`, `frame`, `run-headless` |
| `kotoba.live.lint` | `lint.rs` | `lint-scene` — flags what the tolerant loader silently corrects |
| `kotoba.live.edn-util` | (Rust `kami_scene` tolerant-accessor layer) | `num`/`ident`/`vec3`/`flag`/`root-map` helpers |
| `kotoba.live.mathx` | — | `#?(:clj :cljs)` transcendental-math wrappers (portability) |
| `kotoba.live.vec3` | (`glam::Vec3` usage) | Minimal `[x y z]` vector helpers |
| `kotoba.live` | `lib.rs` | Convenience re-exports |

## Design notes / deviations from the Rust source

- **No custom EDN accessor layer.** The Rust crate hand-rolled a tolerant
  `EdnValue` accessor (`kami_scene::{EdnValue, mget, num, vec3, root_map}`)
  because Rust is statically typed. In Clojure, `clojure.edn/read-string`
  already produces native maps/keywords/vectors/numbers, so
  `kotoba.live.edn-util` is a small *defaulting* layer (missing/mistyped
  keys fall back to a default, matching the original tolerant behaviour) —
  not a parser.
- **Functional, not mutable.** `BeatGrid::tick`/`drain_events`,
  `LiveShow::tick`/`snapshot`, `Crowd::snapshot`, `VJDeck::frame`, and
  `DanceScene::frame` were mutable methods in Rust. Here every stateful
  subsystem is a plain map and its "tick" is a pure function returning
  `[state' result]` (or `[state' events]`) — the functional analogue, and
  the actual `.cljc` idiom for "no I/O" domain logic.
- **Different (but still deterministic) crowd RNG.** `kotoba.live.crowd`
  uses mulberry32, a small dependency-free 32-bit PRNG portable across JVM
  and ClojureScript, instead of the Rust crate's SplitMix64. Same seed →
  same layout on any platform; bit-identical cross-language RNG output
  was never a goal.
- **One classpath resource read, no other I/O.** `kotoba.live.scene`
  bundles the default `:dance/audio :bank` at
  `resources/kotoba/live/audio.edn` (mirrored from the
  `kotoba-lang/kami-scene-contracts` authority, same pattern that repo's
  other mirrors use) and reads it via `clojure.java.io/resource` + `slurp`
  on JVM Clojure only (`#?(:clj ...)`); the ClojureScript build returns an
  empty default bank (a scene's own `:dance/audio :bank` still works). No
  network access anywhere.
- **Action-map keys are plain strings.** `Director`/`Trigger` free-form
  action keys (`:fx`, `:sound`, `:camera`, ...) are stored and looked up by
  their bare string name (`(director/action trigger "fx")`), matching the
  original Rust `Trigger::action(&self, key: &str)` signature.

## Ported (logic)

Beat-grid math (including swing), setlist sequencing + open-closed cue
dispatch, `DancePose` interpolation for all 11 dance moves, crowd placement
+ mood/energy state machine, lighting cue envelopes + laser sweep, VJ
pattern/palette advance, the director/trigger reaction system
(`:dance/triggers`, including `:tag`/`:every` filters), `lint-scene`
validation (every check from `lint.rs`), the render-IR projection shape
(`show->render-ir`: performer/crowd/stage instances, lights, camera,
materials, VRM mesh + expression weights + animation layer), `Live2DBinding`'s
standard-Cubism-param mapping + inline motion keyframe sampling, the full
`:dance/*` EDN scene loader (`DanceScene`/`from-edn`/`from-root`), per-frame
`frame` (tick → director resolve → render-IR → sounds → live2d → particles →
camera-shot → post chain), and `run-headless`.

Hardcoded constants/presets are either Clojure `def`s (stage presets, VJ
palettes, dance-move waveforms) or, for the sound bank, the mirrored EDN
resource — matching how the rest of this monorepo separates data from logic.

## NOT ported (host/adapter responsibilities)

- **VRM mesh skinning / GPU render.** `render/show->render-ir` builds the
  EDN description only (`:meshes`, `:materials`, `:lights`, `:camera`,
  `:instances`); the actual skinned draw call is the native
  (`kami-webgpu-rs`) or web (CLJS) renderer's job, exactly as in the
  original Rust crate.
- **Live2D Cubism runtime.** `kotoba.live.live2d` resolves per-frame
  parameter values and an EDN `:live2d` render-IR entry; the `.moc3` /
  `.model3.json` ArtMesh warp and physics sim is the host Cubism runtime.
- **Audio playback device I/O.** `kotoba.live.audio`/`kotoba.live.scene`
  emit `AudioCue`s and `kami.audio`-style EDN sound recipes
  (`{:wave :freq :to :dur :gain :at}`); a host's Web Audio bridge plays
  them. No samples, no device access, anywhere in this repo.
- **The `kami-dance` CLI binary.** Its process/file-IO wrapper (reading a
  scene file from disk, driving a window, an `--emit-ir`/`--lint-only` CLI)
  is not ported — a host application wraps `kotoba.live.scene` /
  `kotoba.live.lint` the same way.
- **MMD `.vmd` import / MToon shading / spring-bone simulation.** These are
  `kami-skeleton-scene` / `kami-vrm` capabilities the original crate only
  *referenced* (the `:vmd`/`:spring` fields are parsed and carried in
  `AvatarBinding`, unchanged); out of scope for this repo.

## Usage

```clojure
(require '[kotoba.live.scene :as scene])

(def sc (scene/from-edn (slurp "my-show.edn")))
(def sc (update sc :show kotoba.live.show/start))
(let [[sc' frame] (scene/frame sc (/ 1.0 60.0))]
  (:render-ir frame)   ;; => {:globals ... :instances [...]}
  (:actions frame)     ;; => fired :dance/triggers reactions this tick
  (:sounds frame))     ;; => kami.audio EDN sound recipes fired this tick
```

```clojure
(require '[kotoba.live.lint :as lint])
(lint/lint-scene (slurp "my-show.edn"))
;; => [{:severity :warn :path "dance/show.stage" :message "..."}  ...]
```

## Test / lint

```sh
kbb -M:test
kbb -M:lint
```

## License

Apache License 2.0.
