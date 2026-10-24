(require '[nfs.memory :as memory]
         '[nfs.tcp :as tcp]
         '[nfs.v3 :as nfs]
         '[xdr.core :as xdr])

(def state (memory/store))
(def fs (memory/filesystem state))

(let [root (nfs/-root fs)
      hello (nfs/-create fs root "hello.txt" {})
      _ (nfs/-write fs hello 0 (xdr/->bytes "こんにちは、Cloud Itonami\n"))
      docs (nfs/-mkdir fs root "docs" {})
      note (nfs/-create fs docs "note.md" {})]
  (nfs/-write fs note 0 (xdr/->bytes "# note\n\nwritten over NFSv3\n")))

(def server (tcp/start! {:fs fs
                         :dir "/kotoba"
                         :port (Integer/parseInt (or (first *command-line-args*) "0"))}))

(println (str "nfs listening on 127.0.0.1:" (:port server) " export " (:dir server)))
(flush)
@(promise)
