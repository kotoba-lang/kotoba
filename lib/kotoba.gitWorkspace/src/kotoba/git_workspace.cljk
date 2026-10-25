(ns kotoba.git-workspace
  "Portable repository/forge catalog read-model. Host effects are injected as data."
  (:require [kotoba.lang.text :as str]))

(def sort-keys #{:name :updated-at :issues :pull-requests :work})

(defn remote->ref [remote]
  (when-let [[_ org repo] (re-find #"(?:github\.com|git\.kotobase\.net)[:/]([^/]+)/([^/]+?)(?:\.git)?$"
                                    (str remote))]
    (str org "/" repo)))

(defn normalize-repo [{:repo/keys [path remote ref] :as repo}]
  (let [ref (or ref (remote->ref remote))
        [org name] (when ref (str/split ref #"/" 2))]
    (assoc repo :repo/ref (or ref (str "local/" (last (str/split (str path) #"/"))))
                :repo/org (or org "local")
                :repo/name (or name (last (str/split (str path) #"/")))
                :repo/issues (vec (or (:repo/issues repo) []))
                :repo/pull-requests (vec (or (:repo/pull-requests repo) []))
                :repo/projects (vec (or (:repo/projects repo) []))
                :repo/work-items (vec (or (:repo/work-items repo) [])))))

(defn attach-forge [repos forge-items]
  (let [by-ref (group-by :forge/repo forge-items)]
    (mapv (fn [repo]
            (let [repo (normalize-repo repo)
                  items (get by-ref (:repo/ref repo))]
              (assoc repo
                     :repo/issues (filterv #(= :issue (:forge/kind %)) items)
                     :repo/pull-requests (filterv #(= :pull-request (:forge/kind %)) items))))
          repos)))

(defn- sort-value [sort-key repo]
  (case sort-key
    :updated-at (or (:repo/updated-at repo) "")
    :issues (count (:repo/issues repo))
    :pull-requests (count (:repo/pull-requests repo))
    :work (count (:repo/work-items repo))
    (str/lower (:repo/name repo))))

(defn sort-repos
  ([repos sort-key] (sort-repos repos sort-key :asc))
  ([repos sort-key direction]
   (let [sort-key (if (sort-keys sort-key) sort-key :name)
         ordered (sort-by (juxt #(sort-value sort-key %) :repo/ref) repos)]
     (vec (if (= direction :desc) (reverse ordered) ordered)))))

(defn catalog [{:keys [repos forge-items sort-key sort-direction]}]
  (let [repos (sort-repos (attach-forge repos forge-items)
                          (or sort-key :name) (or sort-direction :asc))]
    {:catalog/repos repos
     :catalog/repo-count (count repos)
     :catalog/issue-count (reduce + (map (comp count :repo/issues) repos))
     :catalog/pull-request-count (reduce + (map (comp count :repo/pull-requests) repos))
     :catalog/orgs (->> repos (group-by :repo/org) (sort-by key)
                        (mapv (fn [[org rs]] {:org/id org :org/repos (vec rs)
                                             :org/repo-count (count rs)})))}))
