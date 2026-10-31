(ns kami.mangaka.komawari
  "コマ割り (komawari / panel-division) design — proposes panel geometry
  (:panel/rect :panel/tilt :panel/polygon :panel/z :panel/bleed) for a page
  from an authored beat sequence.

  Encodes two classic manga composition techniques:

  1. Golden-ratio (φ≈1.618) proportional weighting instead of an even grid —
     a :large beat reads ~φ:1 against a :small one, so a page has a visual
     hierarchy rather than uniform boxes (`weight-of` / `beat-weight`).

  2. Force-line panel borders — when a row contains a :tension/:impact beat,
     the WHOLE ROW is sheared into parallelograms along that beat's
     :beat/vector (degrees), so the panel *frame* itself continues the
     action's diagonal across every gutter in the tier — not just the one
     panel, which would leave a wedge-shaped gap/overlap at its neighbors.
     Shearing every panel in the row by the same amount keeps every shared
     internal edge congruent (`row-tilt` / `shear-quad`).

  Both techniques are gated by a named `:style` (`styles`/`default-style`,
  ADR-2607051530): technique 2 above is the :toriyama preset. A :togashi
  preset instead keeps panels rectilinear (tilt off) and expresses dynamism
  through `:beat/inset` — a small reactive panel drawn overlapping the panel
  below it, panel-in-panel (`apply-inset`), tagged \"frame-break\" so the
  governor expects that specific overlap. ADR-2607172200 adds :araki
  (steeper shear caps + frame-break + `:beat/breakout` character bleed),
  :urasawa (rectilinear, subdued √φ weight table) and :inoue (rectilinear,
  character bleed, full-contrast φ table) — see the `styles` comment below
  for grounding.

  Pure/.cljc, no host interop — runs identically on the JVM, in SCI, and in
  a browser-side layout preview. Not the storage schema: callers merge the
  returned :panel/* keys onto their own panel maps (any other :panel/* key —
  :dialogue :visual :panel/id :panel/focal … — passes straight through)
  before persisting.

  Canonical home (ADR-2607141700): ported from `gftdcojp/ai-gftd-mangaka`'s
  `mangaka.layout.komawari` (ADR-2607051520/2607051530, where it was
  developed and proven against real Ghost Hacker Arc0-1 panels), landed here
  as the shared kotoba-lang package so `ai-gftd-mangaka`/`app-aozora` and any
  other `kami-mangaka-page` consumer (e.g. `kami-app-sip`) draw from one
  implementation instead of maintaining independent copies. `kami.mangaka.page`
  already carries a JVM/Java2D-specific tilt-only port (`komawari-tilt`,
  `row-tilt`, pixel-space `shear-polygon`) predating this file — that one
  stays as-is (it operates in Java2D pixel space on a different panel-map
  vocabulary, `:intensity`/`:vector` vs this namespace's `:beat/*`-prefixed
  beat vocabulary, and `kami-app-sip`'s `sip.page` facade depends on its
  existing `layout-page`/`template-for` API surface unchanged); this
  namespace is the fuller, normalized-space engine (proportional row/col
  band-splitting, named styles, panel-in-panel inset, the deterministic
  governor) that neither `page.clj`'s existing tilt-only port nor the old
  `template-for` grid templates implement.")

(def phi 1.618033988749895)

;; ────────────────────────────── artist styles ──────────────────────────────
;; Named geometry presets (ADR-2607051530; expanded by ADR-2607172200), each
;; grounded in reference material — full citations + honesty grading (what is
;; author-stated vs analyst consensus) live in ai-gftd-mangaka's
;; resources/komawari_styles.edn catalog.
;;
;; :toriyama — reference: DBZ panel-analysis stills. Dynamism lives in the
;;   PANEL FRAME: a tense/impact row is sheared into a parallelogram
;;   (`row-tilt`), reading as one continuous force-line across every panel in
;;   the tier. Panels stay edge-to-edge otherwise — no panel ever intrudes on
;;   its neighbor's territory.
;;
;; :togashi — reference: Hunter×Hunter 王位継承戦編 (冨樫義博). Panels stay
;;   RECTILINEAR even in tense exchanges (tilt disabled) — the dynamism
;;   instead lives in what's allowed to cross a panel's own border: a small
;;   reactive/gesture panel is drawn overlapping the larger panel beneath it
;;   (`:beat/inset`, tagged "frame-break" so the governor doesn't flag the
;;   deliberate overlap).
;;
;; :araki — reference: 『荒木飛呂彦の漫画術』 (page-turn discipline, every
;;   panel load-bearing — author-stated) + analyst consensus on JoJo's
;;   aggressive diagonal gutters, overlapping panels and figures breaking
;;   frames (NOT author-stated — the book's own 黄金比 is facial proportion,
;;   not panel weighting). Everything is allowed at once: steeper shear caps
;;   than :toriyama (45°/15° — a design choice bounding the observed
;;   steepness, not a sourced constant), frame-break insets AND character
;;   bleed-outs (`:beat/breakout`).
;;
;; :urasawa — reference: 浦沢直樹本人の言 (浦沢チャンネル「基本のキ」:
;;   見開き右上が要、コマ数は絞る; 小津安二郎サイトのインタビュー: 定点
;;   カメラの反復を自作に適用) + Benzilla layout analysis (水平バンド構造、
;;   ノド側に断ち切り無し). Panels stay rectilinear, no frame-break, no
;;   character bleed; size contrast is SUBDUED (√φ weight table — bands read
;;   as calm rhythm, the drama lives in repetition/page-turn, which are
;;   authoring-side devices, not geometry).
;;
;; :inoue — reference: SLAM DUNK 山王戦の無音シークエンス分析 (vol.31
;;   pp.91–154) + canmom panel/movement close-reading. Gutters stay
;;   rectilinear — the diagonal energy lives INSIDE the panel (action axis /
;;   speed lines), not in the frame — but figures cross panel borders
;;   (`:beat/breakout`) and size contrast is extreme (default φ table with
;;   splash = φ² for the frozen-moment payoff panels).
(def styles
  {:toriyama {:tilt-enabled? true  :frame-break? false}
   :togashi  {:tilt-enabled? false :frame-break? true}
   :araki    {:tilt-enabled? true  :frame-break? true :character-bleed? true
              :impact-tilt-max 45.0 :tension-tilt-max 15.0}
   :urasawa  {:tilt-enabled? false :frame-break? false
              :weight-of :subdued}
   :inoue    {:tilt-enabled? false :frame-break? false :character-bleed? true}})

(def default-style :toriyama)

(defn- style-opts [style] (get styles style (get styles default-style)))

;; ───────────────────────── proportional weighting ─────────────────────────

(def ^:private sqrt-phi (Math/sqrt phi))

(def ^:private weight-of
  {:splash (* phi phi) :large phi :medium 1.0 :small (/ 1.0 phi) :beat 1.0})

(def ^:private weight-tables
  "Named weight tables selectable per style via :weight-of. :default is the
  φ hierarchy; :subdued (√φ) keeps a visible large/small hierarchy at half
  the contrast — the :urasawa band-grid look."
  {:default weight-of
   :subdued {:splash phi :large sqrt-phi :medium 1.0
             :small (/ 1.0 sqrt-phi) :beat 1.0}})

(defn beat-weight
  "A beat's relative size weight: :beat/weight is either a size keyword
  (looked up in the weight table, unknown keywords default to 1.0) or a bare
  number (used as-is). Missing → :medium (weight 1.0, i.e. an even share).
  The 2-arity takes a named table key (:default/:subdued) or a table map —
  styles select theirs via the :weight-of style opt."
  ([beat] (beat-weight beat :default))
  ([beat table]
   (let [w (:beat/weight beat :medium)
         t (if (map? table) table (get weight-tables table weight-of))]
     (if (number? w) w (get t w 1.0)))))

(defn- style-weight-table [style]
  (get (style-opts style) :weight-of :default))

(defn- normalize [ws]
  (let [total (reduce + ws)]
    (if (pos? total) (mapv #(/ % total) ws) (mapv (constantly (/ 1.0 (max 1 (count ws)))) ws))))

;; ─────────────────────────────── geometry ──────────────────────────────────

(defn- row-bands
  "rows → [[y h] …], one band per row, stacked top-to-bottom. A row's height
  weight is its tallest beat's weight (a :large beat paired with two :small
  side panels still gets a tall tier — normal manga grammar), then row
  heights are φ-weight-normalized to fill the page net of gutters."
  [rows gutter table]
  (let [row-weights (mapv (fn [row] (apply max 1.0 (map #(beat-weight % table) row))) rows)
        n (count rows)
        usable (max 0.0 (- 1.0 (* gutter (max 0 (dec n)))))
        hs (mapv #(* usable %) (normalize row-weights))]
    (loop [hs hs y 0.0 acc []]
      (if (empty? hs)
        acc
        (recur (rest hs) (+ y (first hs) gutter) (conj acc [y (first hs)]))))))

(defn- col-bands
  "A single row of beats → [[x w] …] in READING order (manga right-to-left:
  the first beat in `row` renders rightmost, i.e. highest x)."
  [row gutter table]
  (let [n (count row)
        usable (max 0.0 (- 1.0 (* gutter (max 0 (dec n)))))
        ws (mapv #(* usable %) (normalize (mapv #(beat-weight % table) row)))]
    (loop [ws ws x 1.0 acc []]
      (if (empty? ws)
        acc
        (let [w (first ws) x0 (- x w)]
          (recur (rest ws) (- x0 gutter) (conj acc [x0 w])))))))

;; ─────────────────────────── force-line tilt ───────────────────────────────

(def ^:private radians->degrees
  "Math/toDegrees is JVM-only (no JS Math.toDegrees) -- this namespace must
  stay portable to cljs/nbb, so multiply by the constant instead."
  (/ 180.0 Math/PI))
(def ^:private degrees->radians (/ Math/PI 180.0))

(def ^:private impact-tilt-max
  "The steepest a panel border is allowed to read: the diagonal angle of a
  1:φ rectangle itself (~31.7°) — the same golden-ratio geometry driving the
  proportional weighting above, rather than an arbitrary degree count."
  (* (Math/atan (/ 1.0 phi)) radians->degrees))
(def ^:private tension-tilt-max 10.0)

(defn- clamp [v lo hi] (max lo (min hi v)))

(defn tilt-for
  "An action-line angle (any degrees, e.g. a punch/slash direction measured
  off vertical) + intensity → a signed horizontal-shear angle within this
  intensity's readability bound. :calm never tilts (nil). The 3-arity takes
  a caps map ({:impact-tilt-max :tension-tilt-max}, e.g. a `styles` entry)
  so a style may bound the shear differently (:araki reads steeper than the
  default φ-diagonal bound)."
  ([vector-deg intensity] (tilt-for vector-deg intensity nil))
  ([vector-deg intensity caps]
   (when (and vector-deg (not= intensity :calm))
     (let [max-t (if (= intensity :impact)
                   (get caps :impact-tilt-max impact-tilt-max)
                   (get caps :tension-tilt-max tension-tilt-max))
           folded (- (mod (+ vector-deg 90) 180) 90)]
       (double (clamp folded (- max-t) max-t))))))

(defn row-tilt
  "The single shared tilt for a row: the :impact beat's tilt if any beat in
  the row is :impact, else the first :tension beat's, else nil (calm row,
  stays axis-aligned). `style` (a key into `styles`, default :toriyama) gates
  this entirely: a style with :tilt-enabled? false (e.g. :togashi/:urasawa/
  :inoue) always returns nil, regardless of any beat's intensity/vector, and
  a style's own tilt caps bound the result (:araki)."
  ([row] (row-tilt row default-style))
  ([row style]
   (let [opts (style-opts style)]
     (when (:tilt-enabled? opts)
       (let [pick (or (first (filter #(= :impact (:beat/intensity %)) row))
                      (first (filter #(= :tension (:beat/intensity %)) row)))]
         (when pick (tilt-for (:beat/vector pick) (:beat/intensity pick) opts)))))))

;; ─────────────────────── panel-in-panel frame-break ────────────────────────

(defn- inset-opts [v]
  (merge {:scale 0.5 :overlap 0.15} (when (map? v) v)))

(defn apply-inset
  "[x y w h] + inset opts → a smaller rect anchored to the trailing (reading-
  first) edge of the cell, whose height grows by `:overlap` × h beyond the
  row's own band — deliberately overlapping the row below."
  [[x y w h] opts]
  (let [{:keys [scale overlap]} (inset-opts opts)
        w2 (* w scale)
        x2 (+ x (- w w2))]
    [x2 y w2 (* h (+ 1.0 overlap))]))

(defn- shear-quad
  "[x y w h] + a row-shared tilt (degrees) → a parallelogram (4 [x y] corners)
  shifting the TOP edge by dx = h·tan(tilt) while the bottom edge stays put.
  Every panel in a row shares the same h and tilt, so adjoining internal
  gutters stay congruent — no gaps or overlaps between neighbors."
  [[x y w h] tilt-deg]
  (let [dx (* h (Math/tan (* tilt-deg degrees->radians)))]
    [[(+ x dx) y] [(+ x w dx) y] [(+ x w) (+ y h)] [x (+ y h)]]))

;; ──────────────────────────────── propose ──────────────────────────────────

(defn propose-page-layout
  "rows: a vector of rows, each row a vector of beats in READING order
  (right-to-left — the first beat in a row renders rightmost, matching
  manga page-turn direction). A beat is any map; keys consumed as layout
  hints and stripped from the output: :beat/weight, :beat/intensity,
  :beat/vector, :beat/inset. Everything else on the beat passes straight
  through onto the returned panel map, alongside the computed :panel/rect
  (always) and :panel/tilt/:panel/polygon/:panel/z/:panel/bleed (only when
  applicable). `opts` also takes :gutter (default 0.012) and :style (a key
  into `styles`, default :toriyama). A truthy :beat/breakout marks the
  drawn figure as crossing its own panel border (character bleed) — honored
  only under a :character-bleed? style (:araki/:inoue), where it tags the
  panel \"character-bleed\", sets :panel/bleed and raises :panel/z; other
  styles strip it silently, like :beat/inset under a non-frame-break style.
  Returns a flat vector of panels in reading order (row-major, RTL within a
  row)."
  ([rows] (propose-page-layout rows {}))
  ([rows {:keys [gutter style] :or {gutter 0.012 style default-style}}]
   (let [table (style-weight-table style)]
     (vec
      (mapcat
       (fn [row [y h]]
         (let [tilt (row-tilt row style)
               ;; The row's shear inherits the intensity of the beat that set
               ;; it (row-tilt picks :impact first) — every panel in the row
               ;; is tagged with it so the governor caps the SHARED tilt by
               ;; the row's own intensity, not each neighbor's missing tag.
               shear-tag (when tilt
                           (if (some #(= :impact (:beat/intensity %)) row)
                             "sheared-impact" "sheared-tension"))
               frame-break-ok? (:frame-break? (style-opts style))
               bleed-ok? (:character-bleed? (style-opts style))]
           (map (fn [beat [x w]]
                  (let [base-rect [x y w h]
                        inset? (and frame-break-ok? (some? (:beat/inset beat)))
                        breakout? (and bleed-ok? (:beat/breakout beat))
                        rect (if inset? (apply-inset base-rect (:beat/inset beat)) base-rect)]
                    (-> beat
                        (dissoc :beat/weight :beat/intensity :beat/vector :beat/inset :beat/breakout)
                        (assoc :panel/rect rect)
                        (cond->
                         tilt (-> (assoc :panel/tilt tilt :panel/polygon (shear-quad rect tilt))
                                  (assoc :panel/bleed true)
                                  (update :panel/tags (fnil conj []) shear-tag))
                         (= :impact (:beat/intensity beat)) (-> (assoc :panel/z 2)
                                                                 (update :panel/tags (fnil conj []) "impact"))
                         (= :splash (:beat/weight beat)) (assoc :panel/bleed true)
                         breakout? (-> (assoc :panel/bleed true :panel/z 3)
                                       (update :panel/tags (fnil conj []) "character-bleed"))
                         inset? (-> (assoc :panel/bleed true :panel/z 5)
                                    (update :panel/tags (fnil conj []) "frame-break"))))))
                row (col-bands row gutter table))))
       rows (row-bands rows gutter table))))))

;; ──────────────────────────────── governor ─────────────────────────────────
;; Deterministic, no-LLM QA over ANY panel vector (not just this ns's own
;; output — a hand-authored :panel/tilt/:panel/polygon goes through the same
;; checks).

(defn- corners
  "Panel `i`'s 4 corners (clockwise from top-left): its :panel/polygon when
  present, else the axis-aligned rect's corners."
  [i panel]
  (or (:panel/polygon panel)
      (let [[x y w h] (:panel/rect panel [0.04 (min 0.95 (+ 0.02 (* i 0.24))) 0.92 0.22])]
        [[x y] [(+ x w) y] [(+ x w) (+ y h)] [x (+ y h)]])))

(defn- bbox [pts]
  (let [xs (map first pts) ys (map second pts)]
    [(apply min xs) (apply min ys) (apply max xs) (apply max ys)]))

(defn- bbox-overlap-area [[ax0 ay0 ax1 ay1] [bx0 by0 bx1 by1]]
  (let [ox (max 0.0 (- (min ax1 bx1) (max ax0 bx0)))
        oy (max 0.0 (- (min ay1 by1) (max ay0 by0)))]
    (* ox oy)))

(def ^:private overlap-tolerance
  "Bbox-overlap area allowed before flagging :panel-overlap — small enough
  to admit a force-line shear's own diagonal overhang, not a real collision."
  0.015)

(defn- round3 [n] (/ (Math/round (* (double n) 1000.0)) 1000.0))

(defn validate-layout
  "panels → {:ok? :issues [{:code :severity :panel :message}] :count}.
  Checks: (a) every corner within the page ([-0.0001,1.0001] normally;
  :panel/bleed panels get [-0.4,1.4]), (b) no two panels' bounding boxes
  overlap beyond `overlap-tolerance`, UNLESS either carries :panel/tags
  \"frame-break\", (c) |:panel/tilt| within its intensity's bound, (d) reading
  order — within a same-y-band run, x must strictly decrease (RTL) as
  :panel/index increases. The 2-arity takes {:style k}: tilt bounds then
  come from that style's own caps (an :araki 45° impact shear passes under
  {:style :araki} but still fails the default φ bound).

  Sheared rows: a force-line row shares ONE tilt across every panel
  (`row-tilt`), so its non-impact members carry the impact-level tilt too —
  they are tagged \"sheared-impact\"/\"sheared-tension\" by the generator and
  capped by the ROW's intensity. Two same-row sheared panels' bounding boxes
  also overlap by construction (a parallelogram's bbox spills over the
  gutter) even though the polygons never do, so that specific pair (both
  sheared, equal tilt, same y-band) is exempt from the overlap check."
  ([panels] (validate-layout panels {}))
  ([panels {:keys [style]}]
  (let [panels (vec panels)
        caps (when style (style-opts style))
        bboxes (mapv bbox (map-indexed corners panels))
        bleed? (fn [p] (true? (:panel/bleed p)))
        frame-break? (fn [p] (boolean (some #{"frame-break" :frame-break} (:panel/tags p))))
        sheared? (fn [p] (boolean (some #{"sheared-impact" "sheared-tension"} (:panel/tags p))))
        same-shear-row? (fn [i j]
                          (and (sheared? (nth panels i)) (sheared? (nth panels j))
                               (= (:panel/tilt (nth panels i)) (:panel/tilt (nth panels j)))
                               (< (Math/abs (- (nth (nth bboxes i) 1) (nth (nth bboxes j) 1))) 0.02)))
        bounds-issues
        (->> (map vector (range) panels bboxes)
             (keep (fn [[i p [x0 y0 x1 y1]]]
                     (let [lo (if (bleed? p) -0.4 -0.0001) hi (if (bleed? p) 1.4 1.0001)]
                       (when (or (< x0 lo) (< y0 lo) (> x1 hi) (> y1 hi))
                         {:code :panel-out-of-bounds :severity :error :panel i
                          :message (str "panel " i " runs outside the page: " [x0 y0 x1 y1])})))))
        overlap-issues
        (for [i (range (count panels)) j (range (inc i) (count panels))
              :let [area (bbox-overlap-area (nth bboxes i) (nth bboxes j))]
              :when (and (> area overlap-tolerance)
                         (not (frame-break? (nth panels i)))
                         (not (frame-break? (nth panels j)))
                         (not (same-shear-row? i j)))]
          {:code :panel-overlap :severity :error :panel i
           :message (str "panel " i " overlaps panel " j " (bbox area " (round3 area) ")")})
        tilt-issues
        (->> (map vector (range) panels)
             (keep (fn [[i p]]
                     (when-let [tilt (:panel/tilt p)]
                       (let [impact? (boolean (some #{"impact" :impact "sheared-impact"} (:panel/tags p)))
                             cap (if impact?
                                   (get caps :impact-tilt-max impact-tilt-max)
                                   (get caps :tension-tilt-max tension-tilt-max))]
                         (when (> (Math/abs (double tilt)) cap)
                           {:code :tilt-out-of-bounds :severity :error :panel i
                            :message (str "panel " i " tilt " tilt "° exceeds "
                                          (if impact? "impact" "non-impact") " bound ±" cap "°")}))))))
        order-issues
        (loop [i 1 acc []]
          (if (>= i (count panels))
            acc
            (let [[prev-x0 py0 _ _] (nth bboxes (dec i))
                  [x0 y0 _ _] (nth bboxes i)
                  same-row? (< (Math/abs (- y0 py0)) 0.02)]
              (recur (inc i)
                     (if (and same-row? (>= x0 prev-x0))
                       (conj acc {:code :reading-order :severity :warn :panel i
                                  :message (str "panel " i " does not sit left of panel " (dec i)
                                                " within its row (expected right-to-left reading order)")})
                       acc)))))
        issues (vec (concat bounds-issues overlap-issues tilt-issues order-issues))
        by-sev (frequencies (map :severity issues))]
    {:ok? (zero? (:error by-sev 0))
     :issues issues
     :count (count issues)
     :errors (:error by-sev 0)
     :warnings (:warn by-sev 0)})))
