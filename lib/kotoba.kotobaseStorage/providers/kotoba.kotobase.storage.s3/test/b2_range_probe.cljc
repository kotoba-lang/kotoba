#!/usr/bin/env kbb
;; b2_range_probe.cljc — the one claim miniflare cannot settle: does a REAL
;; S3-compatible endpoint honour our Range header, byte for byte?
;;
;; `test/object_r2.cljk` in kotobase-storage-s3 checks the R2 conversion
;; against miniflare, which is an implementation of the R2 API and not R2.
;; The signed-HTTP client converts differently -- to an inclusive
;; `Range: bytes=a-b` -- and two things about that have never met a real
;; server:
;;
;;   1. whether the endpoint returns exactly the bytes we asked for
;;      (one too many is the first byte of the NEXT CAR frame, which parses);
;;   2. whether SigV4 with a `range` header among the signed headers is
;;      accepted at all, or 403s on canonicalisation.
;;
;; It packs a real CARv2, PUTs it, ranges one frame back out, verifies the
;; frame's CID, and deletes the object. Required environment variables:
;;   B2_PROBE_KEYCHAIN_SERVICE  exact Keychain service name (account = key id,
;;                              password = app key; never enumerated or printed)
;;   B2_PROBE_BUCKET            target B2 bucket name
;; Optional overrides: B2_PROBE_ENDPOINT, B2_PROBE_REGION.
;;
;;   B2_PROBE_KEYCHAIN_SERVICE=<service> B2_PROBE_BUCKET=<bucket> \
;;     kbb --backend sci --classpath "<cp>" b2_range_probe.cljc [--keep]

(ns b2-range-probe
  (:require ["node:child_process" :as cp]
            [kotoba.lang.text :as str]
            [ipld.car.bytes :as b]
            [ipld.car.v2 :as v2]
            [ipld.core :as ipld]
            [kotobase.storage.object :as object]
            [kotobase.storage.object-s3 :as objs3]
            [kotobase.storage.s3 :as s3]
            [multiformats.core :as mf]))

(defn- env [k]
  (let [v (aget (.-env js/process) k)]
    (when (and (string? v) (not (str/blank? v)))
      v)))

(def args (vec *command-line-args*))
(def keep? (some #{"--keep"} args))
(def service (env "B2_PROBE_KEYCHAIN_SERVICE"))
(def bucket (env "B2_PROBE_BUCKET"))
(def endpoint (or (env "B2_PROBE_ENDPOINT") "https://s3.us-west-004.backblazeb2.com"))
(def region (or (env "B2_PROBE_REGION") "us-west-004"))

(defn- require-config!
  "Fail closed before any Keychain lookup or network request when required
  environment variables are unset or blank."
  []
  (let [missing (cond-> []
                  (str/blank? service) (conj "B2_PROBE_KEYCHAIN_SERVICE")
                  (str/blank? bucket)  (conj "B2_PROBE_BUCKET"))]
    (when (seq missing)
      (js/console.error
       (str "FAIL: missing required environment variable(s): "
            (str/join ", " missing)
            "\nUsage: B2_PROBE_KEYCHAIN_SERVICE=<service> B2_PROBE_BUCKET=<bucket> "
            "kbb --backend sci --classpath \"<cp>\" b2_range_probe.cljc [--keep]"))
      (js/process.exit 2))))

(def failures (atom 0))
(defn check! [ok? label]
  (println (str (if ok? "  ok   " "  FAIL ") label))
  (when-not ok? (swap! failures inc)))

(defn- keychain
  "One item, by its exact service name. Never `dump-keychain`, never a scan:
  the safety floor forbids enumerating a vault to find something."
  []
  (let [meta (str (cp/execSync (str "security find-generic-password -s " service)
                               #js {:encoding "utf8" :stdio #js ["ignore" "pipe" "ignore"]}))
        acct (second (re-find #"\"acct\"<blob>=\"([^\"]+)\"" meta))
        pw (str/trim (str (cp/execSync (str "security find-generic-password -w -s " service)
                                       #js {:encoding "utf8" :stdio #js ["ignore" "pipe" "ignore"]})))]
    (when (or (str/blank? acct) (str/blank? pw))
      (println "FAIL: credential not resolvable from Keychain — refusing to guess")
      (js/process.exit 2))
    {:access-key acct :secret-key pw}))

(defn -main [& _]
  (require-config!)
  (let [{:keys [access-key secret-key]} (keychain)
        client (s3/signed-client {:endpoint endpoint :bucket bucket :region region
                                  :access-key access-key :secret-key secret-key})
        objects (objs3/open-objects {:client client :prefix "kotobase-range-probe"})
        blocks (mapv #(ipld/node->block {"probe" "range" "i" %}) (range 4))
        {:keys [bytes entries]} (v2/pack {:roots [] :blocks blocks})
        pack-cid (mf/cidv1-raw (b/as-bytes bytes))
        target (nth entries 2)]
    (println (str "packed " (count blocks) " blocks into " (b/bcount bytes)
                  " bytes as " pack-cid))
    (check! (object/range-read? objects)
            "the signed client declares AND implements :range-read")
    (-> (object/-put-object! objects pack-cid bytes)
        (.then (fn [_]
                 (println (str "PUT ok; ranging bytes=" (:file-offset target)
                               "-" (+ (:file-offset target) (:frame-length target) -1)))
                 (object/-get-object-range objects pack-cid
                                           (:file-offset target)
                                           (+ (:file-offset target)
                                              (:frame-length target)))))
        (.then (fn [got]
                 (check! (= (:frame-length target) (b/bcount got))
                         (str "the endpoint returned " (b/bcount got)
                              " bytes for a " (:frame-length target)
                              "-byte frame"))
                 ;; The real check: those bytes must BE the frame. A
                 ;; one-byte overshoot still parses -- as the wrong block.
                 (let [frame (v2/read-frame got 0)]
                   (check! (= (:cid target) (:cid frame))
                           (str "and they parse as the frame we asked for ("
                                (subs (:cid frame) 0 12) "…)"))
                   (check! (b/equal? (:bytes (nth blocks 2)) (:bytes frame))
                           "with byte-identical block contents"))))
        (.then (fn [_]
                 (if keep?
                   (js/Promise.resolve {:deleted? false :reason :kept})
                   (object/-delete-object! objects pack-cid))))
        (.then (fn [{:keys [deleted? reason]}]
                 (check! (or deleted? (= :kept reason))
                         (str "probe object removed (" (pr-str (or reason :deleted)) ")"))
                 (println (str "\nb2-range-probe: "
                               (if (zero? @failures) "all checks passed"
                                   (str @failures " FAILED"))))
                 (js/process.exit (if (zero? @failures) 0 1))))
        (.catch (fn [e]
                  (println (str "FAIL: " (.-message e) " " (pr-str (ex-data e))))
                  (js/process.exit 1))))))

(-main)
