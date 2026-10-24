(ns kotoba.car-sim.color
  "Pure colour/numeric utilities ported verbatim from `kami-app-car-sim`'s
  `src/lib.rs` (the only DOMAIN-pure logic that lived directly in the Rust
  app crate itself, as opposed to the `kami-vehicle`/`kami-vehicle-scene`
  physics/scene crates it depended on — ADR-2607010000).

  Pure data in, pure data out: no network, no I/O. Portable across
  JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ── Paint colour ─────────────────────────────────────────────────────────────

(defn- parse-hex-byte [sub]
  #?(:clj (try (Integer/parseInt sub 16) (catch Exception _ nil))
     :cljs (let [n (js/parseInt sub 16)] (when-not (js/isNaN n) n))))

(defn parse-color-hex
  "Parse a `#rrggbb` (leading `#` optional) hex string into a paint colour
  `[r g b]` (floats, 0..1). A malformed *length* (not exactly 6 hex
  digits) falls back to the default red `[0.85 0.20 0.25]`; a malformed
  digit *within* a well-sized string falls back per-channel to `0xda`
  `0x33` `0x40` (`\"da3340\"`, the same default red baked as raw bytes).
  Mirrors Rust `parse_color_hex` exactly, including its two distinct
  fallback paths."
  [s]
  (let [s (str/replace (or s "") #"^#" "")]
    (if (not= (count s) 6)
      [0.85 0.20 0.25]
      (let [r (or (parse-hex-byte (subs s 0 2)) 218)
            g (or (parse-hex-byte (subs s 2 4)) 51)
            b (or (parse-hex-byte (subs s 4 6)) 64)]
        [(/ r 255.0) (/ g 255.0) (/ b 255.0)]))))

;; ── IEEE-754 binary32 -> binary16 (half float) ───────────────────────────────
;; Used by the Rust renderer to pack the baked sky cubemap into an
;; `Rgba16Float` texture. Kept here as a pure numeric utility since it has
;; no wgpu/texture dependency of its own.

(defn- bits-of-f32
  "The IEEE-754 binary32 bit pattern of `v`, as a non-negative integer."
  [v]
  #?(:clj (bit-and (long (Float/floatToRawIntBits (float v))) 0xFFFFFFFF)
     :cljs (let [buf (js/ArrayBuffer. 4)
                 f32 (js/Float32Array. buf)
                 u32 (js/Uint32Array. buf)]
             (aset f32 0 v)
             (aget u32 0))))

(defn f32->f16-bits
  "Convert `v` (IEEE 754 binary32) to its binary16 (half) bit pattern (an
  integer 0..0xFFFF). Handles overflow -> +-Inf, underflow -> +-0,
  otherwise exponent shift + 13-bit mantissa truncation — denormals are
  flushed to zero (sufficient for HDR colour values, which never need
  denormal precision). Ported verbatim from `f32_to_f16_bits`."
  [v]
  (let [bits (bits-of-f32 v)
        sign (bit-and (unsigned-bit-shift-right bits 31) 1)
        exp (bit-and (unsigned-bit-shift-right bits 23) 0xff)
        mant (bit-and bits 0x7fffff)]
    (cond
      ;; +-0 or denormal -> flush to signed zero.
      (zero? exp) (bit-shift-left sign 15)
      ;; Inf / NaN.
      (= exp 0xff) (bit-or (bit-shift-left sign 15)
                            (bit-shift-left 0x1f 10)
                            (if (not (zero? mant)) 0x200 0))
      :else
      (let [new-exp (- exp 112)] ; exp - 127 + 15
        (cond
          (>= new-exp 0x1f) (bit-or (bit-shift-left sign 15) (bit-shift-left 0x1f 10)) ; overflow
          (<= new-exp 0) (bit-shift-left sign 15) ; underflow
          :else (bit-or (bit-shift-left sign 15)
                         (bit-shift-left new-exp 10)
                         (unsigned-bit-shift-right mant 13)))))))
