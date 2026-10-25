(ns bim.cloud.http
  "Real OpenCDE HTTP publication for coordinated BIM/IFC and BCF payloads."
  (:require [kotoba.issue.opencde.http :as http]))

(def client http/client)
(def service-info! http/service-info!)
(def list-documents! http/list-documents!)
(def list-topics! http/list-topics!)

(defn publish-coordination-package!
  "Publish an IFC document followed by its ordered BCF topics. Stops on the
  first HTTP/conflict failure so callers never report a partially successful
  topic sequence as complete. Each topic may provide :expected-revision and
  :idempotency-key beside :guid and :topic."
  [client project-id document topics]
  (let [document-result (http/put-document! client project-id document)
        topic-results
        (mapv (fn [{:keys [guid topic expected-revision idempotency-key]}]
                (http/put-topic! client project-id guid topic
                                 (or expected-revision 0) idempotency-key))
              topics)]
    {:opencde.http/status :published
     :opencde.http/document document-result
     :opencde.http/topics topic-results}))
