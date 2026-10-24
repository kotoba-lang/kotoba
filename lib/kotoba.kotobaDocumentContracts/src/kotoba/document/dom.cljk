(ns kotoba.document.dom
  "The trusted-subset DOM tree node SHAPE this stack already produces and
   consumes -- `kotoba.wasm.dom` (in `kotoba-lang/dom-gpu`) constructs it,
   `kotoba-lang/htmldom` parses real markup into it, `kotoba-lang/cssom`
   walks it for cascade+layout. This namespace documents and structurally
   validates that shape; it does NOT parse, mutate, or render anything --
   see this repo's own README, \"Non-goals\", for why a full WHATWG DOM
   (Shadow DOM, iframes, live NodeLists, mutation events) is deliberately
   not part of this contract.

   An element node:
     {:node/id   pos-int?   ; stable identity within one document
      :tag       keyword?   ; e.g. :div, :input, :ol -- lower-case HTML tag name
      :attrs     map?       ; keyword-keyed attribute map, e.g. {:class \"box\"}
      :children  [pos-int?]} ; ordered child :node/id refs, NOT inline nodes

   A text node:
     {:node/id pos-int?
      :text/content string?}

   Nodes are referenced by id (not nested inline) so a document is a flat
   map of id -> node, matching how `kotoba.wasm.dom` actually stores a
   document today -- a future non-Clojure renderer is free to use whatever
   internal representation it wants, as long as whatever tree it hands to a
   `kotoba-lang/cssom`-equivalent cascade/layout step conforms to this
   element/text-node shape at the boundary.")

(defn element-node?
  [x]
  (and (map? x)
       (pos-int? (:node/id x))
       (keyword? (:tag x))
       (map? (:attrs x))
       (vector? (:children x))
       (every? pos-int? (:children x))))

(defn text-node?
  [x]
  (and (map? x)
       (pos-int? (:node/id x))
       (string? (:text/content x))))

(defn node?
  [x]
  (or (element-node? x) (text-node? x)))
