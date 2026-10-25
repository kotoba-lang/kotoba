(ns sumitsubo.methods.agent
  "sumitsubo 墨壺 — generative + modeling-assist cell. 1:1 port of py/agent.py. One ModelOp model,
  two runtimes (TS kernel applies, this cell emits). handle-model (NL → op plan → drawing datoms),
  handle-draft (2D drafting suggestions), handle-interop (Vectorworks/AutoCAD-shaped script → neutral
  ModelOp list, cleanroom G1), handle-export (resolve format + emit record, DWG-proprietary honesty
  G5). Pure-stdlib (json/re); the Murakumo llm (G3) + datalog host bindings are unused, so _llm_plan
  falls to the deterministic heuristic planner and _emit_datoms just returns the datoms (omitted legs)."
  (:require [kotoba.lang.text :as str]))

;; Shared ModelOp vocabulary (MUST stay in lockstep with the pinned Sumitsubo CAD SDK).
(def ^:private OP-SCHEMA
  {"layer" #{"name"} "point" #{"x" "y"} "line" #{"x1" "y1" "x2" "y2"} "polyline" #{"points"}
   "rect" #{"x" "y" "w" "h"} "circle" #{"cx" "cy" "r"} "arc" #{"cx" "cy" "r" "start" "end"}
   "box" #{"x" "y" "z" "w" "d" "h"} "extrude" #{"profile" "height"}
   "move" #{"target" "dx" "dy"} "scale" #{"target" "factor"}})

(def EXPORT-FIDELITY
  {"dxf" "full" "svg" "full" "obj" "full" "gltf" "full" "ifc" "subset" "step" "subset" "dwg" "fallback"})

(defn validate-ops
  "Keep only well-formed ops (G4 honesty: silently-malformed ops are dropped)."
  [ops]
  (vec (filter (fn [op] (when-let [req (get OP-SCHEMA (get op "op"))]
                          (every? #(contains? op %) req)))
               ops)))

(defn- heuristic-plan
  "Deterministic planner: recognizes 'box 10x20x30', 'rect 100x50', 'circle r=5', 'extrude WxH by N'."
  [prompt]
  (let [p (str/lower prompt)
        i #(Integer/parseInt %)
        ops (concat
             (for [[_ w d h] (re-seq #"box\s+(\d+)\s*[x×]\s*(\d+)\s*[x×]\s*(\d+)" p)]
               {"op" "box" "x" 0 "y" 0 "z" 0 "w" (i w) "d" (i d) "h" (i h)})
             (for [[_ w h] (re-seq #"rect(?:angle)?\s+(\d+)\s*[x×]\s*(\d+)" p)]
               {"op" "rect" "x" 0 "y" 0 "w" (i w) "h" (i h)})
             (for [[_ r] (re-seq #"circle\s+r\s*=?\s*(\d+)" p)]
               {"op" "circle" "cx" 0 "cy" 0 "r" (i r)})
             (for [[_ w h ht] (re-seq #"extrude\s+(\d+)\s*[x×]\s*(\d+)\s+by\s+(\d+)" p)]
               (let [w (i w) h (i h)]
                 {"op" "extrude" "profile" [[0 0] [w 0] [w h] [0 h]] "height" (i ht)})))]
    (validate-ops (if (empty? ops) [{"op" "rect" "x" 0 "y" 0 "w" 100 "h" 100}] (vec ops)))))

(defn- llm-plan
  "Murakumo-fronted ModelOp plan (G3); the llm host binding is the omitted leg, so this is the
  deterministic heuristic planner."
  [prompt]
  (heuristic-plan prompt))

(defn- emit-datoms [drawing-id ops sourcing]
  ;; datalog host binding omitted → return the datoms, never transact
  (first (reduce (fn [[acc n] op]
                   (if (contains? #{"layer" "move" "scale"} (get op "op"))
                     [acc n]
                     (let [n (inc n) eid (str drawing-id ".e" n)]
                       [(into acc [[eid ":dwg.entity/id" eid] [eid ":dwg.entity/of" drawing-id]
                                   [eid ":dwg.entity/kind" (get op "op")]
                                   [eid ":dwg.entity/layer" (get op "layer" "0")]]) n])))
                 [[[drawing-id ":dwg/id" drawing-id] [drawing-id ":dwg/sourcing" sourcing]] 0]
                 ops)))

(defn handle-model [state]
  (let [ops (llm-plan (get state "prompt" ""))
        drawing-id (get state "drawing_id" "drawing-1")
        sourcing (get state "sourcing" "representative")]   ; G7
    (merge state {"ops" ops "datoms" (emit-datoms drawing-id ops sourcing) "sourcing" sourcing})))

(defn handle-draft
  "Suggest dimensions / constraints / layer hygiene. Heuristic over a validated op set."
  [state]
  (let [ops (validate-ops (get state "ops" []))
        has-layer (some #(= (get % "op") "layer") ops)
        base (if (and (not has-layer) (seq ops))
               [{"kind" "layer" "note" "geometry on default layer '0'; create named layers"}]
               [])
        suggestions (reduce (fn [s o]
                              (case (get o "op")
                                "rect" (conj s {"kind" "dimension" "target" "rect"
                                                "note" (str "width=" (get o "w") " height=" (get o "h"))})
                                "circle" (conj s {"kind" "dimension" "target" "circle"
                                                  "note" (str "diameter=" (* 2 (get o "r")))})
                                "polyline" (if (not (get o "closed"))
                                             (conj s {"kind" "constraint" "target" "polyline"
                                                      "note" "open polyline; close for a region/extrude"})
                                             s)
                                s))
                            base ops)]
    (merge state {"suggestions" suggestions})))

(defn handle-interop
  "Vendor-shaped script → neutral ops (python mirror of the TS adapters, G1). Unsupported tokens are
  skipped (G4 honesty)."
  [state]
  (let [ops (loop [lines (get state "script" []) layer "0" acc []]
              (if (empty? lines)
                acc
                (let [line (first lines)]
                  (if (empty? line)
                    (recur (rest lines) layer acc)
                    (let [cmd (-> (str (first line)) str/upper (str/replace #"^[._]+" ""))
                          args (vec (rest line))
                          nf (fn [k] (double (nth args k)))]
                      (cond
                        (= cmd "LAYER")
                        (let [l (str (nth args 0))] (recur (rest lines) l (conj acc {"op" "layer" "name" l})))
                        (= cmd "LINE")
                        (recur (rest lines) layer (conj acc {"op" "line" "layer" layer
                                                             "x1" (nf 0) "y1" (nf 1) "x2" (nf 2) "y2" (nf 3)}))
                        (contains? #{"RECT" "RECTANG" "RECTANGLE"} cmd)
                        (let [x0 (nf 0) y0 (nf 1) x1 (nf 2) y1 (nf 3)]
                          (recur (rest lines) layer (conj acc {"op" "rect" "layer" layer
                                                               "x" (min x0 x1) "y" (min y0 y1)
                                                               "w" (Math/abs (- x1 x0)) "h" (Math/abs (- y1 y0))})))
                        (contains? #{"CIRCLE" "OVAL"} cmd)
                        (recur (rest lines) layer (conj acc {"op" "circle" "layer" layer
                                                             "cx" (nf 0) "cy" (nf 1) "r" (nf 2)}))
                        (contains? #{"ARC" "ARCBYCENTER"} cmd)
                        (recur (rest lines) layer (conj acc {"op" "arc" "layer" layer "cx" (nf 0) "cy" (nf 1)
                                                             "r" (nf 2) "start" (nf 3) "end" (nf 4)}))
                        (contains? #{"POLY" "PLINE" "POLYLINE"} cmd)
                        (let [pts (vec (for [k (range 0 (dec (count args)) 2)]
                                         [(double (nth args k)) (double (nth args (inc k)))]))]
                          (recur (rest lines) layer (conj acc {"op" "polyline" "layer" layer
                                                               "points" pts "closed" false})))
                        (= cmd "EXTRUDE")
                        (let [height (double (last args)) flat (vec (butlast args))
                              prof (vec (for [k (range 0 (dec (count flat)) 2)]
                                          [(double (nth flat k)) (double (nth flat (inc k)))]))]
                          (recur (rest lines) layer (conj acc {"op" "extrude" "layer" layer
                                                               "profile" prof "height" height})))
                        :else (recur (rest lines) layer acc)))))))]
    (merge state {"ops" (validate-ops ops) "flavor" (get state "flavor" "")})))

(defn handle-export
  "Resolve target format + emit export record. Fidelity reported (full|subset|fallback); DWG never
  claimed native (G5)."
  [state]
  (let [fmt (str/lower (str (get state "format" "dxf")))
        fidelity (get EXPORT-FIDELITY fmt "unsupported")
        record (cond-> {"drawingId" (get state "drawing_id" "drawing-1") "format" fmt
                        "fidelity" fidelity "native" (not= fmt "dwg")}
                 (= fmt "dwg")
                 (merge {"advisory" "DWG_PROPRIETARY" "fallback" "dxf"
                         "note" "DWG is proprietary; emit DXF and convert via external ODA/LibreDWG."})
                 (and (not= fmt "dwg") (= fidelity "subset"))
                 (assoc "note" (str fmt " is an honest subset export (ADR-2606033600 N6).")))]
    (merge state {"record" record})))
