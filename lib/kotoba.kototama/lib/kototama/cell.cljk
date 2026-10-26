(ns kototama.cell
  "kototama · cell — the distilled kotodama cell abstraction. A cell is a pure
  transformer `solve : state -> state` plus declarative metadata (id, phase,
  triggers). Cells are the unit of work; an organism (see `kototama.organism`)
  schedules them. Pure `.cljc`, no Pregel/StateGraph dependency — the heavy
  langgraph orchestration is optional and lives above this layer."
  (:refer-clojure :exclude [run]))

(defonce ^{:doc "id → cell map"} registry (atom {}))

(defn cell
  "Construct a cell. opts: :phase (kw, e.g. :periodic), :triggers (vec),
  :doc (str). `solve` is `(fn [state] state')` and MUST be pure."
  [id solve & [opts]]
  (merge {:id id :phase :periodic :triggers [] :solve solve} opts))

(defn register!
  "Register a cell in the global registry; returns the cell."
  [c] (swap! registry assoc (:id c) c) c)

(defn get-cell [id] (get @registry id))

(defn run
  "Run a registered (or given) cell on `state`. Throws if id unknown."
  [id-or-cell state]
  (let [c (if (map? id-or-cell) id-or-cell
              (or (get-cell id-or-cell)
                  (throw (ex-info "unknown cell" {:id id-or-cell}))))]
    ((:solve c) state)))

#?(:clj
   (defmacro defcell
     "(defcell my-cell {:phase :periodic} [state] ...body...) → registers a cell
     named my-cell and binds the var to it."
     [name opts argv & body]
     `(def ~name (register! (cell ~(keyword name) (fn ~argv ~@body) ~opts)))))
