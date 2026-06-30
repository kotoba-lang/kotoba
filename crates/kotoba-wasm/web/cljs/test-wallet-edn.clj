(ns test-wallet-edn
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]))

(def root (-> "../../../../" io/file .getCanonicalFile))

(defn file-at
  [& path]
  (apply io/file root path))

(defn slurp-at
  [& path]
  (slurp (apply file-at path)))

(defn fail!
  [message data]
  (throw (ex-info message data)))

(defn assert!
  [pred message data]
  (when-not pred
    (fail! message data)))

(def adr (edn/read-string (slurp-at "docs/adr.edn")))
(def shadow (edn/read-string (slurp-at "crates/kotoba-wasm/web/cljs/shadow-cljs.edn")))
(def package-json (slurp-at "crates/kotoba-wasm/web/cljs/package.json"))
(def package-lock (slurp-at "crates/kotoba-wasm/web/cljs/package-lock.json"))
(def ci-yml (slurp-at ".github/workflows/ci.yml"))
(def root-readme (slurp-at "README.md"))
(def cljs-readme (slurp-at "crates/kotoba-wasm/web/cljs/README.md"))

(def wallet
  (some #(when (= :adr-wallet-actor-cljs (:id %)) %)
        (:adrs adr)))

(assert! wallet
         "wallet ADR entry missing"
         {})

(assert! (= "ADR-wallet-actor-cljs.md" (:file wallet))
         "wallet ADR file mismatch"
         {:file (:file wallet)})

(assert! (.isFile (file-at "docs" (:file wallet)))
         "wallet ADR file missing"
         {:file (:file wallet)})

(def wallet-doc (slurp-at "docs" (:file wallet)))
(defn r0-status [s]
  (second (re-find #"(?i)r0[.-]([0-9]+)" (str s))))

(let [doc-r0 (r0-status wallet-doc)
      registry-r0 (r0-status (:status wallet))
      note-r0 (r0-status (:note wallet))]
  (assert! doc-r0
           "wallet ADR document status is missing R0 marker"
           {:file (:file wallet)})
  (assert! (= doc-r0 registry-r0 note-r0)
           "wallet ADR status markers are out of sync"
           {:document-r0 doc-r0
            :registry-r0 registry-r0
            :note-r0 note-r0
            :status (:status wallet)}))

(doseq [artifact (:artifacts wallet)]
  (assert! (.exists (file-at artifact))
           "wallet ADR artifact missing"
           {:artifact artifact}))

(assert! (= "cd crates/kotoba-wasm/web/cljs && npm run test:wallet:all"
            (:verify wallet))
         "wallet ADR verify command mismatch"
         {:verify (:verify wallet)})

(assert! (re-find #"npm run test:wallet:all\s+# Node \+ pure \+ ADR/package-lock/CI/export \+ browser ESM smoke"
                  root-readme)
         "root README wallet gate command summary is stale"
         {})

(assert! (re-find #"The same wallet gate runs in CI as `Wallet CLJS maturity gate`"
                  root-readme)
         "root README wallet CI discoverability line missing"
         {})

(assert! (re-find #"npm run test:wallet:all # Node \+ pure \+ ADR/package-lock/CI/export \+ browser ESM smoke"
                  cljs-readme)
         "CLJS README wallet gate command summary is stale"
         {})

(assert! (re-find #"kotoba\.wallet\.\*` R0\.168 is Node 22\+-guarded, pure-test, ADR/package-lock/CI/export-consistency, README-checked"
                  cljs-readme)
         "CLJS README wallet status summary is stale"
         {})

(let [exports (get-in shadow [:builds :web :modules :kotoba-node :exports])]
  (doseq [export '[walletRequest createWalletProvider runWalletEffect applyWalletCommands]]
    (assert! (contains? exports export)
             "wallet ESM export missing"
             {:export export})))

(assert! (re-find #"\"test:wallet:all\"" package-json)
         "package script test:wallet:all missing"
         {})

(assert! (re-find #"\"node\"\s*:\s*\">=22\"" package-json)
         "package Node engine must stay aligned to Node 22+"
         {})

(assert! (re-find #"\"test:wallet:node\"" package-json)
         "package script test:wallet:node missing"
         {})

(assert! (re-find #"test:wallet:node && npm run test:wallet" package-json)
         "wallet maturity gate must run Node version guard first"
         {})

(assert! (re-find #"\"lockfileVersion\"\s*:\s*3" package-lock)
         "package-lock must use npm lockfileVersion 3"
         {})

(assert! (re-find #"\"devDependencies\"\s*:\s*\{\s*\"shadow-cljs\"\s*:\s*\"\^2\.28\.0\"" package-lock)
         "package-lock root shadow-cljs range must match package.json"
         {})

(assert! (re-find #"\"engines\"\s*:\s*\{\s*\"node\"\s*:\s*\">=22\"" package-lock)
         "package-lock root Node engine must match package.json"
         {})

(assert! (re-find #"\"node_modules/shadow-cljs\"\s*:\s*\{\s*\"version\"\s*:\s*\"2\.28\.23\"" package-lock)
         "package-lock must pin shadow-cljs 2.28.23"
         {})

(doseq [[pattern message] [[#"(?m)^  wallet-cljs:" "CI wallet-cljs job missing"]
                           [#"name: Wallet CLJS maturity gate" "CI wallet job name missing"]
                           [#"working-directory: crates/kotoba-wasm/web/cljs" "CI wallet working directory mismatch"]
                           [#"actions/setup-node@v4" "CI wallet Node setup missing"]
                           [#"node-version: \"22\"" "CI wallet Node version must stay at 22"]
                           [#"cache-dependency-path: crates/kotoba-wasm/web/cljs/package-lock.json" "CI wallet npm cache path mismatch"]
                           [#"DeLaGuardo/setup-clojure@13\.2" "CI wallet bb setup missing"]
                           [#"run: npm ci" "CI wallet npm ci step missing"]
                           [#"run: npm run test:wallet:all" "CI wallet maturity command missing"]]]
  (assert! (re-find pattern ci-yml)
           message
           {:pattern (str pattern)}))

(println :ok)
