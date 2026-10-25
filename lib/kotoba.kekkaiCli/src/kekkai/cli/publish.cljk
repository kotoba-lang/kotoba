(ns kekkai.cli.publish
  "`kekkai netmap publish` — the command that did not exist.

  `kekkai.netmap/publish` and `kekkai.envelope/seal` landed on 2026-08-06 and
  could only be called from a REPL or a test: there was no way to turn a
  control-plane description into a signed netmap file from a shell. So the
  boundary between control plane and data plane was implemented, byte-pinned,
  and unusable.

  The input is one EDN file describing the tailnet. It is the operator's source
  of truth and it is deliberately the *whole* plane rather than one node's view
  — a netmap is a projection, and projecting each node separately from separate
  files is how two nodes end up disagreeing about who is in the tailnet."
  (:require [kotoba.lang.text :as str]
            [kekkai.acl :as acl]
            [kekkai.cli.sign :as sign]
            [kekkai.netmap :as netmap]
            ["node:fs" :as fs]
            ["node:path" :as path]))

(defn plane-problems
  "What is missing from a plane file, as a vector of strings.

  Reported together rather than one per run: an operator fixing a description
  should not have to re-run the command once per mistake."
  [{:keys [nodes plane version]}]
  (cond-> []
    (not (sequential? nodes)) (conj ":nodes must be a vector of node maps")
    (not (map? plane)) (conj ":plane must be {:policies {…} :peerings [...]}")
    (and (map? plane) (not (map? (:policies plane))))
    (conj ":plane :policies must be a map of tailnet-id -> policy")
    (not (int? version))
    (conj (str ":version must be an integer — it is bound into the Noise "
               "prologue, so it has to be monotonic across a rollout and only "
               "you know that"))))

(defn publish-all
  "-> `{node-id {:netmap … :envelope … :excluded […]}}` for every node in the
  plane that has data-plane facts.

  Every node's netmap is cut from **one** snapshot, which is the whole reason
  this takes a plane rather than a node."
  [inputs authority]
  (into {}
        (map (fn [node]
               (let [id (:id node)
                     nm (netmap/publish inputs id)]
                 [id {:netmap nm
                      :envelope (sign/seal nm authority)
                      :excluded (netmap/excluded inputs id)}])))
        (:nodes inputs)))

(defn- write! [dir id envelope]
  (let [p (.join path dir (str "netmap-" id ".signed.edn"))]
    (.writeFileSync fs p (str (sign/envelope-string envelope) "\n"))
    p))

(defn- describe-exclusions [excluded]
  (when (seq excluded)
    (str "      excluded: "
         (str/join ", "
                   (map (fn [{:keys [node excluded peering-would-allow?]}]
                          (str node " (" (name excluded)
                               (when peering-would-allow? ", peering would allow")
                               ")"))
                        excluded)))))

(defn run
  "Read the plane, publish and sign one netmap per node, write them out."
  [{:keys [plane-file authority-file out-dir only]}]
  (let [inputs (cljs.reader/read-string (.readFileSync fs plane-file "utf8"))
        problems (plane-problems inputs)]
    (when (seq problems)
      (throw (ex-info (str "plane file is not usable:\n  - "
                           (str/join "\n  - " problems))
                      {:type :kekkai/invalid-plane :problems problems})))
    (let [authority (cljs.reader/read-string
                     (.readFileSync fs authority-file "utf8"))
          published (publish-all inputs authority)
          wanted (if only (select-keys published [only]) published)]
      (when (and only (empty? wanted))
        (throw (ex-info (str "no such node in the plane: " only)
                        {:type :kekkai/unknown-node
                         :known (vec (keys published))})))
      (.mkdirSync fs out-dir #js {:recursive true})
      (println (str "authority " (sign/fingerprint (:public-b64 authority))
                    "  (nodes configure this as :netmap-authority-spki-b64)"))
      (println (sign/authority-spki-b64 authority))
      (println)
      (doseq [[id {:keys [netmap envelope excluded]}] (sort-by key wanted)]
        (let [p (write! out-dir id envelope)
              tailnet (:netmap/tailnet netmap)
              peers (count (:netmap/peers netmap))]
          (println (str "  " id "  tailnet=" tailnet
                        " v" (:netmap/version netmap)
                        " peers=" peers
                        "  -> " p))
          ;; Exclusions are printed, not buried. A node missing from a netmap
          ;; and a node denied by it are different operational states, and the
          ;; operator is the one who can tell whether the reason is intended.
          (when-let [line (describe-exclusions excluded)]
            (println line))))
      (println)
      (println (str (count wanted) " netmap(s) signed. Nodes verify against the "
                    "authority above; nothing here is trusted by being on disk."))
      {:published wanted :authority authority})))

(defn tailnets
  "Every tailnet the plane describes, for `kekkai netmap show`."
  [inputs]
  (->> (:nodes inputs) (map acl/tailnet-of) distinct sort vec))
