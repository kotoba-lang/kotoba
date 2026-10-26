(ns browser.text-edit
  "Small text editing model for browser/OS surface text input.")

(defn empty-state
  []
  {:text/value ""
   :text/caret 0
   :text/selection [0 0]
   :text/composition nil})

(defn- clamp
  [n lo hi]
  (max lo (min hi (or n lo))))

(defn- code-unit-at
  [s idx]
  #?(:clj (int (.charAt ^String s idx))
     :cljs (.charCodeAt s idx)))

(defn- surrogate-pair-boundary?
  "True when position `p` in `value` sits strictly INSIDE a real UTF-16
   surrogate pair (e.g. most emoji, some rare CJK-B ideographs) -- i.e.
   `value`'s code unit immediately before `p` is a high surrogate
   (0xD800-0xDBFF) and the one at `p` is its low surrogate (0xDC00-0xDFFF).
   Every caret-moving/deleting position below is computed by raw code-unit
   arithmetic (`dec`/`inc`/`+delta`); without this check, landing exactly
   here corrupts the string into two lone, invalid surrogates -- confirmed
   via a real REPL reproduction before this fix: typing an emoji then
   pressing Backspace, Delete, or an arrow key that lands mid-pair all
   produced a value containing an unpaired surrogate code unit."
  [value p]
  (and (pos? p) (< p (count value))
       (<= 0xD800 (code-unit-at value (dec p)) 0xDBFF)
       (<= 0xDC00 (code-unit-at value p) 0xDFFF)))

(defn normalize-selection
  [state]
  (let [value (:text/value state "")
        n (count value)
        [a b] (or (:text/selection state) [(:text/caret state) (:text/caret state)])
        a (clamp a 0 n)
        b (clamp b 0 n)]
    (assoc state
           :text/caret (clamp (:text/caret state) 0 n)
           :text/selection [(min a b) (max a b)])))

(defn- snap-out-of-surrogate-pair
  "Snaps `p` backward, to just before the pair, whenever it sits strictly
   inside a real UTF-16 surrogate pair -- move-caret (arrow keys) already
   snaps its own computed position before ever reaching collapse/select,
   but collapse/select are ALSO called directly for a mouse click or
   drag-select (browser.surface/edit-text's :caret/:select ops, driven by
   browser.input's :text/caret/:text/selection events), which pass a raw,
   unsnapped position straight through -- previously with no check at
   all. Confirmed via direct REPL reproduction before this fix: clicking
   to place the caret strictly between an emoji's high/low surrogate,
   then pressing Backspace, corrupted the value into a lone, invalid
   surrogate code unit -- the identical corruption class move-caret's own
   surrogate-pair-boundary? check already guards against for arrow-key
   movement, just reachable through this different entry point."
  [value p]
  (if (surrogate-pair-boundary? value p) (dec p) p))

(defn collapse
  [state caret]
  (let [value (:text/value state "")
        caret (-> caret (clamp 0 (count value)) (->> (snap-out-of-surrogate-pair value)))]
    (assoc state :text/caret caret :text/selection [caret caret])))

(defn select
  [state start end]
  (let [value (:text/value state "")]
    (-> state
        (assoc :text/selection [(snap-out-of-surrogate-pair value start)
                                 (snap-out-of-surrogate-pair value end)]
               :text/caret (snap-out-of-surrogate-pair value end))
        (normalize-selection))))

(defn insert-text
  [state text]
  (let [state (normalize-selection state)
        value (:text/value state "")
        [start end] (:text/selection state)
        text (str text)
        value (str (subs value 0 start) text (subs value end))
        caret (+ start (count text))]
    (assoc state
           :text/value value
           :text/caret caret
           :text/selection [caret caret]
           :text/composition nil)))

(defn delete-backward
  [state]
  (let [state (normalize-selection state)
        value (:text/value state "")
        [start end] (:text/selection state)]
    (cond
      (< start end)
      (insert-text state "")

      (pos? start)
      (let [caret (if (surrogate-pair-boundary? value (dec start)) (- start 2) (dec start))]
        (assoc state
               :text/value (str (subs value 0 caret) (subs value start))
               :text/caret caret
               :text/selection [caret caret]))

      :else state)))

(defn delete-forward
  [state]
  (let [state (normalize-selection state)
        value (:text/value state "")
        [start end] (:text/selection state)]
    (cond
      (< start end)
      (insert-text state "")

      (< end (count value))
      (let [delete-end (if (surrogate-pair-boundary? value (inc end)) (+ end 2) (inc end))]
        (assoc state
               :text/value (str (subs value 0 start) (subs value delete-end))
               :text/caret start
               :text/selection [start start]))

      :else state)))

(defn- selection-anchor
  [state]
  (let [state (normalize-selection state)
        caret (:text/caret state)
        [start end] (:text/selection state)]
    (if (<= caret start) end start)))

(defn move-caret
  ([state delta]
   (move-caret state delta {}))
  ([state delta {:keys [extend?]}]
   (let [state (normalize-selection state)
         value (:text/value state "")
         [start end] (:text/selection state)
         caret (:text/caret state)
         next-caret (clamp (if (and (not extend?) (< start end))
                             (if (neg? delta) start end)
                             (+ caret delta))
                           0
                           (count value))
         next-caret (cond
                      (and (neg? delta) (surrogate-pair-boundary? value next-caret)) (dec next-caret)
                      (and (pos? delta) (surrogate-pair-boundary? value next-caret)) (inc next-caret)
                      :else next-caret)]
     (if extend?
       (select state (selection-anchor state) next-caret)
       (collapse state next-caret)))))

(defn move-to
  ([state caret]
   (move-to state caret {}))
  ([state caret {:keys [extend?]}]
   (let [state (normalize-selection state)
         caret (clamp caret 0 (count (:text/value state "")))]
     (if extend?
       (select state (selection-anchor state) caret)
       (collapse state caret)))))

(defn select-all
  [state]
  (select state 0 (count (:text/value state ""))))

(defn composition-start
  [state]
  (assoc state :text/composition {:composition/text ""}))

(defn composition-update
  [state text]
  (assoc state :text/composition {:composition/text (str text)}))

(defn composition-end
  [state text]
  (insert-text (assoc state :text/composition nil) text))
