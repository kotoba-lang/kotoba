(ns shugyo.scene-cfg
  "Isaac Lab-compat scene config — port of the original crate's `scene_cfg.rs`.

  Substitution note (scene.yaml -> EDN): the original loaded a YAML text file
  (`load_scene_yaml`) via `serde_yaml`. This project has no zero-dependency
  YAML parser available (per convention already established across ~15 other
  `kami-*-scene` restorations in kotoba-lang), so this port accepts EDN
  instead — semantically equivalent structured data, produced by whatever
  host loads the file (a build step, a resource loader, etc.). `load-scene-edn`
  is a light validator/normalizer over already-parsed EDN data, not a text
  parser; the original `SceneCfg`/nested-struct *shape* is preserved exactly,
  field-for-field, just kebab-cased.

  The struct nesting mirrors `scene_cfg.rs`:
    scene            -> {:num-envs :env-spacing :gravity :dt :decimation}
    robot            -> {:urdf :base-link :spawn {:pos :rot} :actuators}
    observation      -> {:joint-pos :joint-vel}
    action           -> {:joint-efforts}
    reward           -> {:alive :terminating :pole-pos-penalty :cart-vel-penalty :pole-vel-penalty}
    termination      -> {:time-out {:max-episode-length-s}
                          :pole-out-of-bounds {:asset :bounds}
                          :cart-out-of-bounds {:asset :bounds}}
    quality-gate     -> {:reward-curve-tolerance-pct :reference-baseline
                          :reference-basis :reference-seed} (optional)")

;; ---------------------------------------------------------------------------
;; Embedded EDN fixture — Cartpole scene, numerically consistent with
;; `shugyo.cartpole`'s constants and the two `scene_cfg.rs` tests below.
;; (An embedded Clojure map def, not a resource file, since the original crate
;; loaded it via `include_str!` and there is no fixture-file convention here.)
;; ---------------------------------------------------------------------------

(def cartpole-scene-edn
  "Reconstruction of `fixtures/cartpole/scene.yaml` as EDN, matching the two
  original `scene_cfg.rs` tests' assertions (num-envs 1024, dt 1/60,
  decimation 2, gravity [0 0 -9.81], action joint-efforts
  [\"slider_to_cart\"], reward alive 1.0 / terminating -2.0, quality-gate
  present) and the classic CartPole-v1 termination bounds also used by
  `kotoba-lang/cartpole-wasm` and `shugyo.cartpole` (pole ±0.2094 rad = 12°,
  cart ±2.4 m)."
  {:adr "ADR-2605261800"
   :phase "R1.1-cartpole-poc"
   :nv-compat-target "isaaclab.envs.ManagerBasedRLEnv"
   :scene {:num-envs 1024
           :env-spacing 2.0
           :gravity [0.0 0.0 -9.81]
           :dt (/ 1.0 60.0)
           :decimation 2}
   :robot {:urdf "fixtures/cartpole/cartpole.urdf"
           :base-link "cart"
           :spawn {:pos [0.0 0.0 0.0] :rot [1.0 0.0 0.0 0.0]}
           :actuators {}}
   :observation {:joint-pos ["slider_to_cart"] :joint-vel ["slider_to_cart"]}
   :action {:joint-efforts ["slider_to_cart"]}
   :reward {:alive 1.0
            :terminating -2.0
            :pole-pos-penalty -0.01
            :cart-vel-penalty -0.001
            :pole-vel-penalty -0.001}
   :termination {:time-out {:max-episode-length-s 20.0}
                 :pole-out-of-bounds {:asset "pole_link" :bounds [-0.20943951 0.20943951]}
                 :cart-out-of-bounds {:asset "cart" :bounds [-2.4 2.4]}}
   :quality-gate {:reward-curve-tolerance-pct 5.0
                  :reference-baseline "isaaclab-cartpole-v1"
                  :reference-basis "mean-episode-return"
                  :reference-seed [0 1 2]}})

;; ---------------------------------------------------------------------------
;; Loader / validator
;; ---------------------------------------------------------------------------

(defn load-scene-edn
  "Validate + normalize an already-parsed EDN scene map (as produced by
  whatever host loads `scene.edn`), returning it unchanged if the required
  keys are present. See namespace docstring for the substitution rationale
  (original: `load_scene_yaml(yaml_text: &str)`)."
  [scene-edn]
  (when-not (and (map? scene-edn)
                 (map? (:scene scene-edn))
                 (map? (:robot scene-edn))
                 (map? (:observation scene-edn))
                 (map? (:action scene-edn))
                 (map? (:reward scene-edn))
                 (map? (:termination scene-edn)))
    (throw (ex-info "scene EDN missing required sections" {:scene-edn scene-edn})))
  scene-edn)
