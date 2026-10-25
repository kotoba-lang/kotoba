(ns kisekae.capability
  "Fail-closed capability policy for VRM composition. URLs/CIDs are resources,
   never authority. The host supplies concrete capability values after its
   CACAO/local-policy intersection; this namespace only consumes them."
  (:require [kotoba.lang.capability-values :as values]))

(def kinds
  #{:vrm/asset-read :vrm/compose :vrm/preview :vrm/export :vrm/publish})

(def action->kind
  {:asset/read :vrm/asset-read
   :character/compose :vrm/compose
   :character/preview :vrm/preview
   :character/export :vrm/export
   :character/publish :vrm/publish})

(defn capability? [x]
  (and (values/capability? x)
       (contains? kinds (:cap/kind x))
       (= (:cap/kind x) (get values/effect-for-kind (:cap/kind x)))
       ;; Requested caps have no grant provenance. Only a concrete cap
       ;; returned by canonical grant/policy intersection executes a plan.
       (seq (:cap/provenance x))))

(defn permits? [cap action resource]
  (and (capability? cap)
       (= (action->kind action) (:cap/kind cap))
       (let [scope (:cap/resource cap)]
         (or (= :any scope) (= resource scope)
             (and (set? scope) (contains? scope resource))))))

(defn require! [caps action resource]
  (or (first (filter #(permits? % action resource) caps))
      (throw (ex-info "kisekae: capability denied"
                      {:denied :capability/missing-or-out-of-scope
                       :action action :resource resource
                       :required-kind (action->kind action)}))))

(defn required-for-spec [spec output-resource]
  (vec (concat
        (map (fn [url] {:action :asset/read :resource url})
             (distinct (cons (get-in spec [:spec/base :vrm/url])
                             (map #(get-in % [:part/source :vrm/url]) (:spec/parts spec)))))
        [{:action :character/compose :resource (:spec/id spec)}
         {:action :character/preview :resource (:spec/id spec)}
         {:action :character/export :resource output-resource}])))

(defn authorize-plan! [caps requirements]
  (doseq [{:keys [action resource]} requirements]
    (require! caps action resource))
  requirements)
