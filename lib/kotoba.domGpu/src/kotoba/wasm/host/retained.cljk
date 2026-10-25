(ns kotoba.wasm.host.retained
  "Shared retained-tree host utilities for kotoba:dom renderers.
   WebGL, WebGPU, and native hosts should share this state transition layer so
   ABI semantics are tested once and renderer backends only handle drawing."
  (:require [cssom.layout :as layout]))

(def base-state
  {:nodes {}
   :listeners {}
   :events []
   :draw-ops []})

(defn- normalize-event-name [x]
  (keyword x))

(defn apply-op [state op]
  (case (:op op)
    :create-element
    (assoc-in state [:nodes (:id op)] {:node/id (:id op)
                                       :node/type :element
                                       :tag (keyword (:tag op))
                                       :attrs {}
                                       :children []})

    :create-text
    (assoc-in state [:nodes (:id op)] {:node/id (:id op)
                                       :node/type :text
                                       :text (:text op)})

    ;; A comment is retained so the tree stays a faithful mirror of the
    ;; guest's DOM (a later mutation can reference its id), and skipped by
    ;; node-tree, which is the layout view -- same split as
    ;; kotoba.wasm.dom's `tree` vs `comment-tree`.
    ;; template content: retained so the host mirrors the guest's DOM, and
    ;; skipped by node-tree, which is the LAYOUT view -- template content is
    ;; explicitly not rendered. Same split as :comment.
    :append-content
    (update-in state [:nodes (:parent op) :content] (fnil conj []) (:child op))

    :create-comment
    (assoc-in state [:nodes (:id op)] {:node/id (:id op)
                                       :node/type :comment
                                       :text (:text op)})

    :set-root
    (assoc state :root (:id op))

    :set-attr
    (assoc-in state [:nodes (:id op) :attrs (if-let [ns (:namespace op)]
                                               (keyword ns (:name op))
                                               (keyword (:name op)))]
              (:value op))

    ;; Sibling gap to :set-attr above: previously entirely unhandled here
    ;; (falling through to the default `state` below, a silent no-op) --
    ;; a real removeAttribute()/boolean-attribute-off setter never reached
    ;; this state layer at all before, since no op was ever emitted for
    ;; it in the first place. Without this case, the retained tree this
    ;; namespace's own draw-ops/renderers actually paint from would keep
    ;; a removed attribute stale forever.
    :remove-attr
    (update-in state [:nodes (:id op) :attrs] dissoc (if-let [ns (:namespace op)]
                                                        (keyword ns (:name op))
                                                        (keyword (:name op))))

    :append-child
    (update-in state [:nodes (:parent op) :children] (fnil conj []) (:child op))

    :remove-children
    (assoc-in state [:nodes (:id op) :children] [])

    :remove-child
    (update-in state [:nodes (:parent op) :children]
              (fn [children] (vec (remove #{(:child op)} (or children [])))))

    :insert-before
    (update-in state [:nodes (:parent op) :children]
              (fn [children]
                (let [children (vec (or children []))
                      before (:before op)]
                  (if (and before (some #{before} children))
                    (let [[pre post] (split-with #(not= before %) children)]
                      (vec (concat pre [(:child op)] post)))
                    (conj children (:child op))))))

    :add-event-listener
    ;; Real HTML5 addEventListener supports MULTIPLE independent listeners
    ;; for the same (element, event-type) pair -- e.g. a framework and
    ;; user code each attaching their own click handler to the same
    ;; button -- so this keeps an ORDERED collection of handler-ids per
    ;; (node-id, event-name), not a single scalar. Previously a plain
    ;; assoc-in here silently overwrote any prior handler-id for the same
    ;; node+event-type, confirmed via direct REPL reproduction: a second
    ;; add-event-listener op on the same (node, :click) dropped the
    ;; first handler's registration entirely, only the most-recently-
    ;; added one ever matched in hit-test/listener-event below. Mirrors
    ;; kotoba.wasm.dom/add-event-listener's own, already-correct model
    ;; (this retained-tree host layer never got the same fix when that
    ;; one was made) -- adding the exact same handler-id twice is a
    ;; no-op (idempotent), matching real addEventListener semantics for
    ;; a duplicate registration.
    (update-in state [:listeners (:id op) (normalize-event-name (:name op))]
               (fn [ids]
                 (let [ids (or ids [])]
                   (if (some #{(:handler op)} ids) ids (conj ids (:handler op))))))

    :remove-event-listener
    ;; Previously entirely unhandled here (falling through to the default
    ;; `state` below, a silent no-op) -- kotoba.wasm.abi's own encode/
    ;; validate-batch had no case for this op at all either (a real crash,
    ;; "Unknown kotoba DOM op", confirmed via direct REPL reproduction),
    ;; so no real removeEventListener() call had ever reached this far
    ;; before. Without this case, :listeners stayed stale after a real
    ;; removal -- a node's own node-tree projection (and this session's
    ;; own draw-ops :listeners field) would keep reporting a listener
    ;; that real dispatch logic elsewhere had already stopped calling.
    ;;
    ;; Once :add-event-listener above started keeping an ORDERED
    ;; collection of handler-ids (not a scalar), this case's own plain
    ;; `dissoc` of the whole event-type entry became a second, related
    ;; bug: it ignored WHICH handler-id was actually being removed and
    ;; wiped every listener registered for that (node, event-type) pair
    ;; -- confirmed via direct REPL reproduction: removing one of two
    ;; click listeners on the same node dropped BOTH. Mirrors
    ;; kotoba.wasm.dom/remove-event-listener's own, already-correct
    ;; model: remove only the matching handler-id, leaving every other
    ;; listener for that same (element, event-type) pair untouched.
    (let [event-name (normalize-event-name (:name op))
          handler (:handler op)
          remaining (vec (remove #{handler} (get-in state [:listeners (:id op) event-name])))]
      (update-in state [:listeners (:id op)]
                 (fn [by-type]
                   (if (seq remaining)
                     (assoc by-type event-name remaining)
                     (dissoc by-type event-name)))))

    ;; Sibling gap to :remove-event-listener above: kotoba.wasm.abi had no
    ;; case for these four ops either (a real crash, fixed alongside this),
    ;; and this state layer never applied them -- confirmed via direct
    ;; REPL reproduction before touching source.
    :set-text
    (assoc-in state [:nodes (:id op) :text] (:text op))

    :create-fragment
    (assoc-in state [:nodes (:id op)] {:node/id (:id op)
                                       :node/type :document-fragment
                                       :children []})

    :focus
    (assoc state :focus (:id op))

    :blur
    ;; Real HTMLElement.blur() only clears focus when the blurring
    ;; element IS the currently-focused one -- blurring some OTHER,
    ;; not-currently-focused element must not steal focus away from a
    ;; genuinely different, already-focused element.
    (if (= (:focus state) (:id op)) (dissoc state :focus) state)

    state))

(defn node-tree [state id]
  (let [node (get-in state [:nodes id])]
    (case (:node/type node)
      :text (:text node)
      :comment nil
      :element (assoc node
                      :listeners (keys (get-in state [:listeners id]))
                      :children (into [] (comp (map #(node-tree state %)) (remove nil?))
                                      (:children node)))
      node)))

(defn draw-ops
  "Projects `state`'s retained node tree to a flat draw-ops vector (see
   cssom.layout/draw-ops). `measure-text` is an OPTIONAL real
   text-width function (`(fn [text font-size font-weight font-style]
   width-in-px)`) -- e.g. one
   backed by a real browser's `CanvasRenderingContext2D.measureText`,
   which the WebGL/WebGPU hosts already hold as `text-ctx` at the exact
   point they call this fn (see kotoba.wasm.host.webgl/webgpu's render!)
   -- passed straight through to cssom.layout/draw-ops' own optional
   `:measure-text` theme key, so this engine's word-wrap decisions can
   agree with how a real host will actually paint the already-wrapped
   text instead of cssom.layout's built-in per-character approximation.
   Omitting it (every caller before this arg existed, and every host
   without a real measurement function available) leaves cssom.layout's
   default char-w-approximation wrap behavior completely unaffected."
  ([state] (draw-ops state nil))
  ([state text-fns]
   ;; `text-fns` is either the legacy bare measure-text FN, or a map of
   ;; the host's text capabilities:
   ;;
   ;;   {:measure-text  (fn [text font-size weight style family] px)
   ;;    :font-metrics  (fn [font-size weight style family]
   ;;                     {:ascent px :descent px :x-height px})
   ;;    :avg-advance   (fn [font-size weight style family] px)
   ;;    :max-advance   (fn [font-size weight style family] px)}
   ;;
   ;; cssom.layout gained `:font-metrics` -- a font's real ascent and
   ;; descent, which is what a line box is genuinely built from -- but
   ;; until a HOST supplies it the engine falls back to its documented
   ;; 1.2em approximation. These hosts already hold a real Canvas 2D
   ;; context at this exact point (it is where measure-text comes from),
   ;; so the vertical half costs nothing more than the horizontal half
   ;; already did, and leaving it unsupplied would have kept the model
   ;; dormant in the only place that actually paints.
   ;;
   ;; `:avg-advance`/`:max-advance` joined them on 2026-08-05 and are the
   ;; same story one layer down: a FORM CONTROL's intrinsic width is
   ;; `size` (or `cols`) of the font's AVERAGE advance plus, for an
   ;; `<input>`, one glyph's worth of slack -- neither of which any
   ;; string measurement produces. cssom.layout's fallback when no host
   ;; answers is the `0` glyph, which is 6% too wide in the UA control
   ;; face, so a host that holds a canvas and does not supply these is
   ;; choosing a measurably worse answer. See avg-advance-fn /
   ;; max-advance-fn in the WebGL and WebGPU hosts for the measured laws.
   (let [{:keys [measure-text font-metrics avg-advance max-advance theme]}
         (if (map? text-fns) text-fns {:measure-text text-fns})
         tree (when-let [root (:root state)]
                (node-tree state root))
         ;; `:theme` is the host's own theme -- colours, font size, default
         ;; padding -- merged UNDER the text hooks so a host can never
         ;; accidentally drop them by supplying a theme.
         ;;
         ;; It exists because cssom.layout/default-theme is a DARK
         ;; application-chrome theme (`#e6ebf5` on `#121724`), inherited
         ;; from wasm-ui where this engine painted app UI. A host that
         ;; paints WEB PAGES needs to say so: a page that sets its own
         ;; light background -- most of the web -- otherwise gets near-white
         ;; text on it. Measured in kotoba-lang/browser: its visual smoke
         ;; page painted an <h1> in #e6ebf5 on the page's own #ffffff, and
         ;; had done for as long as the smoke existed, because this
         ;; function had no way to be told otherwise and the browser's own
         ;; page theme could not reach the only code that paints.
         theme (cond-> (or theme {})
                 measure-text (assoc :measure-text measure-text)
                 font-metrics (assoc :font-metrics font-metrics)
                 avg-advance (assoc :avg-advance avg-advance)
                 max-advance (assoc :max-advance max-advance))]
     (layout/draw-ops tree (cond-> {:width (:width state)}
                             (seq theme) (assoc :theme theme))))))

(defn with-draw-ops
  ([state] (with-draw-ops state nil))
  ([state text-fns]
   (assoc state :draw-ops (draw-ops state text-fns))))

(defn content-height
  "The max Y-extent any draw op in `ops` reaches, for auto-sizing a host's
   canvas to the actual laid-out content instead of relying solely on a
   hand-maintained :height literal in host state -- see
   kotoba.wasm.host.webgl/render!'s own docstring history for the bug this
   guards against (a stale :height literal silently clipping a page's real
   content, confirmed via git history that a fix to a DIFFERENT, duplicated
   source of truth left the host-state literal render! actually reads
   untouched). Shared here (rather than duplicated per-backend) so BOTH
   webgl.cljs and webgpu.cljs auto-grow identically and so this pure
   computation is testable on the JVM without a live GL/GPU context.

   Reads :y/:h off every op that carries them (:rect and :node both always
   do; a bare :text op has no explicit :h of its own, but every real page's
   text always sits inside a wrapping :node/:rect box that already covers
   at least as tall an area, so omitting :text's own height here is safe,
   not a guess -- confirmed by cssom.layout's own text-inside-a-box
   invariant).

   Defensively skips any op whose :y/:h isn't a genuine number -- a real,
   separate data-integrity gap (some ops can carry string-typed coordinates
   from an un-coerced upstream value) this function only needs to not be
   corrupted by, not fix."
  [ops]
  (reduce (fn [acc op]
            (let [y (:y op 0) h (:h op 0)]
              (if (and (number? y) (number? h)) (max acc (+ y h)) acc)))
          0 ops))

(defn enqueue-event [state event]
  (update state :events (fnil conj []) event))

(defn focus [state target]
  (assoc state :focus target))

(defn poll-event [state]
  (let [event (first (:events state))]
    [event (if event (update state :events subvec 1) state)]))

(defn- parent-index
  "Maps every node id to its parent id, derived from each node's own
   `:children` (the only direction `:nodes` stores). Absent from the map
   (nil lookup) means either an untracked id or the real root, which has
   no parent -- both correctly terminate `ancestor-chain` below."
  [state]
  (into {}
        (mapcat (fn [[id node]] (map #(vector % id) (:children node)))
                (:nodes state))))

(defn- ancestor-chain
  "`id` itself, then its parent, grandparent, etc, up to (and including)
   the root -- stops the first time `parents` has no entry."
  [parents id]
  (take-while some? (iterate parents id)))

(defn hit-test
  "Finds the topmost node whose painted box contains (x,y) -- regardless
   of whether IT has a listener -- then walks up its REAL ancestor chain
   for the first one that does, matching real DOM hit-testing + bubbling:
   a listener-less box always blocks (never becomes transparent to)
   whatever happens to be painted underneath it at the same point.

   Previously this reverse-scanned draw-ops (topmost paint order first)
   for the first box satisfying BOTH the point-in-box test AND already
   having a matching listener, skipping straight past any listener-less
   box in between to whatever unrelated node underneath also happened to
   contain the point -- a real click-through: a `position: absolute`
   overlay (a modal, dropdown, tooltip panel -- an ordinary, common
   layout, not an edge case) with no listener of its own, painted over
   an in-flow sibling that DOES have one, let a click on the overlay's
   own blank area silently fire the unrelated sibling underneath's
   handler instead of hitting nothing.

   `pointer-events: none` (previously never consulted here at all,
   confirmed via direct REPL reproduction before touching source): a
   real, common idiom for a decorative overlay/spinner/scrim that must
   be fully transparent to pointer events, letting whatever's painted
   underneath receive them instead -- the CSS spec's own contract is
   that such an element is treated as if it doesn't exist for hit-
   testing purposes. Without this, an element with `pointer-events:
   none` still `topmost`-blocked the point-in-box scan below exactly
   like an ordinary opaque box, so a click over it never reached a
   listener on whatever it visually sits on top of -- the OPPOSITE of
   `pointer-events: none`'s entire purpose. Fixed by skipping any op
   whose `:pointer-events` is `\"none\"` in the topmost scan, letting it
   continue past to whatever real box is underneath, exactly as if the
   `pointer-events: none` box weren't painted there at all."
  ;; `:handlers` is a real vector of EVERY handler-id registered for the
  ;; matched (node, event-type) pair, not just one -- matching
  ;; :add-event-listener's own multi-listener storage above. Nothing
  ;; downstream of hit-test's OWN return value currently reads
  ;; `:handlers` for dispatch (hit-event immediately re-queries via
  ;; listener-event below, which is where multi-handler DISPATCH
  ;; actually matters), but this keeps hit-test's own contract honest
  ;; about what's really registered, not silently truncated to one.
  ;;
  ;; `:hit` is cssom.layout's own answer to "where is this element
  ;; clicked", and it is not always its box (see that namespace's ns
  ;; docstring for the three measurements). When a `:node` op carries one,
  ;; it is a vector of rects that REPLACES the box here, `[]` meaning the
  ;; element is not a hit-test candidate at all. Without reading it, a
  ;; click on the ragged edge of a WRAPPED inline box -- inside the union
  ;; its box reports, inside neither line it actually occupies -- fired
  ;; that element's handler where a browser fires the containing block's;
  ;; a click on a `<p>`'s OVERFLOWING text hit nothing; and a click in a
  ;; table's border-spacing gap hit the `<tr>`, which no browser ever
  ;; reports.
  [state x y event-name]
  (let [event-name (normalize-event-name event-name)
        topmost (->> (:draw-ops state)
                     reverse
                     (some (fn [op]
                             (when (and (= :node (:draw/op op))
                                        (not= "none" (:pointer-events op))
                                        ;; visibility:hidden/collapse is
                                        ;; fully transparent to pointer
                                        ;; events too, same as pointer-
                                        ;; events:none -- previously never
                                        ;; consulted here either.
                                        (not (contains? #{"hidden" "collapse"} (:visibility op)))
                                        (if-let [hit (:hit op)]
                                          (some (fn [r] (and (<= (:x r) x (+ (:x r) (:w r)))
                                                             (<= (:y r) y (+ (:y r) (:h r)))))
                                                hit)
                                          (and (<= (:x op) x (+ (:x op) (:w op)))
                                               (<= (:y op) y (+ (:y op) (:h op))))))
                               (:id op)))))]
    (when topmost
      (let [parents (parent-index state)]
        (some (fn [id]
                (when-let [handlers (seq (get-in state [:listeners id event-name]))]
                  {:target id :handlers (vec handlers)}))
              (ancestor-chain parents topmost))))))

(defn listener-event
  "Returns a real vector of one event map PER handler-id currently
   registered for (target, event-name), in REGISTRATION ORDER -- matching
   real addEventListener dispatch order and kotoba.wasm.dom/dispatch-event's
   own established convention of one dispatch op per handler invocation.
   Previously returned a single `{:handler ... :target ... :name ...}` map
   assuming a scalar handler, silently dropping every listener after the
   first for a (node, event-type) pair with more than one registered.
   nil (not an empty vector) when there are no listeners at all, so
   callers' existing `(when-let [...] ...)` short-circuit is unchanged."
  ([state target event-name]
   (listener-event state target event-name nil))
  ([state target event-name extra]
   (let [event-name (normalize-event-name event-name)
         handlers (seq (get-in state [:listeners target event-name]))]
     (when handlers
       (mapv (fn [handler]
               (merge {:handler handler
                       :target target
                       :name event-name}
                      extra))
             handlers)))))

(defn hit-event
  "A real vector of event maps (see listener-event), one per handler
   registered on the hit-tested target, or nil if nothing matched."
  ([state x y event-name]
   (hit-event state x y event-name nil))
  ([state x y event-name extra]
   (let [event-name (normalize-event-name event-name)]
     (when-let [{:keys [target]} (hit-test state x y event-name)]
       (listener-event state target event-name (merge {:x x :y y} extra))))))

(defn focused-event
  "A real vector of event maps (see listener-event), one per handler
   registered on the currently-focused node, or nil if none/unfocused."
  ([state event-name]
   (focused-event state event-name nil))
  ([state event-name extra]
   (when-let [target (:focus state)]
     (listener-event state target event-name extra))))

(defn queue-event [state event]
  (cond-> (enqueue-event state event)
    (:target event) (focus (:target event))))

(defn queue-hit-event
  ([state x y event-name]
   (queue-hit-event state x y event-name nil))
  ([state x y event-name extra]
   ;; hit-event/focused-event now return a real vector of one event per
   ;; registered handler (see listener-event), so every matched handler
   ;; gets queued -- previously only the single (post-overwrite) handler
   ;; ever reached the queue at all.
   (if-let [events (hit-event state x y event-name extra)]
     (reduce queue-event state events)
     state)))

(defn queue-focused-event
  ([state event-name]
   (queue-focused-event state event-name nil))
  ([state event-name extra]
   (if-let [events (focused-event state event-name extra)]
     (reduce enqueue-event state events)
     state)))
