(ns kotoba.lsp-rpc
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: errors. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:require [kotoba.lsp-rpc.error-response :as error-response-ns]
            [kotoba.lsp-rpc.frame :as frame-ns]
            [kotoba.lsp-rpc.handle-message :as handle-message-ns]
            [kotoba.lsp-rpc.make-server :as make-server-ns]
            [kotoba.lsp-rpc.notification :as notification-ns]
            [kotoba.lsp-rpc.request :as request-ns]
            [kotoba.lsp-rpc.response :as response-ns]
            [kotoba.lsp-rpc.unframe :as unframe-ns]))

(def error-response "See kotoba.lsp-rpc.error-response/error-response." error-response-ns/error-response)
(def frame "See kotoba.lsp-rpc.frame/frame." frame-ns/frame)
(def handle-message "See kotoba.lsp-rpc.handle-message/handle-message." handle-message-ns/handle-message)
(def make-server "See kotoba.lsp-rpc.make-server/make-server." make-server-ns/make-server)
(def notification "See kotoba.lsp-rpc.notification/notification." notification-ns/notification)
(def request "See kotoba.lsp-rpc.request/request." request-ns/request)
(def response "See kotoba.lsp-rpc.response/response." response-ns/response)
(def unframe "See kotoba.lsp-rpc.unframe/unframe." unframe-ns/unframe)
