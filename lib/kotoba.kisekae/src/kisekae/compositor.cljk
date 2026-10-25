(ns kisekae.compositor
  "Portable composition IR. Pure CLJC decides what must happen; a CLJS host
   fetches bytes/renders a preview, while Murakumo workers may execute the same
   plan remotely. No DOM, WebGPU, fetch, or credentials enter this value."
  (:require [kisekae.spec :as spec]
            [kisekae.capability :as capability]))

(def plan-version 1)

(defn plan
  [{:keys [spec output-resource preview-target]}]
  (let [requirements (capability/required-for-spec spec output-resource)]
    {:kisekae.plan/version plan-version
     :plan/id (str "compose:" (:spec/id spec))
     :plan/spec spec
     :plan/requirements requirements
     :plan/phases
     [{:phase :asset/fetch :inputs (spec/part-urls spec)}
      {:phase :vrm/parse :engine :kotoba-lang/org-vrmc-vrm}
      {:phase :part/decompose :categories [:body :hair :face :outfit :accessory]}
      {:phase :skeleton/unify :base (get-in spec [:spec/base :vrm/url])
       :skin-policy :rebind-to-base-humanoid}
      {:phase :mesh/compose :operations [:remove-overridden :append-selected]}
      {:phase :material/apply :edits (:spec/material-edits spec)}
      {:phase :expression/apply :edits (:spec/expression-edits spec)}
      {:phase :preview/render :target preview-target :host :cljs}
      {:phase :vrm/export :format :vrm-1.0 :output output-resource}]}))

(defn authorized-plan! [caps opts]
  (let [p (plan opts)]
    (capability/authorize-plan! caps (:plan/requirements p))
    p))

(defn murakumo-job [caps authorized-plan destination]
  (capability/require! caps :character/publish destination)
  {:job/type :kisekae/compose-vrm
   :job/version 1
   :job/plan authorized-plan
   :job/destination destination
   :job/requires [:mac-mini-control-worker]
   :job/outputs [{:kind :vrm :addressing :cid}
                 {:kind :preview :format :gltf}]})
