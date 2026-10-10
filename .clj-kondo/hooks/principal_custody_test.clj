(ns hooks.principal-custody-test)

;; clj-kondo's view of kotoba.principal-custody-test/with-cli: the binding
;; vector names the world and directory locals, and the optional host-opts /
;; approve forms are evaluated where those locals are in scope -- exactly as
;; the real macro expands.
(defmacro with-cli [[world dir & opts] & body]
  `(let [~world (atom {}) ~dir ""]
     ~world ~dir
     ~@opts
     ~@body))
