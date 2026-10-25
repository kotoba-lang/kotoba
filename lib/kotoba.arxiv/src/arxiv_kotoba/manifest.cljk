(ns arxiv-kotoba.manifest)

(def actor
  {:actor/id :actor/arxiv
   :actor/kind :organism
   :actor/domain :scholarly-publishing
   :actor/name "arXiv yorishiro organism"
   :actor/represents {:external/service "arxiv.org"
                      :not-official true}
   :actor/capabilities
   [{:op :arxiv/search
     :risk :read-only
     :skill :arxiv.search}
    {:op :arxiv/advise-categories
     :risk :read-only
     :skill :arxiv.advise-categories}
    {:op :arxiv/validate-package
     :risk :read-only
     :skill :arxiv.validate-package}
    {:op :arxiv/plan-submission
     :risk :read-only
     :skill :arxiv.plan-submission}
    {:op :arxiv/login
     :risk :external-auth
     :skill :arxiv.login}
    {:op :arxiv/create-submission
     :risk :external-draft
     :skill :arxiv.create-submission}
    {:op :arxiv/fill-start-form
     :risk :external-draft
     :skill :arxiv.fill-start-form}
    {:op :arxiv/upload-source
     :risk :external-draft
     :skill :arxiv.upload-source}
    {:op :arxiv/final-submit
     :risk :public-submit
     :skill :arxiv.final-submit
     :requires [:human-approval]}
    {:op :arxiv/check-status
     :risk :read-only
     :skill :arxiv.check-status}
    {:op :arxiv/run-browser-pipeline
     :risk :external-draft
     :skill :arxiv.run-browser-pipeline}]
   :actor/yorishiro :yorishiro/arxiv
   :actor/browser-runner
   {:module "arxiv_submit"
    :bin "bin/arxiv-submit"
    :credentials {:op-item "Arxiv - N24" :op-vault "Private"
                  :account "junkawasaki-n24y"
                  :email "n24y001j@mail.cc.niigata-u.ac.jp"}}})

(def yorishiro
  {:yorishiro/id :yorishiro/arxiv
   :yorishiro/surfaces
   [{:route/id :local
     :route/kind :local
     :route/capabilities [:arxiv/advise-categories
                          :arxiv/validate-package
                          :arxiv/plan-submission]
     :route/prefer 1}
    {:route/id :api
     :route/kind :api
     :route/capabilities [:arxiv/search]
     :route/prefer 10}
    ;; computer route preferred for multi-step Playwright pipeline
    {:route/id :computer
     :route/kind :computer
     :route/capabilities [:arxiv/login
                          :arxiv/create-submission
                          :arxiv/fill-start-form
                          :arxiv/upload-source
                          :arxiv/run-browser-pipeline
                          :arxiv/check-status]
     :route/prefer 20}
    {:route/id :browser-dom
     :route/kind :browser
     :route/capabilities [:arxiv/login
                          :arxiv/create-submission
                          :arxiv/fill-start-form
                          :arxiv/upload-source
                          :arxiv/final-submit
                          :arxiv/check-status]
     :route/prefer 50}
    {:route/id :human-handoff
     :route/kind :human
     :route/capabilities [:arxiv/final-submit]
     :route/prefer 100}]})

(defn capability
  [op]
  (first (filter #(= op (:op %)) (:actor/capabilities actor))))
