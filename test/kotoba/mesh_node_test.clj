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

(def ^:private test-port 18099)
(def ^:private server (atom nil))

(defn- with-server [f]
  (let [wasm (mesh-node/compile-route "src/mesh_drama_profile.kotoba"
                                      "src/mesh_drama_profile_policy.edn")]
    (reset! server (mesh-node/start! {"drama-profile" wasm} test-port)))
  (try (f) (finally (.stop ^com.sun.net.httpserver.HttpServer @server 0))))

(use-fixtures :once with-server)

(defn- http-get [path]
  (let [req (-> (HttpRequest/newBuilder (URI/create (str "http://localhost:" test-port path)))
                (.GET) (.build))]
    (.send (HttpClient/newHttpClient) req (HttpResponse$BodyHandlers/ofString))))

(defn- http-post [path]
  (let [req (-> (HttpRequest/newBuilder (URI/create (str "http://localhost:" test-port path)))
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
    (is (= 404 (.statusCode resp)))))
