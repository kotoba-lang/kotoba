(ns devtools
  "KAMI Devtools — automation and inspection contracts for KAMI
  runtimes. Does not capture screenshots or click real UI itself;
  defines semantic element snapshots, automation plans/steps, synthetic
  input generation, screenshot artifact metadata, and a UI/UX
  accessibility evaluator. Host runtimes (e.g. `kami-web`) implement
  actual screenshot capture and event injection using these shared
  contracts. Restored from the legacy kami-engine/kami-devtools Rust
  crate (deleted in kotoba-lang/kami-engine PR #82 'Remove Rust
  workspace from kami-engine') as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  `InputEvent`/`Device` values are plain `:type`-tagged maps, duck-typed
  to match `kotoba-lang/input`'s documented shapes (that namespace
  defines the domain interpreter but not event constructors, so this
  namespace constructs them directly rather than adding a hard
  dependency).

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU."
  (:require [kotoba.lang.text :as str]))

(def semantic-roles #{:button :panel :meter :text :canvas :node :list-item :input :toggle :unknown})

(defn rect [x y width height] {:x x :y y :width width :height height})

(defn rect-center [r] [(+ (:x r) (* (:width r) 0.5)) (+ (:y r) (* (:height r) 0.5))])

(defn rect-contains? [r x y]
  (and (>= x (:x r)) (<= x (+ (:x r) (:width r)))
       (>= y (:y r)) (<= y (+ (:y r) (:height r)))))

(defn element-snapshot
  [{:keys [id role rect visible enabled text tags]}]
  {:id id :role role :rect rect :visible visible :enabled enabled :text text :tags (vec tags)})

(defn scene-snapshot [width height elements] {:width width :height height :elements (vec elements)})

(defn find-by-id [scene id] (some (fn [e] (when (= (:id e) id) e)) (:elements scene)))
(defn find-by-tag [scene tag] (some (fn [e] (when (some #(= % tag) (:tags e)) e)) (:elements scene)))

(defn hit-test
  "Topmost visible+enabled element containing `(x,y)`."
  [scene x y]
  (some (fn [e] (when (and (:visible e) (:enabled e) (rect-contains? (:rect e) x y)) e))
        (reverse (:elements scene))))

;; TargetRef: `[:element-id id]` / `[:tag tag]` / `[:position x y]`

(def screenshot-formats #{:png :raw-rgba})

(defn screenshot-artifact
  [{:keys [id width height format path tags]}]
  {:id id :width width :height height :format format :path path :tags (vec tags)})

;; AutomationStep: `:type`-tagged map, one of
;;   {:type :wait-for-element :target ... :timeout-ms ...}
;;   {:type :click :target ...} {:type :double-click :target ...}
;;   {:type :move-pointer :target ...} {:type :key-press :code ...}
;;   {:type :screenshot :name ... :tags [...]}
;;   {:type :assert-text-contains :target ... :needle ...}

(defn automation-plan [id steps] {:id id :steps (vec steps)})

(defn automation-log-entry [step-index status detail] {:step-index step-index :status status :detail detail})

(defn automation-transcript
  ([plan-id] (automation-transcript plan-id [] []))
  ([plan-id logs screenshots] {:plan-id plan-id :logs (vec logs) :screenshots (vec screenshots)}))

(defn log
  "Append a log entry to `transcript`. Returns the updated transcript."
  [transcript step-index status detail]
  (update transcript :logs conj (automation-log-entry step-index status detail)))

(def uiux-severities #{:critical :high :medium :low})

(defn render-capabilities
  []
  {:text-visible true :keyboard-navigation true :focus-ring-visible true
   :hover-feedback true :responsive-layout true :semantic-lists true})

(defn uiux-finding [severity rule-id message element-id]
  {:severity severity :rule-id rule-id :message message :element-id element-id})

(defn uiux-report [score usable findings] {:score score :usable usable :findings (vec findings)})

(defn has-blockers? [report] (boolean (some #(#{:critical :high} (:severity %)) (:findings report))))

(defn resolve-target
  "Resolve `target` (`[:element-id id]` / `[:tag tag]` / `[:position x
  y]`) against `scene`."
  [scene target]
  (case (first target)
    :element-id (find-by-id scene (second target))
    :tag (find-by-tag scene (second target))
    :position (hit-test scene (nth target 1) (nth target 2))))

(defn click-events-for-target
  "Synthetic pointer-move/down/up event sequence for `target`, or nil if
  unresolvable."
  [scene target]
  (let [[cx cy] (if (= (first target) :position)
                  [(nth target 1) (nth target 2)]
                  (when-let [el (resolve-target scene target)] (rect-center (:rect el))))]
    (when cx
      [{:type :pointer-move :x cx :y cy :dx 0.0 :dy 0.0 :device :mouse :stylus nil}
       {:type :pointer-down :x cx :y cy :button 0 :device :mouse :stylus nil}
       {:type :pointer-up :x cx :y cy :button 0 :device :mouse :stylus nil}])))

(defn keypress-events
  "Synthetic key-down/key-up event pair for `code`."
  [code]
  [{:type :key-down :code code :device :keyboard}
   {:type :key-up :code code :device :keyboard}])

(defn sample-diskcleaner-plan
  []
  (automation-plan
   "diskcleaner-smoke"
   [{:type :wait-for-element :target [:tag "hero"] :timeout-ms 5000}
    {:type :screenshot :name "boot" :tags ["initial"]}
    {:type :click :target [:element-id "scan-now"]}
    {:type :screenshot :name "after-click" :tags ["interaction"]}]))

(defn- rect-center-distance [a b]
  (let [[ax ay] (rect-center a) [bx by] (rect-center b)]
    (Math/sqrt (+ (Math/pow (- ax bx) 2) (Math/pow (- ay by) 2)))))

(defn- rect-overlap-ratio [a b]
  (let [left (max (:x a) (:x b)) top (max (:y a) (:y b))
        right (min (+ (:x a) (:width a)) (+ (:x b) (:width b)))
        bottom (min (+ (:y a) (:height a)) (+ (:y b) (:height b)))]
    (if (or (<= right left) (<= bottom top))
      0.0
      (let [overlap (* (- right left) (- bottom top))
            base (max 1.0 (min (* (:width a) (:height a)) (* (:width b) (:height b))))]
        (/ overlap base)))))

(defn evaluate-uiux
  "Evaluate `scene` against runtime `caps` (render capabilities),
  producing a `UiUxReport` with findings and a 0-100 usability score."
  [scene caps]
  (let [text-elements (filter #(and (= (:role %) :text) (:visible %)) (:elements scene))
        text-semantics-count (count (filter #(and (:visible %) (not (str/blank? (:text %)))) (:elements scene)))
        interactive (filter #(and (:visible %) (:enabled %)
                                   (#{:button :input :toggle :list-item} (:role %)))
                             (:elements scene))
        findings
        (cond-> []
          (and (not (:text-visible caps)) (pos? text-semantics-count))
          (conj (uiux-finding :critical "text.not-rendered"
                               "scene contains text semantics, but the renderer cannot display text" nil)))

        findings
        (into findings
              (mapcat
               (fn [el]
                 (let [small (or (< (:width (:rect el)) 44.0) (< (:height (:rect el)) 44.0))
                       has-own-text (not (str/blank? (:text el)))
                       has-embedded-label (some (fn [t] (and (< (rect-center-distance (:rect t) (:rect el)) 120.0)
                                                              (> (rect-overlap-ratio (:rect t) (:rect el)) 0.15)))
                                                 text-elements)]
                   (cond-> []
                     small (conj (uiux-finding :high "target.too-small"
                                                (str "interactive target is smaller than 44x44 px ("
                                                     (:width (:rect el)) "x" (:height (:rect el)) ")")
                                                (:id el)))
                     (and (not has-own-text) (not has-embedded-label))
                     (conj (uiux-finding :high "control.unlabeled"
                                          "interactive control has no visible or semantic label" (:id el))))))
               interactive))

        findings (cond-> findings
                   (and (seq interactive) (not (:keyboard-navigation caps)))
                   (conj (uiux-finding :high "input.keyboard-nav-missing"
                                        "interactive UI is present, but keyboard navigation is not supported" nil))

                   (and (seq interactive) (not (:focus-ring-visible caps)))
                   (conj (uiux-finding :medium "focus.not-visible"
                                        "interactive UI is present, but focus indication is not visible" nil))

                   (and (seq interactive) (not (:hover-feedback caps)))
                   (conj (uiux-finding :medium "hover.no-feedback"
                                        "interactive UI is present, but hover feedback is missing" nil))

                   (and (>= (:width scene) 900) (not (:responsive-layout caps)))
                   (conj (uiux-finding :medium "layout.not-responsive"
                                        "layout is fixed-size and does not expose responsive behavior" nil)))

        max-right (reduce max 0.0 (map (fn [e] (+ (:x (:rect e)) (:width (:rect e)))) (:elements scene)))
        findings (if (> max-right (:width scene))
                   (conj findings (uiux-finding :high "layout.overflow-x"
                                                 (str "scene content overflows horizontally by "
                                                      #?(:clj (format "%.1f" (double (- max-right (:width scene))))
                                                         :cljs (.toFixed (double (- max-right (:width scene))) 1))
                                                      "px")
                                                 nil))
                   findings)

        score (reduce (fn [s f] (- s (case (:severity f) :critical 35 :high 20 :medium 10 :low 4)))
                       100 findings)
        score (max 0 (min 100 score))
        usable (and (>= score 70) (not (some #(= (:severity %) :critical) findings)))]
    (uiux-report score usable findings)))
