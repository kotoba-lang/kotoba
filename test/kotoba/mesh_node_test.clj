(ns kotoba.mesh-node-test
  "ADR-2607082400 step 3 -- proves the murakumo -> cljc-node HTTP contract
  end-to-end: a REAL HTTP server (java.net.http.HttpClient on the wire, not
  an in-process handler call) serving the REAL compiled
  `mesh_drama_profile.kotoba` guest, exactly as an operator (or eventually
  murakumo) would reach it."
  (:require [clojure.test :refer [deftest is testing use-fixtures]]
            [kotoba.mesh-node :as mesh-node])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpRequest$BodyPublishers
            HttpResponse$BodyHandlers]))

(def ^:private server (atom nil))
(def ^:private test-port (atom nil))

(defn- with-server [f]
  (let [drama-wasm (mesh-node/compile-route "src/mesh_drama_profile.kotoba"
                                            "src/mesh_drama_profile_policy.edn")
        no-answer-wasm (mesh-node/compile-route "src/mesh_no_answer.kotoba"
                                                "src/mesh_drama_profile_policy.edn")]
  (let [started (mesh-node/start! {"drama-profile" drama-wasm
                                    "no-answer" no-answer-wasm}
                                   0)]
    (reset! server started)
    (reset! test-port (.getPort (.getAddress ^com.sun.net.httpserver.HttpServer started))))
  (try (f) (finally (.stop ^com.sun.net.httpserver.HttpServer @server 0)))))

(use-fixtures :once with-server)

(defn- http-get [path]
  (let [req (-> (HttpRequest/newBuilder (URI/create (str "http://localhost:" @test-port path)))
                (.GET) (.build))]
    (.send (HttpClient/newHttpClient) req (HttpResponse$BodyHandlers/ofString))))

(defn- http-post [path]
  (let [req (-> (HttpRequest/newBuilder (URI/create (str "http://localhost:" @test-port path)))
                (.POST (HttpRequest$BodyPublishers/noBody)) (.build))]
    (.send (HttpClient/newHttpClient) req (HttpResponse$BodyHandlers/ofString))))

(deftest health-answers-over-real-http
  (let [resp (http-get "/health")]
    (is (= 200 (.statusCode resp)))
    (is (= "{:status :ok :runtime :kotoba.wasm-exec}" (.body resp)))))

(deftest bound-route-dispatches-the-real-compiled-guest-over-real-http
  (testing "POST /mesh/http/drama-profile runs the same .kotoba guest
            mesh_drama_profile_test.clj proves in-process -- here over an
            actual HTTP round trip"
    (let [resp (http-post "/mesh/http/drama-profile")]
      (is (= 200 (.statusCode resp)))
      (is (= "[[\"minidrama.aozora.app\"]]" (.body resp))
          "the queried handle, read back out of guest memory, served as the HTTP response body"))))

(deftest unbound-route-answers-404-not-a-server-error
  (let [resp (http-post "/mesh/http/no-such-route")]
    (is (= 404 (.statusCode resp)))
    (is (= "{:error :route-not-bound}" (.body resp)))))

(deftest bound-route-with-nothing-to-answer-serves-204
  (testing "dispatch returns nil when the guest never calls kgraph-query (an
            assert-only guest has nothing to answer with, per dispatch's own
            docstring) -- previously untested since mesh_drama_profile.kotoba
            (the only fixture ever bound in this test file) always queries"
    (let [resp (http-post "/mesh/http/no-answer")]
      (is (= 204 (.statusCode resp)))
      (is (= "" (.body resp))))))

(deftest unmatched-method-or-path-falls-through-to-the-generic-404
  (testing ":not-found is a DIFFERENT 404 than :route-not-bound above -- the
            handler's final :else catch-all for anything that's neither
            GET /health nor POST /mesh/http/*, e.g. a GET to any other
            path. Previously untested; every existing test hit either the
            GET /health branch or a POST /mesh/http/* branch."
    (let [resp (http-get "/not-a-real-endpoint")]
      (is (= 404 (.statusCode resp)))
      (is (= "{:error :not-found}" (.body resp))))))

(deftest compile-route-throws-when-the-guest-fails-to-compile
  (testing "a route this node can't actually serve is a startup-time
            configuration error, not a per-request one (compile-route's own
            docstring) -- previously untested, only ever called with a
            guest known to compile cleanly"
    (let [err (try
                (mesh-node/compile-route "src/mesh_bad_route.kotoba"
                                         "src/mesh_drama_profile_policy.edn")
                nil
                (catch clojure.lang.ExceptionInfo e e))]
      (is (some? err))
      (is (= "src/mesh_bad_route.kotoba" (:kotoba.mesh-node/source (ex-data err))))
      (is (false? (get-in (ex-data err) [:kotoba.mesh-node/wasm :kotoba.wasm/ok?])))
      (is (= :unsupported-op
             (get-in (ex-data err) [:kotoba.mesh-node/wasm :kotoba.wasm/problems 0 :kotoba.wasm/problem]))))))

(deftest compile-route-throws-when-the-static-checker-rejects-the-route
  (testing "compile-route must run runtime/check BEFORE wasm-binary -- a
            route using a host-import (kgraph-assert!) its own policy
            doesn't grant must be rejected at the static-check stage, not
            silently compiled and shipped (the bypass this test guards
            against: wasm-binary's own POLICY argument is not itself a
            guard, so a caller that skipped `check` got a working binary
            for a program the policy never actually authorized). Reuses
            mesh_drama_profile.kotoba (needs :graph/kotoba) against
            demo_policy.edn (grants only :notify/show, not :graph/kotoba)."
    (let [err (try
                (mesh-node/compile-route "src/mesh_drama_profile.kotoba"
                                         "src/demo_policy.edn")
                nil
                (catch clojure.lang.ExceptionInfo e e))]
      (is (some? err))
      (is (= "src/mesh_drama_profile.kotoba" (:kotoba.mesh-node/source (ex-data err))))
      (is (false? (get-in (ex-data err) [:kotoba.runtime/result :kotoba.runtime/ok?]))
          "must be rejected by the static checker, not left to wasm-binary")
      (is (some #(= :capability-not-granted (:kotoba.runtime/problem %))
                (get-in (ex-data err) [:kotoba.runtime/result :kotoba.runtime/problems]))))))
