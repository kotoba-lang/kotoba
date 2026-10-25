(ns kotoba.lang.kami-nv-compat.index
  "NVIDIA Omniverse stack public-API drop-in compat facade — portable .cljc
  port of src/index.ts, the grand top-level barrel. R1.0 path reservation
  per ADR-2605261800; closes the top-level-facade sweep of ADR-2607020130
  (13 of 13: dynamics/controllers/actions/assets/warp/policies through
  isaac-sim, e7m-sim, optix, rtx-renderer, kami-rt, omni-usd, kami-usd,
  omni-kit-app, amenominaka, omni-replicator-core, utsushimi, isaaclab-envs,
  e7m-shugyo, omni-nucleus, kotoba-datomic-nucleus, omni-cloud,
  murakumo-render, alpamayo, alpasim, kami-drive, drive-sim, wadachi-sim).

  Almost the entire file is `export * as X from \"./...\"` re-export
  bookkeeping with no CLJC equivalent need — every sub-namespace is already
  ported 1:1; callers require the specific namespace they need directly,
  matching the kami-rt.index barrel precedent (\"most of index.ts is TS
  re-export bookkeeping with no CLJC equivalent — callers require kami-rt.
  bvh / kami-rt.pathtrace / etc. directly instead of going through a
  barrel\").

  The only genuinely new content is the compat-name metadata below (ADR,
  PHASE, ALPAMAYO_COMPAT_MAP, NV_COMPAT_MAP) — referenced by name in several
  already-ported facades' docstrings (rtx-renderer, optix: \"per
  NV_COMPAT_MAP\"). TS wraps the maps in Object.freeze; Clojure maps are
  already immutable, so that boilerplate has no CLJC equivalent either.

  See README.md for trademark notice and sub-phase delivery plan. Wave 44
  of ADR-2607020130 (closes the top-level-facade sweep; only warp/examples.ts,
  explicitly deprioritized, and the final TS-deletion batch remain).")

(def adr "ADR-2605261800")

;; R1 Omniverse stack complete: R1.2 OptiX/RTX · R1.3 Replicator · R1.4 USD +
;; Kit app · R1.5 Isaac Lab · R1.6 DriveSim · R1.7 Omniverse Cloud · R1.9
;; Nucleus (+ the separate Alpamayo AV stack). Engines: kami-rt / kami-rtx /
;; kami-usd / utsushimi / e7m-shugyo / wadachi-sim / amenominaka /
;; murakumo-render / kotoba-datomic-nucleus / michibiki.
(def phase "R1-complete")

(def alpamayo-compat-map
  "Canonical KAMI engine names for the Alpamayo AV stack (parallel to
  nv-compat-map, which covers the Omniverse stack)."
  {"Alpamayo" "michibiki"
   "AlpaSim"  "wadachi-sim"
   "AlpaGym"  "wadachi-gym"})

(def nv-compat-map
  {"Omniverse Kit"   "amenominaka"
   "Nucleus"         "kotoba-datomic-nucleus"
   "Isaac Sim"       "e7m-sim"
   "Isaac Lab"       "e7m-shugyo"
   "OptiX"           "hikari-rt"
   "RTX Renderer"    "kami-rtx"
   "Replicator"      "utsushimi"
   "DriveSim"        "wadachi-sim"
   "Omniverse Cloud" "murakumo-render"})
