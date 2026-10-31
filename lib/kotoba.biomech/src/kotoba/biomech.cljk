(ns kotoba.biomech
  "Biomechanics simulation domain layer for kotoba-lang.

  筋肉・骨・皮膚・内臓の生体力学的な sim を扱う capability repo.
  専用 repo として存在しなかった（2026-07-19 探索確認）ため、既存の solver
  資産を束ねる統合層として起こした。

  Phase 1 (this repo, this commit):
    - tissue-property domain — kotoba.biomech.tissue (pure .cljc)
    - closed-form bone mechanics — kotoba.biomech.osteo (Euler-Bernoulli beam)
    - lumped mass-spring muscle model — kotoba.biomech.muscle
    純 Clojure, zero-dep, standalone で動く。

  Phase 2 (follow-up commits; :local/root で既存 solver を消費):
    - kotoba-lang/fea             — 骨の FEM (linear-static beam2/tet4)
    - kotoba-lang/kami-vehicle    — soft-body XPBD (筋肉・皮膚の大規模変形)
    - kotoba-lang/kami-engine-cfd — 血流・気流 (Lattice-Boltzmann CFD)

  Phase 3 (backend blocker):
    - kotoba-lang/kami-engine     — 熱・水分 (DEC voxel PDE; 未実装)

  3D rendering は kotoba-lang/kami-engine stack を使う (repo-wide 3D mandate).
  本 repo は biomech の *domain + simulation* を所有し、rendering は持たない。

  No network, no I/O in any .cljc domain namespace (tissue-loader の JVM
  resource 読み出しだけが唯一の I/O で、純 .clj に隔離されている — fea の
  material-loader と同型)。")

(comment
  ;; quick repl smoke (JVM)
  (require '[kotoba.biomech.tissue :as tissue]
           '[kotoba.biomech.tissue-loader :as loader]
           '[kotoba.biomech.osteo :as osteo]
           '[kotoba.biomech.muscle :as muscle])
  (def cortical (tissue/find-tissue (loader/presets) "Cortical-Bone"))
  (tissue/youngs-modulus cortical)         ;=> 1.7e10
  (osteo/cantilever-tip-deflection 100.0 0.20 (tissue/youngs-modulus cortical)
                                   (osteo/second-moment-area-rect 0.01 0.01))
  (muscle/simulate (muscle/make-state 0.15) (muscle/make-params) 1.0 1.0e-3 50))
