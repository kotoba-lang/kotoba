(ns apn.model
  "An All-Photonics Network (APN) topology as plain EDN data — photonic
  nodes (ROADM sites), DWDM fibre links, and lightpaths (end-to-end
  single-wavelength optical circuits that never leave the optical domain,
  i.e. no O-E-O regeneration along the path). No I/O, no third-party deps
  — portable .cljc (JVM, ClojureScript, SCI).

  Wavelength continuity is enforced structurally: a lightpath carries one
  :apn/wavelength for its whole :apn/path, so a wavelength-converting
  circuit is inexpressible in this model.")

(defn system
  "An empty APN topology."
  []
  {:apn/nodes {} :apn/links {} :apn/lightpaths {}})

;; -- nodes -------------------------------------------------------------

(defn node
  [id opts]
  (merge {:apn/id id :apn/role :roadm} opts {:apn/id id}))

(defn add-node
  [sys n]
  (assoc-in sys [:apn/nodes (:apn/id n)] n))

(defn nodes [sys] (vals (:apn/nodes sys)))
(defn node-by-id [sys id] (get-in sys [:apn/nodes id]))

;; -- links ---------------------------------------------------------------

(defn link
  "A bidirectional fibre link between node a and node z, carrying a set of
  DWDM channels available for lightpaths. :apn/occupied maps a channel
  number to the id of the lightpath currently holding it."
  [id a z opts]
  (merge {:apn/id id :apn/a a :apn/z z
          :apn/channels #{}
          :apn/occupied {}}
         opts
         {:apn/id id :apn/a a :apn/z z}))

(defn add-link
  [sys l]
  (assoc-in sys [:apn/links (:apn/id l)] l))

(defn links [sys] (vals (:apn/links sys)))
(defn link-by-id [sys id] (get-in sys [:apn/links id]))

(defn links-at
  "All links touching node-id."
  [sys node-id]
  (filter #(or (= node-id (:apn/a %)) (= node-id (:apn/z %))) (links sys)))

(defn other-end
  "The node at the far end of link from node-id."
  [l node-id]
  (cond
    (= node-id (:apn/a l)) (:apn/z l)
    (= node-id (:apn/z l)) (:apn/a l)
    :else nil))

;; -- lightpaths ------------------------------------------------------------

(defn lightpath
  [id src dst opts]
  (merge {:apn/id id :apn/src src :apn/dst dst :apn/state :requested}
         opts
         {:apn/id id :apn/src src :apn/dst dst}))

(defn add-lightpath
  [sys lp]
  (assoc-in sys [:apn/lightpaths (:apn/id lp)] lp))

(defn remove-lightpath
  [sys id]
  (update sys :apn/lightpaths dissoc id))

(defn lightpaths [sys] (vals (:apn/lightpaths sys)))
(defn lightpath-by-id [sys id] (get-in sys [:apn/lightpaths id]))

;; -- spectrum bookkeeping --------------------------------------------------

(defn occupy-channel
  "Mark channel on link-id as held by lightpath-id."
  [sys link-id channel lightpath-id]
  (assoc-in sys [:apn/links link-id :apn/occupied channel] lightpath-id))

(defn free-channel
  [sys link-id channel]
  (update-in sys [:apn/links link-id :apn/occupied] dissoc channel))

(defn occupy-path
  "Mark channel on every link in path as held by lightpath-id."
  [sys path channel lightpath-id]
  (reduce (fn [s link-id] (occupy-channel s link-id channel lightpath-id))
          sys path))

(defn free-path
  [sys path channel]
  (reduce (fn [s link-id] (free-channel s link-id channel)) sys path))
