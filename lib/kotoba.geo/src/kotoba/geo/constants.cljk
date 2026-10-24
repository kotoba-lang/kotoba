(ns kotoba.geo.constants
  "Geospatial constants used across `kotoba.geo.*`.

  Authority mirror: `resources/kotoba/geo/constants.edn`. This namespace
  embeds the same values as plain Clojure data (rather than reading the EDN
  resource at load time) so the numbers are usable from ClojureScript/SCI
  contexts without an `io/resource` + slurp round-trip. A JVM-only test
  (`kotoba.geo.constants-test`) asserts this map matches the EDN resource
  byte-for-byte, the same authority-vs-mirror pattern as
  `kotoba-lang/kami-scene-contracts`.

  Ported from kami-engine/kami-geo (Rust, deleted from the working tree
  pre-commit; recovered from git history) — see
  `90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md`.")

(def constants
  {:tile-size-px 256.0
   :lat-clamp-deg 85.05112878
   :ground-resolution-zoom0 156543.03392
   :globe-default-terrain-scale-ratio 0.028
   :max-cached-tiles 512
   :dem-height-clamp-px 4096.0
   :relief {:continent {:octaves 4 :lacunarity 2.0 :gain 0.52}
            :shelf {:octaves 3 :lacunarity 2.1 :gain 0.5}
            :ridges {:octaves 5 :lacunarity 2.05 :gain 0.56}
            :hills {:octaves 4 :lacunarity 2.0 :gain 0.5}
            :ocean {:octaves 3 :lacunarity 2.2 :gain 0.45}}})

(def tile-size-px (:tile-size-px constants))
(def lat-clamp-deg (:lat-clamp-deg constants))
(def ground-resolution-zoom0 (:ground-resolution-zoom0 constants))
(def globe-default-terrain-scale-ratio (:globe-default-terrain-scale-ratio constants))
(def max-cached-tiles (:max-cached-tiles constants))
(def dem-height-clamp-px (:dem-height-clamp-px constants))
