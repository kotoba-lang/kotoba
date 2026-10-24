(ns terrain.biome
  "BiomePreset: bundled terrain + splatmap + material color configurations.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/biome.rs (deleted in
  PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Each preset defines a
  cohesive environmental look: heightmap FBM params (frequency, octaves,
  max-height), splatmap thresholds (sand/snow lines + rock slope), and
  material base + tip colors (for fragment shaders). Rust's `BiomePreset` enum
  becomes a plain keyword; use `biome-values` to enumerate valid values.")

(def biome-values
  "Valid biome preset keywords, mirroring Rust's BiomePreset enum."
  #{:plains :quarry :desert :tundra})

(defn heightmap-config
  "HeightmapConfig for this biome at the given seed."
  [biome seed]
  (case biome
    :plains {:seed seed :max-height 80.0 :frequency 0.008 :octaves 7
              :lacunarity 2.0 :persistence 0.5}
    :quarry {:seed seed :max-height 120.0 :frequency 0.012 :octaves 7
              ;; Rolling hills + mid-scale mesas. ~80m main feature wavelength,
              ;; 7 octaves for detail layering, persistence <0.5 keeps
              ;; high-freq gentle (prevents jagged noise). Works at 512m
              ;; world scale.
              :lacunarity 2.1 :persistence 0.45}
    :desert {:seed seed :max-height 45.0 :frequency 0.006 :octaves 5
              :lacunarity 2.0 :persistence 0.45}
    :tundra {:seed seed :max-height 110.0 :frequency 0.005 :octaves 6
              :lacunarity 2.0 :persistence 0.5}))

(defn splat-thresholds
  "Splatmap generation thresholds {:sand-line :snow-line :rock-slope} for this biome."
  [biome]
  (case biome
    :plains {:sand-line 15.0 :snow-line 100.0 :rock-slope 0.4}
    :quarry {:sand-line 5.0 :snow-line 200.0 :rock-slope 0.22}
    :desert {:sand-line 200.0 :snow-line 999.0 :rock-slope 0.6}
    :tundra {:sand-line 10.0 :snow-line 55.0 :rock-slope 0.45}))

(defn palette
  "Material palette for shader upload: {:base [grass rock sand snow] :tip [...]},
  each an RGB triple in [0,1]."
  [biome]
  (case biome
    :plains {:base [[0.28 0.52 0.15]   ; grass (green)
                     [0.45 0.40 0.35]   ; rock
                     [0.76 0.69 0.50]   ; sand
                     [0.92 0.93 0.95]]  ; snow
              :tip [[0.42 0.68 0.22]
                    [0.55 0.50 0.45]
                    [0.85 0.78 0.60]
                    [1.00 1.00 1.00]]}
    :quarry {;; Warm ochre rock + dry tan grass + grey gravel
              :base [[0.48 0.44 0.30]   ; "grass" -> dormant/dry (tan-olive)
                     [0.55 0.42 0.28]   ; rock (warm ochre, sedimentary)
                     [0.62 0.55 0.42]   ; sand (gravel path)
                     [0.85 0.82 0.78]]  ; "snow" -> dusty top layer
              :tip [[0.66 0.58 0.35]
                    [0.72 0.55 0.35]
                    [0.78 0.70 0.55]
                    [0.95 0.92 0.88]]}
    :desert {:base [[0.68 0.55 0.32]
                     [0.58 0.42 0.28]
                     [0.82 0.70 0.50]
                     [0.90 0.82 0.70]]
              :tip [[0.78 0.65 0.40]
                    [0.72 0.52 0.35]
                    [0.92 0.80 0.58]
                    [1.00 0.92 0.78]]}
    :tundra {:base [[0.32 0.42 0.22]
                     [0.40 0.38 0.36]
                     [0.70 0.68 0.55]
                     [0.95 0.96 0.98]]
              :tip [[0.48 0.58 0.30]
                    [0.55 0.50 0.48]
                    [0.82 0.78 0.65]
                    [1.00 1.00 1.00]]}))

(defn biome-name
  "Lowercase string name of this biome, e.g. \"plains\"."
  [biome]
  (case biome
    :plains "plains"
    :quarry "quarry"
    :desert "desert"
    :tundra "tundra"))
