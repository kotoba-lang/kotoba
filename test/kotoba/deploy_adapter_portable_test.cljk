(ns kotoba.deploy-adapter-portable-test
  "The genuinely portable slice of kotoba.deploy-adapter-test: pure
  plan/parse-target/public-urls/validate-control-plane-profile coverage that
  touches no host port at all. Everything that goes through `execute!`
  against a fake-host, `kotoba.launcher`, or java.nio.file stays in
  kotoba.deploy-adapter-test (.clj) -- not only because those specific
  assertions use java.nio.file/Files, but because
  kotoba.deploy-adapter/execute! itself resolves manifests and receipts
  through a private `read-edn` whose `:cljs` branch is a bare `nil` (its
  `:clj` require of `clojure.edn` is not even mirrored into a `:cljs`
  branch, though nbb does support `clojure.edn/read-string` directly --
  verified separately). So on this host, EVERY `execute!` operation that
  reads a manifest or a receipt returns as if the file were empty, no
  matter what the fake-host's `-read-file` returns. That is a real,
  measured behavioural gap between the two hosts for this .cljc namespace,
  not a test-portability problem to paper over by porting the assertion
  anyway -- see the porting session's report for the exact finding."
  (:require #?(:clj [clojure.test :refer [deftest is]]
               :cljs [cljs.test :refer [deftest is] :include-macros true])
            [kotoba.deploy-adapter :as deploy-adapter]))

(deftest plan-defaults-to-plan-operation
  (let [p (deploy-adapter/plan {:positionals []
                                :options {:manifest "pkg.edn" :target "dev"}})]
    (is (= :plan (:operation p)))
    (is (true? (:dry-run? p)))
    (is (= "./.kotoba/deploy/dev" (:target-dir p)))))

(deftest plan-rejects-bad-requests
  (is (= :deploy/unknown-operation
         (:error (deploy-adapter/plan {:positionals ["ship"] :options {:target "dev"}}))))
  (is (= :deploy/missing-target
         (:error (deploy-adapter/plan {:positionals ["apply"] :options {}})))))

(deftest request-dry-run-respects-contract-default
  (is (true? (deploy-adapter/request-dry-run? {:options {}})))
  (is (true? (deploy-adapter/request-dry-run? {:options {:dry-run true}})))
  (is (false? (deploy-adapter/request-dry-run? {:options {:dry-run "false"}}))))

(deftest parse-target-classifies-local-and-reside
  (is (= :local (:substrate (deploy-adapter/parse-target "pkg.edn" "dev"))))
  (is (= "./.kotoba/deploy/dev"
         (:target-dir (deploy-adapter/parse-target "pkg.edn" "dev"))))
  (is (= "/t/env" (:target-dir (deploy-adapter/parse-target "pkg.edn" "/t/env"))))
  (is (= "/abs" (:target-dir (deploy-adapter/parse-target "pkg.edn" "file:/abs"))))
  (let [r (deploy-adapter/parse-target "pkg.edn" "murakumo:asher")]
    (is (= :reside (:substrate r)))
    (is (= "murakumo" (:control-plane r)))
    (is (= "asher" (:node r)))
    (is (= "./.kotoba/deploy/murakumo/asher" (:target-dir r))))
  (let [r (deploy-adapter/parse-target "pkg.edn" "fleet")]
    (is (= :reside (:substrate r)))
    (is (nil? (:node r)))
    (is (= "./.kotoba/deploy/fleet/default" (:target-dir r))))
  (is (= :deploy/unknown-target-scheme
         (:error (deploy-adapter/parse-target "pkg.edn" "https://deno.com")))))

(deftest plan-reside-selects-explicit-or-canary-node-without-a-process
  (let [p (deploy-adapter/plan {:positionals ["apply"]
                                :options {:manifest "app.edn"
                                          :target "murakumo:asher"}})]
    (is (= :reside (:substrate p)))
    (is (= "asher" (:node p)))
    (is (nil? (:invoke p)))
    (is (true? (:dry-run? p)))))

(deftest public-urls-are-murakumo-https-and-ipns
  (let [urls (deploy-adapter/public-urls "k51qabc" "bafkreidemo")]
    (is (= "k51qabc" (:kotoba.deploy/ipns-name urls)))
    (is (= "ipns://k51qabc" (:kotoba.deploy/ipns-url urls)))
    (is (= "ipfs://bafkreidemo" (:kotoba.deploy/ipfs-url urls)))
    (is (= "https://murakumo.cloud/ipns/k51qabc"
           (:kotoba.deploy/public-url urls))))
  (is (nil? (deploy-adapter/public-urls "" "bafkreidemo")))
  (is (nil? (deploy-adapter/public-urls nil "bafkreidemo"))))

(deftest public-urls-support-independent-gateways-and-ipns-only
  (let [gateways (deploy-adapter/parse-ipns-gateways
                  "https://gw1.example/, https://gw2.example")
        urls (deploy-adapter/public-urls "k51qabc" "bafkreidemo" gateways)]
    (is (= ["https://gw1.example" "https://gw2.example"] gateways))
    (is (= ["https://gw1.example/ipns/k51qabc"
            "https://gw2.example/ipns/k51qabc"]
           (:kotoba.deploy/gateway-urls urls)))
    (is (= "https://gw1.example/ipns/k51qabc"
           (:kotoba.deploy/public-url urls))))
  (let [urls (deploy-adapter/public-urls
              "k51qabc" "bafkreidemo"
              (deploy-adapter/parse-ipns-gateways "ipns-only"))]
    (is (= "ipns://k51qabc" (:kotoba.deploy/ipns-url urls)))
    (is (= [] (:kotoba.deploy/gateway-urls urls)))
    (is (nil? (:kotoba.deploy/public-url urls)))))

(def control-plane-profile
  {:schema deploy-adapter/control-plane-schema
   :roles {:control {:origin "https://api.kotoba.cloud"}
           :identity {:origin "https://auth.kotoba.cloud"
                      :rpId "auth.kotoba.cloud"}
           :storage {:origin "https://kotobase.net"}
           :compute {:origin "https://api.murakumo.cloud"
                     :publicOrigin "https://murakumo.cloud"}
           :agentWork {:origin "https://itonami.cloud"}}
   :deploy {:hostedApply false}})

(deftest control-plane-profile-pins-domain-roles
  (is (:ok? (deploy-adapter/validate-control-plane-profile control-plane-profile)))
  (is (= [:authority-origin-mismatch]
         (:problems
          (deploy-adapter/validate-control-plane-profile
           (assoc-in control-plane-profile [:roles :storage :origin]
                     "https://api.murakumo.cloud")))))
  (is (= [:hosted-apply-overclaim]
         (:problems
          (deploy-adapter/validate-control-plane-profile
           (assoc-in control-plane-profile [:deploy :hostedApply] true))))))

(deftest parse-target-rejects-deno-cloudflare-vercel
  (doseq [target ["https://deno.com"
                  "deno:project"
                  "cloudflare:pages"
                  "cf:workers"
                  "vercel:prod"]]
    (is (= :deploy/unknown-target-scheme
           (:error (deploy-adapter/parse-target "pkg.edn" target))))))
