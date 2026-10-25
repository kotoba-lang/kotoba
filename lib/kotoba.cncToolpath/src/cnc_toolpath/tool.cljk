(ns cnc-toolpath.tool
  "Cutting tool definitions and tool library management. Restored from
  kami-cam's `tool` module (kami-engine/kami-cam/src/tool.rs, deleted
  PR #82).")

(def tool-types #{:end-mill :ball-nose :bull-nose :drill :tap :face-mill :chamfer-mill :lathe})
(def tool-materials #{:hss :carbide :ceramic :cbn :pcd})

(defn tool
  [{:keys [id name tool-type diameter flute-length overall-length
            flute-count corner-radius material coating]}]
  {:id id :name name :tool-type tool-type :diameter diameter
   :flute-length flute-length :overall-length overall-length
   :flute-count flute-count :corner-radius corner-radius
   :material material :coating coating})

(defn tool-library
  "A fresh, empty tool library."
  []
  {:tools {}})

(defn add
  "Insert or replace `t` in `lib`. Returns `[lib' previous-tool-or-nil]`."
  [lib t]
  [(assoc-in lib [:tools (:id t)] t) (get (:tools lib) (:id t))])

(defn get-tool [lib id] (get (:tools lib) id))

(defn remove-tool
  "Remove the tool with `id` from `lib`. Returns `[lib' removed-tool-or-nil]`."
  [lib id]
  [(update lib :tools dissoc id) (get (:tools lib) id)])

(defn list-tools
  "All tools in `lib`, sorted by id."
  [lib]
  (vec (sort-by :id (vals (:tools lib)))))

(defn lib-count [lib] (count (:tools lib)))
(defn lib-empty? [lib] (empty? (:tools lib)))
