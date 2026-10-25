(ns arrow.ipld-test
  "An Arrow file that is not one object.

  The claim is not that FBL works -- io-ipld tests that. It is that the two
  range contracts compose: a real pyarrow-written file, chunked into
  content-addressed blocks, must answer every query identically to the same
  file read directly, and must do so without materialising the file.

  The fixture is deliberately the same one `reader-test` uses, from pyarrow,
  because a fixture this repo generated would test the composition against
  its own idea of the format."
  (:require [arrow.ipld :as aipld]
            [arrow.reader-test :as rt]
            [arrow.source :as asrc]
            [clojure.test :refer [deftest is testing]]
            [columnar.bytes :as bytes]
            [columnar.plan :as plan]
            [columnar.source :as csrc]
            [ipld.fbl :as fbl]))

(defn- err [f]
  (try (f) nil
       (catch #?(:clj Exception :cljs :default) e (:type (ex-data e)))))

(defn- chunked
  "The fixture stored as an FBL, plus a getter recording DISTINCT blocks read.

  Distinct rather than a call count on purpose: the root is legitimately
  re-read once per range, so counting calls conflates how many blocks this
  needs with how many times it asked. The first is the claim."
  [bytes chunk-size]
  (let [{:keys [root blocks]} (fbl/build bytes chunk-size)
        m (into {} (map (juxt :cid :bytes)) blocks)
        touched (atom #{})]
    {:root root :touched touched :block-count (count blocks)
     :get-fn (fn [cid] (swap! touched conj cid) (get m cid))}))

;; ── the composition ──────────────────────────────────────────────────────────

(deftest a_chunked_arrow_file_reads_identically_to_a_whole_one
  (doseq [chunk-size [64 512 4096]]
    (testing (str "chunk size " chunk-size)
      (let [raw @rt/plain
            {:keys [root get-fn]} (chunked raw chunk-size)
            direct (asrc/open (bytes/source raw))
            over-ipld (aipld/open get-fn root)]
        (is (= (csrc/-schema direct) (csrc/-schema over-ipld)))
        (is (= (csrc/-chunk-count direct) (csrc/-chunk-count over-ipld)))
        (doseq [column (csrc/-schema direct)
                chunk (range (csrc/-chunk-count direct))]
          (is (= (csrc/-read-column direct chunk column)
                 (csrc/-read-column over-ipld chunk column))
              (str "column " column " chunk " chunk)))))))

(deftest a_query_over_the_chunked_file_returns_the_same_rows
  (let [raw @rt/plain
        {:keys [root get-fn]} (chunked raw 512)
        column (first (csrc/-schema (asrc/open (bytes/source raw))))]
    (is (= (plan/scan (asrc/open (bytes/source raw)) {:columns [column]})
           (plan/scan (aipld/open get-fn root) {:columns [column]})))))

;; ── it does not materialise the file ─────────────────────────────────────────

(deftest reading_a_column_does_not_fetch_every_block
  ;; The reason both halves exist. Arrow fetches the ranges it needs; FBL
  ;; fetches the leaves those ranges overlap. If either gave up, this number
  ;; would be the block count.
  ;;
  ;; The chunk size has to be fine enough for the claim to be falsifiable:
  ;; this fixture is ~2 KB, so at 512-byte chunks there are five blocks and a
  ;; column legitimately spans most of them. Measured 2026-09-06 at 64 bytes:
  ;; 7 of 32 distinct blocks. A coarser size does not disprove pruning, it
  ;; just cannot show it -- which is a property of the test, not the code.
  (let [raw @rt/plain
        {:keys [root get-fn touched block-count]} (chunked raw 64)
        src (aipld/open get-fn root)
        column (first (csrc/-schema src))]
    (reset! touched #{})
    (csrc/-read-column src 0 column)
    (is (pos? (count @touched)) "it did read something")
    (is (< (count @touched) (quot block-count 2))
        (str "touched " (count @touched) " of " block-count
             " blocks -- a whole-file read would be all of them"))))

(deftest the_footer_alone_costs_a_fraction_of_the_object
  (let [raw @rt/plain
        {:keys [root get-fn touched block-count]} (chunked raw 64)]
    (reset! touched #{})
    (aipld/open get-fn root)
    (is (< (count @touched) (quot block-count 2))
        "opening parses the footer from two ranges, not the whole file")))

;; ── the refusals survive the composition ─────────────────────────────────────

(deftest a_missing_block_refuses_rather_than_shifting_every_offset
  ;; Arrow computes buffer offsets from the footer and does not re-check the
  ;; width it got back. A layout that returned fewer bytes would shift every
  ;; field after it and still parse, which is why FBL refuses instead.
  (let [raw @rt/plain
        {:keys [root blocks]} (fbl/build raw 512)
        m (into {} (map (juxt :cid :bytes)) blocks)
        ;; drop one leaf that is not the root
        victim (:cid (first blocks))
        holey (fn [cid] (when-not (= cid victim) (get m cid)))]
    (is (= :ipld/missing-block
           (err #(let [src (aipld/open holey root)]
                   (doseq [c (csrc/-schema src)]
                     (csrc/-read-column src 0 c))))))))

(deftest the_source_reports_the_size_without_reading_the_object
  (let [raw @rt/plain
        {:keys [root get-fn touched block-count]} (chunked raw 64)]
    (reset! touched #{})
    (is (= (count raw) (bytes/-size (aipld/source get-fn root))))
    (is (= 1 (count @touched)) "size reads the root only, never a leaf")))

;; ── the copy boundary is not misreported from below ──────────────────────────

(deftest this_source_does_not_claim_to_borrow
  ;; A range spanning two leaves is not contiguous in any buffer. Implementing
  ;; the borrow protocol and copying underneath would make the copy boundary
  ;; invisible at the layer that exists to make it visible.
  (let [raw @rt/plain
        {:keys [root get-fn]} (chunked raw 512)]
    (is (not (satisfies? bytes/IByteViewSource (aipld/source get-fn root)))
        "declining the protocol is the honest answer, not an omission"))
  (testing "the distinction is still available from fbl directly"
    (let [{:keys [root get-fn]} (chunked @rt/plain 512)]
      (is (= :borrowed-leaf (:copy-boundary (fbl/read-range get-fn root 0 16))))
      (is (= :assembled (:copy-boundary (fbl/read-range get-fn root 500 600)))))))
