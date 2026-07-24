(ns kotoba.supply-chain-test
  (:require [clojure.java.io :as io]
            [clojure.test :refer [deftest is testing]]
            [kotoba.supply-chain :as supply]))

(defn- workspace-siblings-present?
  "True only when every non-self product's dependency descriptor is checked
   out next to this repo. The release supply-chain gate reads sibling repos
   at `../<product>`; hosted per-PR CI does not lay out the workspace, so
   `release-ready?` is a workspace/release-time property, not a unit-test
   one -- assert it only where it can actually hold."
  []
  (every? (fn [[id root]]
            (or (= :kotoba id) (.isFile (io/file root "deps.edn"))))
          supply/product-paths))

(deftest manifest-binds-the-entire-scope-and-is-well-formed
  (let [manifest (supply/read-manifest)
        report (supply/report manifest)]
    (testing "every scoped product is present in the manifest"
      (is (= #{:kotoba :kototama :aiueos :kotoba-lang :kotobase}
             (set (map :product/id (:supply-chain/products report)))))
      (is (empty? (:supply-chain/errors report))
          "no :supply-chain/product-scope error"))
    (testing "each manifest entry pins a well-formed revision and digest"
      (doseq [{:keys [product/id source/revision dependency/sha256]}
              (:products manifest)]
        (is (re-matches #"[0-9a-f]{40}" revision)
            (str id " source/revision is a 40-hex commit"))
        (is (re-matches #"[0-9a-f]{64}" sha256)
            (str id " dependency/sha256 is a 64-hex digest"))))))

(deftest local-root-detection-flags-only-workspace-overrides
  (is (not (supply/local-root? {:git/sha "immutable"})))
  (is (true? (supply/local-root? {:local/root "../workspace-only"})))
  (is (true? (supply/local-root? {:deps {:some/dep {:local/root "../x"}}}))))

(deftest release-ready-holds-in-a-real-workspace
  (let [report (supply/report (supply/read-manifest))]
    (if (workspace-siblings-present?)
      (is (:supply-chain/release-ready? report) (pr-str report))
      (testing "without a full workspace the gate stays fail-closed, never falsely ready"
        (is (false? (:supply-chain/release-ready? report))
            "a product whose sibling descriptor is absent must not read as release-ready")))))

(deftest dependency-digest-and-source-revision-fail-closed
  (let [manifest (supply/read-manifest)
        bad (update-in manifest [:products 0 :dependency/sha256]
                       #(str "0" (subs % 1)))
        report (supply/report bad)]
    (is (false? (:supply-chain/release-ready? report)))
    (is (contains? (set (:supply-chain/errors (first (:supply-chain/products report))))
                   :supply-chain/dependency-digest))))
