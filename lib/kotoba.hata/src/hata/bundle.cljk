(ns hata.bundle
  "bundle —— manifest・紋・logic 成果物・UI を 1 つの CAR にまとめた論理形。

  root ADR-2610082200（§7）。bytes からの CAR parse は io-ipld-car の仕事で、
  CAR root の CID 検証は fetch した 宿 の仕事。この ns が持つのは、manifest
  が指す CID がすべて entries に在り、その bytes の digest と一致すること
  だけ —— 内容アドレスが嘘を言っていないことを先に決める。")

(defn- referenced-cids
  "Every CID the manifest names as content: role 紋s, logic Forms, UI bundle.
  `:kotoba.app/latest` is an IPNS name (a Location hint), not content, and
  `:kotoba.app/bundle-cid` is the CAR root itself — the host checks that one
  against the bytes it fetched."
  [manifest]
  (concat (mapcat (fn [role]
                    (cons (:mon role) (or (:logic role) [])))
                  (or (:kotoba.app/roles manifest) []))
          (when-let [ui (:kotoba.app/ui manifest)]
            [(:bundle ui)])))

(defn problems
  "Everything wrong with the bundle's addressing. Empty = its CIDs hold."
  [{:keys [digest-fn]} {:bundle/keys [manifest entries]}]
  (cond-> []
    (nil? manifest)
    (conj {:problem :no-manifest})

    (empty? (:kotoba.app/roles (or manifest {})))
    (conj {:problem :no-roles :detail "a role carries the 紋 and its logic"})

    true
    (into (for [cid (distinct (referenced-cids manifest))
                :let [bytes (get entries cid)]
                :when (not= cid (when bytes (digest-fn bytes)))]
            (if bytes
              {:problem :digest-mismatch :cid cid}
              {:problem :missing-entry :cid cid})))))

(defn read-bundle
  "Verify then split. {:ok {:manifest :mon-cid :mon :logic :ui}} or
  {:problems [...]}. Nothing downstream sees a bundle whose digests do not
  hold — a rebuilt artifact must be the same bytes, and this is where that
  is decided."
  [seams {:bundle/keys [manifest entries cid] :as bundle}]
  (if-let [probs (seq (problems seams bundle))]
    {:problems (vec probs)}
    (let [ui (:kotoba.app/ui manifest)
          role (first (:kotoba.app/roles manifest))]
      {:ok {:manifest manifest
            :bundle-cid (or (:kotoba.app/bundle-cid manifest) cid)
            :mon-cid (:mon role)
            :mon (get entries (:mon role))
            :logic (mapv (fn [c] {:cid c :bytes (get entries c)})
                         (:logic role))
            :ui {:cid (:bundle ui)
                 :entry (:entry ui)
                 :bytes (get entries (:bundle ui))}}})))
