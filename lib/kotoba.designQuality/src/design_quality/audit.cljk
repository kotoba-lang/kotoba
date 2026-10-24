(ns design-quality.audit
  "Deterministic HIG/WCAG UI-quality audit — the *measurable* arm of the
   kotoba-lang design-quality system (ADR-2607132300).

   Founding rule (isekai iteration-02, carried through both upstream forks):
   an unverified / opinion-only metric is 'theater'. The design-quality
   `:llm-judge` layer (3-judge panel scoring clarity/deference/depth/
   consistency/token-discipline) is subjective by design; this namespace is
   the complementary deterministic arm. It scores ACTUAL page source
   (HTML + inline CSS) against Apple-HIG / WCAG / mobile-first heuristics —
   NO LLM, NO browser, regex over source. Each axis yields a 0..1 score, a
   weight, and a concrete *finding* when it falls short (the seed a
   Co-Scientist Generate step turns into a hypothesis). Re-running
   before/after an edit yields the honest kaizen delta.

   This is the SSoT extracted from two forks:
     - isekai.ux.audit           (origin, network-isekai ADR-0007)
     - design-quality.audit      (superproject 90-docs port, ADR-2607132300)
   Axes are DATA: `default-axes` is the 10-axis core both forks share
   (generic finding text, unified control-detection); the isekai-only axes
   (`input-zoom-axis`, `contrast-axis`) ship as optional `extra-axes`.
   Consumers express their deltas as data via the opts map accepted by
   `score-page` / `audit`:

     (audit pages {:extra-axes extra-axes          ;; isekai: add input-zoom + contrast
                   :weights    {:tap-targets 0.2}  ;; per-axis weight override
                   :skip       #{:contrast}        ;; drop axes by id
                   :axes       [...]})             ;; or replace the base set wholesale

   Pure `.cljc`: runs on nbb, babashka, ClojureScript, and the JVM. No deps
   beyond clojure.string. `score-page` scores one source string; `audit`
   aggregates across pages — both return the exact shape the two upstream
   forks return, so both can delegate here as thin wrappers.

   Known limits (documented in ADR-2607132300 addendum 3): heuristics are
   static regex over source, so client-side-rendered apps whose interactive
   elements only exist at JS runtime can score false-positive on
   :tap-targets / :focus-visible / :input-zoom (no literal `<button`/`<input`
   in the static file). Audit the rendered/built page, and concatenate any
   `<link>`-ed stylesheets into the source string before scoring."
  (:require [kotoba.lang.text :as str]))

(defn- has? [s re] (boolean (re-find re s)))

(defn- style-css
  "Just the CSS — the concatenated contents of every <style> block (so font
   checks don't trip over <input>/<textarea> HTML tags or comment prose)."
  [s] (str/join "\n" (map second (re-seq #"(?is)<style[^>]*>(.*?)</style>" s))))

(defn- field-font-sizes
  "Declared font sizes (px) on rules that target a text field (#editor /
   textarea / input / contenteditable) — the only fonts where <16px triggers
   iOS Safari's zoom-on-focus."
  [s]
  (let [css (style-css s)]
    (->> (re-seq #"(?is)(?:#editor|textarea|\binput\b|contenteditable)[^{}]*\{([^}]*)\}" css)
         (mapcat (fn [[_ body]] (re-seq #"font(?:-size)?:\s*(\d{1,3})px" body)))
         (map (fn [[_ n]] (parse-long n)))
         (remove nil?))))

;; --- colour + WCAG contrast (1.4.3) ------------------------------------------
;; A small, correct sRGB contrast calculator: parse #rgb[a]/#rrggbb[aa]/rgb[a]()
;; → [r g b a], blend a translucent colour over a background, relative
;; luminance, ratio. The hard part (which fg sits on which bg) is approximated:
;; muted black/white *text* colours are blended over the page's detected
;; dominant background and checked against the 4.5:1 body-text threshold — the
;; canonical low-contrast antipattern.

(defn- hex16 [s] #?(:clj (Long/parseLong s 16) :cljs (js/parseInt s 16)))

(defn- hex->rgba
  "Parse #rgb / #rgba / #rrggbb / #rrggbbaa → [r g b a] (a in 0..1), or nil."
  [h]
  (let [h (str/replace h "#" "")
        n (count h)]
    (cond
      (#{6 8} n) (let [p (fn [i] (hex16 (subs h i (+ i 2))))]
                   [(p 0) (p 2) (p 4) (if (= n 8) (/ (p 6) 255.0) 1.0)])
      (#{3 4} n) (let [d (fn [i] (let [c (subs h i (inc i))] (hex16 (str c c))))]
                   [(d 0) (d 1) (d 2) (if (= n 4) (/ (d 3) 255.0) 1.0)])
      :else nil)))

(defn parse-color
  "Parse a CSS colour token → [r g b a] (0..255, a 0..1), or nil. Handles hex + rgb[a]()."
  [tok]
  (let [t (str/trim tok)]
    (cond
      (str/starts-with? t "#") (hex->rgba t)
      (str/starts-with? t "rgb")
      (let [nums (map #(#?(:clj Double/parseDouble :cljs js/parseFloat) %)
                      (re-seq #"[\d.]+" t))]
        (when (>= (count nums) 3)
          [(nth nums 0) (nth nums 1) (nth nums 2) (if (>= (count nums) 4) (nth nums 3) 1.0)]))
      :else nil)))

(defn- blend [[r g b a] [br bg bb]]
  (let [a (double a)]
    [(+ (* r a) (* br (- 1 a))) (+ (* g a) (* bg (- 1 a))) (+ (* b a) (* bb (- 1 a)))]))

(defn- lin [c]
  (let [c (/ c 255.0)]
    (if (<= c 0.03928) (/ c 12.92) (Math/pow (/ (+ c 0.055) 1.055) 2.4))))

(defn relative-luminance [[r g b]]
  (+ (* 0.2126 (lin r)) (* 0.7152 (lin g)) (* 0.0722 (lin b))))

(defn contrast-ratio
  "WCAG contrast ratio between two opaque [r g b] colours (1..21)."
  [c1 c2]
  (let [l1 (relative-luminance c1) l2 (relative-luminance c2)
        hi (max l1 l2) lo (min l1 l2)]
    (/ (+ hi 0.05) (+ lo 0.05))))

(defn- dominant-bg
  "The page's dominant light background [r g b] — from --bg/--cream/body background, else white."
  [s]
  (let [css (style-css s)
        cand (or (second (re-find #"(?i)--bg\s*:\s*(#[0-9a-f]{3,8})" css))
                 (second (re-find #"(?i)--cream\s*:\s*(#[0-9a-f]{3,8})" css))
                 (second (re-find #"(?i)body[^{}]*\{[^}]*background:\s*(#[0-9a-f]{3,8})" css))
                 "#ffffff")]
    (vec (take 3 (or (hex->rgba cand) [255 255 255])))))

(defn- text-colors
  "All `color:` declarations in the CSS (the candidate text colours), as raw tokens."
  [s]
  (->> (re-seq #"(?i)[^-]color:\s*([^;}]+)" (style-css s))
       (map (comp str/trim second))
       (remove #(str/starts-with? % "var"))    ;; vars resolve to solid tokens elsewhere
       (remove empty?)))

(defn- muted-text?
  "A near-black / near-white colour with opacity < 0.66 — the canonical muted-text
   antipattern that almost always falls under 4.5:1 for body copy."
  [[r g b a]]
  (and a (< a 0.66)
       (or (every? #(< % 40) [r g b]) (every? #(> % 215) [r g b]))))

(defn- round1 [x] (/ (Math/round (* 10.0 (double x))) 10.0))

;; --- the axes: HIG / WCAG / mobile-first, as data ----------------------------
;; Each axis: {:id :title :weight :check}. `check` is (fn [src] -> {:score 0..1 :finding str?}).
;; A finding is emitted only when the axis is below 1.0 — it names the concrete gap.
;; Weights/thresholds match both upstream forks (they were already identical).

(def default-axes
  "The 10-axis core shared by both upstream forks. Finding text is generic
   (the superproject fork's library-specific messages are a consumer concern —
   override an axis via the `:axes` opt to customize wording)."
  [{:id :viewport :title "Viewport meta (device-width + viewport-fit)" :weight 0.10
    :check (fn [s]
             (let [vp (re-find #"(?is)<meta[^>]*name=[\"']?viewport[\"' >][^>]*>" s)]
               (if-not vp
                 {:score 0.0 :finding "no <meta name=viewport> — the page won't fit device width"}
                 (let [bits {"width=device-width" #"width=device-width"
                             "initial-scale=1"     #"initial-scale=1"
                             "viewport-fit=cover"  #"viewport-fit=cover"}
                       missing (keep (fn [[lbl re]] (when-not (re-find re vp) lbl)) bits)]
                   {:score (/ (- 3 (count missing)) 3.0)
                    :finding (when (seq missing) (str "viewport missing: " (str/join ", " missing)))}))))}

   {:id :safe-area :title "Safe-area insets (notch / home indicator)" :weight 0.13
    :check (fn [s]
             (let [n (count (distinct (re-seq #"safe-area-inset-\w+" s)))]
               (cond
                 (>= n 2) {:score 1.0}
                 (= n 1)  {:score 0.6 :finding "only one safe-area-inset edge handled — cover all edges that meet the screen"}
                 :else    {:score 0.0 :finding "no env(safe-area-inset-*) — content can sit under the notch / home indicator"})))}

   {:id :dynamic-viewport :title "Dynamic viewport (100dvh, not bare 100vh)" :weight 0.09
    :check (fn [s]
             (cond
               (has? s #"\d+dvh")          {:score 1.0}
               (has? s #"height:\s*100vh") {:score 0.3 :finding "uses 100vh without a 100dvh fallback — full-height layout jumps under mobile browser chrome"}
               :else                       {:score 1.0}))}

   {:id :tap-targets :title "Tap targets ≥ 44pt (HIG)" :weight 0.13
    :check (fn [s]
             ;; control detection is the union of both forks' patterns
             ;; (isekai: <button/.btn/role=button; superproject: liquid-glass buttons)
             (let [buttons? (has? s #"(?i)<button|\brole=[\"']button|\.btn\b|liquid-glass__button|liquid-glass__icon-button")]
               (cond
                 (not buttons?) {:score 1.0}
                 (has? s #"min-height:\s*(4[4-9]|[5-9]\d|\d{3,})px") {:score 1.0}
                 :else {:score 0.35 :finding "interactive controls without an explicit min-height ≥44px — sub-target taps on a phone"})))}

   {:id :focus-visible :title "Keyboard focus ring (:focus-visible)" :weight 0.09
    :check (fn [s]
             (if (has? s #":focus-visible")
               {:score 1.0}
               {:score (if (has? s #"(?i)<button|<a |<input|<textarea") 0.0 1.0)
                :finding "no :focus-visible styles — keyboard/switch users get no visible focus (WCAG 2.4.7)"}))}

   {:id :reduced-motion :title "Honors prefers-reduced-motion (WCAG 2.3.3)" :weight 0.11
    :check (fn [s]
             (let [motion? (has? s #"(?i)transition\s*:|animation\s*:|@keyframes|scroll-behavior:\s*smooth")]
               (cond
                 (has? s #"prefers-reduced-motion") {:score 1.0}
                 (not motion?)                      {:score 1.0}
                 :else {:score 0.0 :finding "animations/transitions with no @media (prefers-reduced-motion) — ignores the OS 'reduce motion' setting (WCAG 2.3.3)"})))}

   {:id :overflow-guard :title "No horizontal scroll" :weight 0.06
    :check (fn [s]
             (if (has? s #"(?i)overflow-x:\s*(clip|hidden)|overflow:\s*hidden")
               {:score 1.0}
               {:score 0.5 :finding "no overflow-x guard on html/body — a stray wide element causes sideways scroll on mobile"}))}

   {:id :color-scheme :title "Dark mode + theme-color" :weight 0.06
    :check (fn [s]
             (let [signals (cond-> 0
                             (has? s #"(?i)name=[\"']?theme-color[\"' >]") inc
                             (has? s #"(?i)prefers-color-scheme|color-scheme:") inc)]
               (case signals
                 2 {:score 1.0}
                 1 {:score 0.6 :finding "partial dark-mode support — declare BOTH <meta theme-color> and a color-scheme/prefers-color-scheme rule"}
                 0 {:score 0.0 :finding "no theme-color and no color-scheme — the browser UI and form controls won't match the page in dark mode"})))}

   {:id :responsive :title "Responsive breakpoints" :weight 0.07
    :check (fn [s]
             (if (has? s #"@media[^{]*max-width")
               {:score 1.0}
               {:score 0.0 :finding "no max-width media query — a single fixed layout for phone and desktop"}))}

   {:id :semantics :title "Document semantics (lang + charset)" :weight 0.05
    :check (fn [s]
             (let [ok (cond-> 0 (has? s #"(?i)<html[^>]*\blang=") inc (has? s #"(?i)charset=") inc)]
               {:score (/ ok 2.0)
                :finding (when (< ok 2) "missing <html lang> or <meta charset> — hurts screen readers / encoding")}))}])

;; --- optional axes (isekai-only in the upstream forks) ------------------------

(def input-zoom-axis
  "Inputs ≥ 16px so iOS Safari doesn't zoom-on-focus. isekai-only upstream."
  {:id :input-zoom :title "Inputs ≥ 16px (no iOS focus-zoom)" :weight 0.09
   :check (fn [s]
            (let [inputs? (has? s #"(?i)<textarea|<input|contenteditable")
                  fonts   (field-font-sizes s)]
              (cond
                (not inputs?) {:score 1.0}
                (some #(< % 16) fonts)
                {:score 0.4 :finding (str "a text field uses <16px font ("
                                          (str/join "/" (sort (distinct fonts)))
                                          "px) — iOS zooms in on focus and breaks the layout")}
                :else {:score 1.0})))})

(def contrast-axis
  "WCAG 1.4.3 body-text contrast over muted (translucent near-black/near-white)
   text colours blended onto the detected page background. isekai-only upstream
   (the superproject fork listed it as a follow-up)."
  {:id :contrast :title "Text contrast ≥ 4.5:1 (WCAG 1.4.3)" :weight 0.10
   :check (fn [s]
            (let [bg (dominant-bg s)
                  ;; muted black/white text is the canonical failure; blend it over
                  ;; the bg and measure the real ratio. (Solid colours we can't
                  ;; pair to a bg are trusted.)
                  muted (->> (text-colors s)
                             (keep parse-color)
                             (filter muted-text?))
                  bad (->> muted
                           (map (fn [c] [c (contrast-ratio (blend c bg) bg)]))
                           (filter (fn [[_ r]] (< r 4.5))))]
              (cond
                (empty? muted) {:score 1.0}
                (empty? bad)   {:score 1.0}
                :else {:score (max 0.0 (- 1.0 (/ (count bad) (double (count muted)))))
                       :finding (str (count bad) " muted text colour(s) below 4.5:1 on the page bg (e.g. ratio "
                                     (round1 (second (first bad)))
                                     ":1) — body copy is hard to read (WCAG 1.4.3)")})))})

(def extra-axes
  "The optional axes, ready to splice: (audit pages {:extra-axes extra-axes})
   reproduces the full isekai 12-axis rubric."
  [input-zoom-axis contrast-axis])

;; --- resolution + scoring ------------------------------------------------------

(defn resolve-axes
  "Turn an opts map into the effective axis vector.
   {:axes v}            — replace the base set (default `default-axes`)
   {:extra-axes [a...]} — append axes (e.g. `extra-axes` for the isekai rubric)
   {:skip #{:id ...}}   — drop axes by id
   {:weights {:id w}}   — override per-axis weights"
  [{:keys [axes extra-axes skip weights]}]
  (let [skip (set skip)]
    (->> (concat (or axes default-axes) extra-axes)
         (remove #(contains? skip (:id %)))
         (mapv (fn [a] (if-some [w (get weights (:id a))] (assoc a :weight w) a))))))

(defn score-page
  "Score one page's source string against every axis → {:overall 0..100 :axes [...]}.
   `overall` is the weight-normalized mean (divide by Σweight, per isekai
   iteration-02's quality.rs fix). Optional `opts` — see `resolve-axes`."
  ([src] (score-page src nil))
  ([src opts]
   (let [axes (resolve-axes opts)
         total (reduce + 0.0 (map :weight axes))
         results (mapv (fn [{:keys [id title weight check]}]
                         (let [{:keys [score finding]} (check src)]
                           {:id id :title title :weight weight
                            :score (double score) :finding finding}))
                       axes)
         weighted (reduce + 0.0 (map (fn [a] (* (:score a) (:weight a))) results))]
     {:overall (if (pos? total) (* 100.0 (/ weighted total)) 0.0)
      :axes results})))

(defn audit
  "Audit many pages: `pages` is {page-name → source-string}. Returns
   {:overall mean
    :pages {name → page-report}
    :findings [{:axis :weight :pages [names] :finding :worst-score :headroom}]}.
   `findings` is the cross-page gap list, heaviest headroom first — the
   hypothesis seed list. Optional `opts` — see `resolve-axes`."
  ([pages] (audit pages nil))
  ([pages opts]
   (let [axes (resolve-axes opts)
         reports (into {} (map (fn [[k v]] [k (score-page v opts)]) pages))
         overall (if (empty? reports) 0.0
                     (/ (reduce + 0.0 (map :overall (vals reports))) (count reports)))
         findings (->> axes
                       (keep (fn [{:keys [id weight]}]
                               (let [hits (keep (fn [[pg rep]]
                                                  (let [a (first (filter #(= (:id %) id) (:axes rep)))]
                                                    (when (:finding a) [pg (:finding a) (:score a)])))
                                                reports)]
                                 (when (seq hits)
                                   {:axis id :weight weight
                                    :pages (mapv first hits)
                                    :finding (second (first hits))
                                    :worst-score (reduce min (map #(nth % 2) hits))
                                    ;; potential = how much weight-normalized score this axis can still gain
                                    :headroom (* weight (- (count hits) (reduce + (map #(nth % 2) hits))))}))))
                       (sort-by :headroom >)
                       vec)]
     {:overall overall :pages reports :findings findings})))
