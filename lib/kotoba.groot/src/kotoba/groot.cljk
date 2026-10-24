(ns kotoba.groot
  "kami-groot -> kotoba.groot — clean-room NVIDIA Isaac GR00T N1.x
  foundation-policy compat surface, ported from the Rust `kami-groot` crate
  (`kotoba-lang/kami-engine`) into pure Clojure (`.cljc`) per
  ADR-2607010000.

  Mirrors the *public, documented* GR00T Vision-Language-Action surface
  (model load -> obs->action inference, embodiment/modality config,
  action-chunking, teleop/imitation episode format) by name and shape
  only. No NVIDIA library, header, binary, or model weight is linked,
  vendored, or referenced (ADR-2605261800 section 2(b) N1..N9 NEVER). The
  seat is embodiment-head-pluggable and the shipped default backend is
  KAMI-native (a small affine policy generalized to the VLA I/O shape), so
  everything here builds, tests, and runs with zero NVIDIA assets and zero
  network/IO.

  Subs:
    kotoba.groot.types      - Frame / Observation / Action data + accessors
    kotoba.groot.modality   - ModalityConfig / EmbodimentConfig
    kotoba.groot.native     - the KAMI-native affine backend (LinearPolicy,
                               rescale-to-limits)
    kotoba.groot.embodiment - the embodiment-head seat (native-head +
                               swap point for out-of-tree backends)
    kotoba.groot.policy     - gr00t-policy lifecycle (from-pretrained /
                               native / reset / get-action / checkpoint)
    kotoba.groot.episode    - LeRobot-shaped teleop/imitation episode
                               record format (plain EDN codec)

  See README.md for the ported / unported surface table.")

(def adr "ADR-0037")
(def phase "R1.0-native-seat")
(def kami-name "e7m-groot")
(def nv-compat-target "gr00t.model.policy.Gr00tPolicy (Isaac GR00T N1.x)")
