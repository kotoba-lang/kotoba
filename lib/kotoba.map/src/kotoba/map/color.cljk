(ns kotoba.map.color
  "Hex color parsing — ported 1:1 from `parse_hex_color` in
  `kami-map/src/lib.rs` (Rust, kotoba-lang/kami-engine), per ADR-2607010930
  (clj-wgsl migration Phase 4). Pure string -> `[r g b a]` (0.0-1.0 doubles).")

(defn- hex->component [hex start]
  #?(:clj  (try (/ (double (Integer/parseInt (subs hex start (+ start 2)) 16)) 255.0)
                (catch NumberFormatException _ 1.0))
     :cljs (let [n (js/parseInt (subs hex start (+ start 2)) 16)]
             (if (js/isNaN n) 1.0 (/ n 255.0)))))

(defn parse-hex-color
  "Parse a `#rrggbb` or `#rrggbbaa` (leading `#` optional) string into
  `[r g b a]` doubles in `[0.0, 1.0]`. Falls back to `[1.0 1.0 1.0 1.0]`
  (opaque white) when the string is too short or a component fails to
  parse, matching the Rust source's `unwrap_or(255)` fallback behavior."
  [hex]
  (let [hex (if (and (seq hex) (= \# (first hex))) (subs hex 1) hex)]
    (if (< (count hex) 6)
      [1.0 1.0 1.0 1.0]
      (let [r (hex->component hex 0)
            g (hex->component hex 2)
            b (hex->component hex 4)
            a (if (>= (count hex) 8) (hex->component hex 6) 1.0)]
        [r g b a]))))
