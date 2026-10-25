(ns fix.codec
  "The tag=value/SOH wire codec: BeginString/BodyLength/MsgType header,
  CheckSum trailer, and everything in between as a flat, ungrouped sequence
  of `[tag value-string]` pairs. No data dictionary involved — this
  namespace doesn't know or care what tag 55 means, only where the header
  ends and the trailer begins, and whether the two arithmetic fields agree
  with the bytes actually on the wire. Repeating-group structure is
  `fix.groups`' job, one layer up in `fix.message`."
  (:require [fix.bytes :as b]
            [fix.checksum :as cksum]))

(defn- field+soh
  "`tag=value` followed by SOH, as a vector of bytes."
  [tag value]
  (conj (b/str->bytes (str tag "=" value)) b/soh))

(defn encode
  "`{:begin-string \"FIX.4.2\" :msg-type \"D\" :body [[tag value] ...]}` ->
  `{:begin-string :msg-type :body-length :check-sum :bytes}`. `:body` is
  the flat field list *after* MsgType and *before* CheckSum — this function
  supplies 35 itself from `:msg-type`, and computes both 9 and 10.

  Always succeeds: a `value` containing a stray SOH, or a tag that
  duplicates 8/9/35/10, produces a well-formed-looking frame that is wrong
  in a way this layer has no way to detect (it does not know which tags are
  reserved). That contract belongs to whoever constructs `:body` —
  `fix.message`, or a caller going around it on purpose."
  [{:keys [begin-string msg-type body]}]
  (let [body-bytes (into (vec (field+soh 35 msg-type))
                          (mapcat (fn [[t v]] (field+soh t v)))
                          body)
        len (cksum/body-length body-bytes)
        prefix (into (vec (field+soh 8 begin-string)) (field+soh 9 (str len)))
        without-checksum (into prefix body-bytes)
        cs (cksum/checksum without-checksum)]
    {:begin-string begin-string
     :msg-type msg-type
     :body-length len
     :check-sum cs
     :bytes (into without-checksum (field+soh 10 cs))}))

(defn decode
  "Byte seq -> `[:ok {:begin-string :msg-type :body-length :check-sum
  :body}]` (`:body` = flat `[tag value]` pairs, header/trailer peeled off)
  or `[:error kw]`. BodyLength and CheckSum are both **recomputed from the
  actual bytes and compared** — never trusted from the fields that claim
  them, which is the entire point of having them."
  [bs]
  (let [{:keys [fields trailing?]} (b/split-soh bs)
        n (count fields)]
    (cond
      trailing?
      [:error :fix/malformed-field]

      (< n 4)
      [:error :fix/missing-trailer]

      :else
      (let [parsed (mapv b/parse-field fields)]
        (if (some nil? parsed)
          [:error :fix/malformed-field]
          (let [[t8 begin-string] (nth parsed 0)
                [t9 body-len-str] (nth parsed 1)
                [t35 msg-type] (nth parsed 2)
                [t10 cs-str] (nth parsed (dec n))]
            (cond
              (not (and (= t8 8) (= t9 9) (= t35 35)))
              [:error :fix/invalid-header-order]

              (not= t10 10)
              [:error :fix/missing-trailer]

              :else
              (let [declared-len (b/parse-uint body-len-str)
                    ;; BodyLength's own range: fields[2..n-2] (MsgType
                    ;; through the last body field), each contributing its
                    ;; byte count plus the trailing SOH split-soh stripped.
                    body-field-bytes (subvec fields 2 (dec n))
                    actual-len (reduce + 0 (map (comp inc count) body-field-bytes))]
                (if (not= declared-len actual-len)
                  [:error :fix/body-length-mismatch]
                  ;; CheckSum's range: everything BodyLength counted, plus
                  ;; BeginString+BodyLength themselves — i.e. every field
                  ;; except CheckSum, fields[0..n-2].
                  (let [prefix-field-bytes (subvec fields 0 (dec n))
                        prefix-bytes (into [] (mapcat #(conj (vec %) b/soh)) prefix-field-bytes)
                        computed-cs (cksum/checksum prefix-bytes)]
                    (if (not= computed-cs cs-str)
                      [:error :fix/checksum-mismatch]
                      [:ok {:begin-string begin-string
                            :msg-type msg-type
                            :body-length actual-len
                            :check-sum cs-str
                            :body (subvec parsed 3 (dec n))}])))))))))))
