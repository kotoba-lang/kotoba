(ns openapi.execute
  "Pure request builder for an OpenAPI-3-as-EDN model. State is plain data — no I/O,
  no side effects. The host injects an IHttp port (`openapi.ports`) for actual dispatch.

  `request-for` builds a request map by:
    1. Looking up the operation by operationId
    2. Substituting {param} templates in the path
    3. Collecting remaining declared params as :query or :body
    4. Returning an error map if a required param is missing

  `invoke` delegates the built request to `IHttp/request`."
  (:require [kotoba.lang.text :as str]
            [openapi.model  :as m]
            [openapi.ports  :as p]))

(defn request-for
  "Build a request map for the operation identified by `operation-id` in `model`,
  using `args-map` (string-keyed, e.g. {\"id\" \"42\" \"verbose\" true}).

  Returns:
  - {:method kw :url str [:query map] [:body map]} on success
  - {:openapi/error :operation-not-found :openapi/operation-id id} if the op is missing
  - {:openapi/error :missing-required-params :openapi/missing [\"name\" …]} if required
    params are absent from args-map."
  [model operation-id args-map]
  (if-let [{:keys [path method op]} (m/operation-by-id model operation-id)]
    (let [params          (m/parameters-for op)
          missing-req     (->> params
                               (filter :openapi/required)
                               (remove #(contains? args-map (:openapi/name %)))
                               (mapv :openapi/name))]
      (if (seq missing-req)
        {:openapi/error   :missing-required-params
         :openapi/missing missing-req}
        (let [path-ps  (->> params (filter #(= :path  (:openapi/in %))))
              query-ps (->> params (filter #(= :query (:openapi/in %))))
              body-ps  (->> params (filter #(= :body  (:openapi/in %))))
              url      (reduce (fn [u pp]
                                 (str/replace u
                                              (str "{" (:openapi/name pp) "}")
                                              (str (get args-map (:openapi/name pp)))))
                               path
                               path-ps)
              query    (into {} (for [qp query-ps
                                      :when (contains? args-map (:openapi/name qp))]
                                  [(:openapi/name qp) (get args-map (:openapi/name qp))]))
              body     (into {} (for [bp body-ps
                                      :when (contains? args-map (:openapi/name bp))]
                                  [(:openapi/name bp) (get args-map (:openapi/name bp))]))]
          (cond-> {:method method :url url}
            (seq query) (assoc :query query)
            (seq body)  (assoc :body  body)))))
    {:openapi/error        :operation-not-found
     :openapi/operation-id operation-id}))

(defn invoke
  "Build a request for `operation-id` with `args` and dispatch it via `IHttp/request`
  on `ports`. Returns whatever the IHttp implementation returns."
  [ports model operation-id args]
  (p/request ports (request-for model operation-id args)))
