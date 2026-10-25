(ns kotoba.wasm.host.color
  "Shared CSS color parsing for kotoba's WebGL/WebGPU paint hosts
   (kotoba.wasm.host.webgl / kotoba.wasm.host.webgpu).

   Both hosts previously carried an IDENTICAL, copy-pasted private
   `hex->rgba` that only understood `#rrggbb` -- any other valid CSS color
   value (a named keyword like `\"red\"`, or functional notation like
   `\"rgb(255, 0, 0)\"`) made `js/parseInt` return `NaN`, which JS's
   bitwise ops then silently coerce to 0, painting the WRONG color
   (typically black) instead of failing loudly. This namespace replaces
   both copies with one real parser covering the CSS color forms actually
   used in the wild:

     - hex: `#rgb`, `#rrggbb`, `#rgba`, `#rrggbbaa` (case-insensitive)
     - the 148 CSS named-color keywords (see `named-colors` below), plus
       `transparent`
     - functional notation: `rgb(r, g, b)` / `rgba(r, g, b, a)`, both the
       long-standing comma syntax and (as a bonus) the newer
       space-separated `rgb(r g b)` / `rgb(r g b / a)` syntax; `r`/`g`/`b`
       may be plain 0-255 numbers or percentages, `a` may be a 0-1 number
       or a percentage; out-of-range values are clamped (per spec) rather
       than rejected
     - `hsl(h, s%, l%)` / `hsla(h, s%, l%, a)`, same comma/space-syntax
       duality as `rgb()`; `h` is a bare number or `deg`-suffixed angle
       (wrapped modulo 360, matching real browsers), `s`/`l` MUST be
       percentages (CSS's own `<percentage>`-only grammar for these two
       arguments -- a bare number here is not valid CSS, unlike `rgb()`'s
       channels), `a` has the same 0-1-number-or-percentage grammar as
       `rgba()`. Converted to RGB via the CSS Color Module Level 4
       algorithm (https://www.w3.org/TR/css-color-4/#hsl-to-rgb).

   CSS Level 4 features beyond the above (e.g. `rgb(from ...)`, `lab()`,
   `color()`, `hsl()`'s `rad`/`grad`/`turn` angle units) are NOT
   implemented. A color string this parser can't make sense of -- a typo,
   an unresolved `var(--x)` that should have been substituted upstream,
   a `lab(...)` call, etc. -- is a deliberate, documented case (see
   `->rgba` below), not a crash and not a silently-wrong color.

   ALPHA CONTRACT (unchanged from the old per-file `hex->rgba`): CSS
   `opacity` is a separate, already-cascaded value computed cumulatively
   down the element tree by cssom.layout and stamped onto every draw op
   as `:opacity` (see layout.cljc's `opacity (* opacity (:opacity st))`).
   Callers pass that value through explicitly as this namespace's `alpha`
   arg. `->rgba`'s own color parsing yields ONLY the color value's OWN
   alpha channel (e.g. `rgba(0,0,0,0.5)`'s `0.5`, `#rrggbbaa`'s alpha
   byte, `transparent`'s `0`, or `1` for every color form with no alpha
   component of its own) -- the returned 4th element is
   `(* alpha own-alpha)`, exactly as the old 2-arity `hex->rgba` already
   multiplied (trivially, since its own-alpha was always implicitly 1)."
  (:require [kotoba.lang.text :as str]))

;; 148 CSS Color Module named-color keywords -- the 16 basic CSS2.1
;; keywords (black, silver, gray, white, maroon, red, purple, fuchsia,
;; green, lime, olive, yellow, navy, blue, teal, aqua) plus the 132
;; SVG/CSS3 "extended color keywords" that were folded into CSS Color
;; Module Level 3/4 -- transcribed verbatim (name -> [r g b] byte triple)
;; from MDN's CSS named-color reference
;; (https://developer.mozilla.org/en-US/docs/Web/CSS/named-color),
;; cross-checked against well-known fixed points (red=#ff0000,
;; cornflowerblue=#6495ed, rebeccapurple=#663399, papayawhip=#ffefd5,
;; darkslategray=#2f4f4f, ...) and programmatically deduplicated (several
;; names, e.g. aqua/cyan, gray/grey, fuchsia/magenta, are legitimate
;; synonym pairs that map to the same triple -- that's correct, not a
;; bug). `transparent` is intentionally NOT in this table: it is a
;; distinct CSS value keyword (not part of the `<named-color>` grammar
;; production) meaning `rgba(0,0,0,0)`, handled as its own case in
;; `parse-color` below. So this parser recognizes 148 + 1 = 149 keywords
;; total, one more than the "148" figure sometimes quoted for "named
;; colors including transparent" (that folk count treats the named-color
;; table itself as 147-long; MDN's authoritative table is 148 long before
;; `transparent` is even added -- see this session's report for the
;; from-scratch recount).
(def named-colors
  {"aliceblue" [0xf0 0xf8 0xff]
   "antiquewhite" [0xfa 0xeb 0xd7]
   "aqua" [0x00 0xff 0xff]
   "aquamarine" [0x7f 0xff 0xd4]
   "azure" [0xf0 0xff 0xff]
   "beige" [0xf5 0xf5 0xdc]
   "bisque" [0xff 0xe4 0xc4]
   "black" [0x00 0x00 0x00]
   "blanchedalmond" [0xff 0xeb 0xcd]
   "blue" [0x00 0x00 0xff]
   "blueviolet" [0x8a 0x2b 0xe2]
   "brown" [0xa5 0x2a 0x2a]
   "burlywood" [0xde 0xb8 0x87]
   "cadetblue" [0x5f 0x9e 0xa0]
   "chartreuse" [0x7f 0xff 0x00]
   "chocolate" [0xd2 0x69 0x1e]
   "coral" [0xff 0x7f 0x50]
   "cornflowerblue" [0x64 0x95 0xed]
   "cornsilk" [0xff 0xf8 0xdc]
   "crimson" [0xdc 0x14 0x3c]
   "cyan" [0x00 0xff 0xff]
   "darkblue" [0x00 0x00 0x8b]
   "darkcyan" [0x00 0x8b 0x8b]
   "darkgoldenrod" [0xb8 0x86 0x0b]
   "darkgray" [0xa9 0xa9 0xa9]
   "darkgreen" [0x00 0x64 0x00]
   "darkgrey" [0xa9 0xa9 0xa9]
   "darkkhaki" [0xbd 0xb7 0x6b]
   "darkmagenta" [0x8b 0x00 0x8b]
   "darkolivegreen" [0x55 0x6b 0x2f]
   "darkorange" [0xff 0x8c 0x00]
   "darkorchid" [0x99 0x32 0xcc]
   "darkred" [0x8b 0x00 0x00]
   "darksalmon" [0xe9 0x96 0x7a]
   "darkseagreen" [0x8f 0xbc 0x8f]
   "darkslateblue" [0x48 0x3d 0x8b]
   "darkslategray" [0x2f 0x4f 0x4f]
   "darkslategrey" [0x2f 0x4f 0x4f]
   "darkturquoise" [0x00 0xce 0xd1]
   "darkviolet" [0x94 0x00 0xd3]
   "deeppink" [0xff 0x14 0x93]
   "deepskyblue" [0x00 0xbf 0xff]
   "dimgray" [0x69 0x69 0x69]
   "dimgrey" [0x69 0x69 0x69]
   "dodgerblue" [0x1e 0x90 0xff]
   "firebrick" [0xb2 0x22 0x22]
   "floralwhite" [0xff 0xfa 0xf0]
   "forestgreen" [0x22 0x8b 0x22]
   "fuchsia" [0xff 0x00 0xff]
   "gainsboro" [0xdc 0xdc 0xdc]
   "ghostwhite" [0xf8 0xf8 0xff]
   "gold" [0xff 0xd7 0x00]
   "goldenrod" [0xda 0xa5 0x20]
   "gray" [0x80 0x80 0x80]
   "green" [0x00 0x80 0x00]
   "greenyellow" [0xad 0xff 0x2f]
   "grey" [0x80 0x80 0x80]
   "honeydew" [0xf0 0xff 0xf0]
   "hotpink" [0xff 0x69 0xb4]
   "indianred" [0xcd 0x5c 0x5c]
   "indigo" [0x4b 0x00 0x82]
   "ivory" [0xff 0xff 0xf0]
   "khaki" [0xf0 0xe6 0x8c]
   "lavender" [0xe6 0xe6 0xfa]
   "lavenderblush" [0xff 0xf0 0xf5]
   "lawngreen" [0x7c 0xfc 0x00]
   "lemonchiffon" [0xff 0xfa 0xcd]
   "lightblue" [0xad 0xd8 0xe6]
   "lightcoral" [0xf0 0x80 0x80]
   "lightcyan" [0xe0 0xff 0xff]
   "lightgoldenrodyellow" [0xfa 0xfa 0xd2]
   "lightgray" [0xd3 0xd3 0xd3]
   "lightgreen" [0x90 0xee 0x90]
   "lightgrey" [0xd3 0xd3 0xd3]
   "lightpink" [0xff 0xb6 0xc1]
   "lightsalmon" [0xff 0xa0 0x7a]
   "lightseagreen" [0x20 0xb2 0xaa]
   "lightskyblue" [0x87 0xce 0xfa]
   "lightslategray" [0x77 0x88 0x99]
   "lightslategrey" [0x77 0x88 0x99]
   "lightsteelblue" [0xb0 0xc4 0xde]
   "lightyellow" [0xff 0xff 0xe0]
   "lime" [0x00 0xff 0x00]
   "limegreen" [0x32 0xcd 0x32]
   "linen" [0xfa 0xf0 0xe6]
   "magenta" [0xff 0x00 0xff]
   "maroon" [0x80 0x00 0x00]
   "mediumaquamarine" [0x66 0xcd 0xaa]
   "mediumblue" [0x00 0x00 0xcd]
   "mediumorchid" [0xba 0x55 0xd3]
   "mediumpurple" [0x93 0x70 0xdb]
   "mediumseagreen" [0x3c 0xb3 0x71]
   "mediumslateblue" [0x7b 0x68 0xee]
   "mediumspringgreen" [0x00 0xfa 0x9a]
   "mediumturquoise" [0x48 0xd1 0xcc]
   "mediumvioletred" [0xc7 0x15 0x85]
   "midnightblue" [0x19 0x19 0x70]
   "mintcream" [0xf5 0xff 0xfa]
   "mistyrose" [0xff 0xe4 0xe1]
   "moccasin" [0xff 0xe4 0xb5]
   "navajowhite" [0xff 0xde 0xad]
   "navy" [0x00 0x00 0x80]
   "oldlace" [0xfd 0xf5 0xe6]
   "olive" [0x80 0x80 0x00]
   "olivedrab" [0x6b 0x8e 0x23]
   "orange" [0xff 0xa5 0x00]
   "orangered" [0xff 0x45 0x00]
   "orchid" [0xda 0x70 0xd6]
   "palegoldenrod" [0xee 0xe8 0xaa]
   "palegreen" [0x98 0xfb 0x98]
   "paleturquoise" [0xaf 0xee 0xee]
   "palevioletred" [0xdb 0x70 0x93]
   "papayawhip" [0xff 0xef 0xd5]
   "peachpuff" [0xff 0xda 0xb9]
   "peru" [0xcd 0x85 0x3f]
   "pink" [0xff 0xc0 0xcb]
   "plum" [0xdd 0xa0 0xdd]
   "powderblue" [0xb0 0xe0 0xe6]
   "purple" [0x80 0x00 0x80]
   "rebeccapurple" [0x66 0x33 0x99]
   "red" [0xff 0x00 0x00]
   "rosybrown" [0xbc 0x8f 0x8f]
   "royalblue" [0x41 0x69 0xe1]
   "saddlebrown" [0x8b 0x45 0x13]
   "salmon" [0xfa 0x80 0x72]
   "sandybrown" [0xf4 0xa4 0x60]
   "seagreen" [0x2e 0x8b 0x57]
   "seashell" [0xff 0xf5 0xee]
   "sienna" [0xa0 0x52 0x2d]
   "silver" [0xc0 0xc0 0xc0]
   "skyblue" [0x87 0xce 0xeb]
   "slateblue" [0x6a 0x5a 0xcd]
   "slategray" [0x70 0x80 0x90]
   "slategrey" [0x70 0x80 0x90]
   "snow" [0xff 0xfa 0xfa]
   "springgreen" [0x00 0xff 0x7f]
   "steelblue" [0x46 0x82 0xb4]
   "tan" [0xd2 0xb4 0x8c]
   "teal" [0x00 0x80 0x80]
   "thistle" [0xd8 0xbf 0xd8]
   "tomato" [0xff 0x63 0x47]
   "turquoise" [0x40 0xe0 0xd0]
   "violet" [0xee 0x82 0xee]
   "wheat" [0xf5 0xde 0xb3]
   "white" [0xff 0xff 0xff]
   "whitesmoke" [0xf5 0xf5 0xf5]
   "yellow" [0xff 0xff 0x00]
   "yellowgreen" [0x9a 0xcd 0x32]})

;; Single-hex-digit "0".."9"/"a".."f" -> 0-15, keyed by 1-char STRING (not
;; a Character) so the same map/lookup works unchanged on both platforms
;; -- `subs` returns a 1-char string on both JVM Clojure and
;; ClojureScript, sidestepping the fact that ClojureScript has no
;; separate Character type.
(def ^:private hex-digit-values
  (into {} (map-indexed (fn [i d] [d i])
                        ["0" "1" "2" "3" "4" "5" "6" "7" "8" "9"
                         "a" "b" "c" "d" "e" "f"])))

(defn- hex-digit [s i]
  (get hex-digit-values (subs s i (inc i))))

(defn- hex-nibble-byte
  "1 hex digit at index `i`, doubled (CSS shorthand hex rule: `f` in
   `#f00` means `ff`, i.e. value*16 + value = value*17)."
  [s i]
  (when-let [d (hex-digit s i)]
    (* d 17)))

(defn- hex-pair-byte
  "2 hex digits starting at index `i` -> 0-255."
  [s i]
  (let [hi (hex-digit s i) lo (hex-digit s (inc i))]
    (when (and hi lo) (+ (* hi 16) lo))))

(defn- unit [byte-0-255] (/ byte-0-255 255))

(defn- parse-hex
  "`s` is the hex digits ONLY (no leading `#`), already lower-cased.
   Returns `[r g b a]` with each channel in 0..1, or nil if `s` isn't
   exactly 3, 4, 6, or 8 valid hex digits."
  [s]
  (when (re-matches #"[0-9a-f]+" s)
    (case (count s)
      3 (let [r (hex-nibble-byte s 0) g (hex-nibble-byte s 1) b (hex-nibble-byte s 2)]
          [(unit r) (unit g) (unit b) 1])
      4 (let [r (hex-nibble-byte s 0) g (hex-nibble-byte s 1)
              b (hex-nibble-byte s 2) a (hex-nibble-byte s 3)]
          [(unit r) (unit g) (unit b) (unit a)])
      6 (let [r (hex-pair-byte s 0) g (hex-pair-byte s 2) b (hex-pair-byte s 4)]
          [(unit r) (unit g) (unit b) 1])
      8 (let [r (hex-pair-byte s 0) g (hex-pair-byte s 2)
              b (hex-pair-byte s 4) a (hex-pair-byte s 6)]
          [(unit r) (unit g) (unit b) (unit a)])
      nil)))

(defn- clamp [lo hi n] (max lo (min hi n)))

(defn- parse-css-double
  "Named to avoid shadowing `clojure.core/parse-double` (Clojure 1.11+)."
  [s]
  #?(:clj (try (Double/parseDouble s) (catch NumberFormatException _ nil))
     :cljs (let [n (js/parseFloat s)] (when-not (js/isNaN n) n))))

(defn- parse-number-token
  "Parses one rgb()/rgba() argument token, which may be a plain number or
   a percentage. Returns `[value percent?]`, or nil if `tok` isn't a
   valid CSS number."
  [tok]
  (when (re-matches #"[+-]?(\d+\.?\d*|\.\d+)%?" tok)
    (let [pct? (str/ends-with? tok "%")
          body (cond-> tok pct? (subs 0 (dec (count tok))))]
      (when-let [n (parse-css-double body)]
        [n pct?]))))

(defn- parse-channel-token
  "0-255 color channel; a percentage token is scaled from 0-100% to
   0-255. Out-of-range values are clamped, matching the CSS spec (an
   out-of-gamut rgb()/rgba() channel is valid and clamped, not invalid)."
  [tok]
  (when-let [[n pct?] (parse-number-token tok)]
    (clamp 0 255 (if pct? (* (/ n 100) 255) n))))

(defn- parse-alpha-token
  "0-1 alpha; a percentage token is scaled from 0-100% to 0-1. Clamped
   the same way channel tokens are."
  [tok]
  (when-let [[n pct?] (parse-number-token tok)]
    (clamp 0 1 (if pct? (/ n 100) n))))

(defn- split-fn-args
  "Splits the inside-the-parens text of `rgb(...)`/`rgba(...)` into
   argument tokens, supporting both the long-standing comma syntax
   (`r, g, b[, a]`) and the newer space syntax (`r g b[ / a]`)."
  [inner]
  (if (str/includes? inner ",")
    (->> (str/split inner #",") (map str/trim) (remove str/blank?))
    (let [[main alpha-part] (str/split inner #"/" 2)
          main-toks (->> (str/split (str/trim main) #"\s+") (remove str/blank?))
          alpha-toks (when alpha-part
                       (->> (str/split (str/trim alpha-part) #"\s+") (remove str/blank?)))]
      (vec (concat main-toks alpha-toks)))))

(defn- parse-rgb-fn
  "`ls` is the full, lower-cased, trimmed color string. Returns
   `[r g b a]` (0..1 channels) or nil."
  [ls]
  (when-let [[_ inner] (re-matches #"rgba?\((.*)\)" ls)]
    (let [toks (split-fn-args inner)]
      (when (<= 3 (count toks) 4)
        (let [[r-tok g-tok b-tok a-tok] toks
              r (parse-channel-token r-tok)
              g (parse-channel-token g-tok)
              b (parse-channel-token b-tok)
              a (if a-tok (parse-alpha-token a-tok) 1)]
          (when (and r g b a)
            [(unit r) (unit g) (unit b) a]))))))

(defn- parse-hue-token
  "Parses an hsl()/hsla() hue token: a bare number (`120`) or a `deg`-
   suffixed angle (`120deg`), the two most common real-world hue forms.
   `rad`/`grad`/`turn` angle units (CSS Color 4) are deliberately NOT
   supported, mirroring this namespace's existing \"most common forms,
   not full spec coverage\" convention. Unlike a color channel, a hue
   is never clamped here -- it's a circular quantity, wrapped modulo 360
   by `hsl->rgb` instead (a real, valid CSS pattern: `hsl(-120, ...)` and
   `hsl(480, ...)` are both legal and equivalent to `hsl(240, ...)`)."
  [tok]
  (parse-css-double (if (str/ends-with? tok "deg") (subs tok 0 (- (count tok) 3)) tok)))

(defn- parse-percent-token
  "hsl()/hsla()'s saturation/lightness arguments are CSS <percentage>
   values -- unlike rgb()'s channels, a bare number is NOT valid CSS for
   these two arguments, so (unlike parse-channel-token) this rejects a
   token with no `%` suffix. Returns a 0..1 fraction, clamped."
  [tok]
  (when (str/ends-with? tok "%")
    (let [[n pct?] (parse-number-token tok)]
      (when pct? (clamp 0 1 (/ n 100))))))

(defn- hsl->rgb
  "The CSS Color Module Level 4 hsl-to-rgb conversion
   (https://www.w3.org/TR/css-color-4/#hsl-to-rgb). `h` is a hue angle in
   degrees (any real number, wrapped modulo 360 here); `s`/`l` are 0..1
   fractions (already clamped by `parse-percent-token`). Returns `[r g b]`
   with each channel already in 0..1 -- no separate `unit` byte-scaling
   needed, unlike hex/rgb()'s 0-255 channels."
  [h s l]
  (let [h (mod h 360)
        f (fn [n]
            (let [k (mod (+ n (/ h 30)) 12)
                  a (* s (min l (- 1 l)))]
              (- l (* a (max -1 (min (- k 3) (- 9 k) 1))))))]
    [(f 0) (f 8) (f 4)]))

(defn- parse-hsl-fn
  "`ls` is the full, lower-cased, trimmed color string. Returns
   `[r g b a]` (0..1 channels) or nil."
  [ls]
  (when-let [[_ inner] (re-matches #"hsla?\((.*)\)" ls)]
    (let [toks (split-fn-args inner)]
      (when (<= 3 (count toks) 4)
        (let [[h-tok s-tok l-tok a-tok] toks
              h (parse-hue-token h-tok)
              s (parse-percent-token s-tok)
              l (parse-percent-token l-tok)
              a (if a-tok (parse-alpha-token a-tok) 1)]
          (when (and h s l a)
            (conj (hsl->rgb h s l) a)))))))

(defn parse-color
  "Parses any of this namespace's supported CSS `<color>` forms (see
   namespace docstring) into `[r g b a]`, each channel a float in 0..1.
   Returns nil for anything this parser doesn't understand (typo,
   unresolved `var()`, `lab()`, etc.) -- callers decide the fallback (see
   `->rgba`); this function itself never throws and never guesses."
  [color]
  (when (string? color)
    (let [trimmed (str/trim color)]
      (when (seq trimmed)
        (let [ls (str/lower trimmed)]
          (cond
            (= ls "transparent") [0 0 0 0]
            (str/starts-with? ls "#") (parse-hex (subs ls 1))
            (str/starts-with? ls "rgb") (parse-rgb-fn ls)
            (str/starts-with? ls "hsl") (parse-hsl-fn ls)
            :else (when-let [[r g b] (get named-colors ls)]
                    [(unit r) (unit g) (unit b) 1])))))))

(defn- warn-unparseable! [color]
  #?(:cljs (js/console.warn "kotoba.wasm.host.color: unparseable CSS color, painting fully transparent:" color)
     :clj nil))

(defn ->rgba
  "hex is (despite the name, kept for call-site continuity) any CSS color
   string this namespace's `parse-color` understands: `#rgb`/`#rrggbb`/
   `#rgba`/`#rrggbbaa` hex, one of the 148 named colors + `transparent`,
   `rgb()`/`rgba()`, or `hsl()`/`hsla()` functional notation.

   `alpha` is the SEPARATE, already-cascaded CSS `opacity` value (see the
   namespace docstring's ALPHA CONTRACT) -- it multiplies with the
   color's own alpha channel, it is not the color's own alpha. Defaults
   to fully opaque (1) so a 1-arity call is unaffected, matching the old
   per-file `hex->rgba`'s own 1-arity default.

   A color string `parse-color` can't understand -- deliberately, see
   the namespace docstring -- paints as fully transparent
   (`[0 0 0 0]`, independent of `alpha`) rather than guessing a possibly
   wrong opaque color (the old bug: NaN-from-parseInt coerced to 0 by
   bitwise ops, silently painting black) or throwing and breaking the
   whole frame. In a ClojureScript host this also logs a `console.warn`
   so the bad value is discoverable during development; on the JVM
   (tests) it's silent, since a test asserting the fallback shouldn't
   also have to assert against stderr noise."
  ([hex] (->rgba hex 1))
  ([hex alpha]
   (if-let [[r g b own-a] (parse-color hex)]
     [r g b (* alpha own-a)]
     (do (warn-unparseable! hex)
         [0 0 0 0]))))
