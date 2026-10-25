(ns fix.message
  "Top-level entry point: `fix.codec` (framing/arithmetic) composed with
  `fix.groups` (repeating-group structuring), parameterized on a
  `fix.dictionary` value.

  `decode` needs the dictionary to know which NoXXX tags introduce a group.
  `encode` doesn't — a `{:group tag :entries [...]}` map in the input
  already says everything needed to flatten it — but takes `dict` anyway so
  a caller reaching for `message/encode`/`message/decode` as a pair never
  has to remember which direction actually consults it."
  (:require [fix.codec :as codec]
            [fix.groups :as groups]))

(defn encode
  "`{:begin-string :msg-type :body [...]}` (`:body` may interleave `[tag
  value]` pairs with `{:group tag :entries [...]}` maps) -> the same shape
  `fix.codec/encode` returns."
  [_dict {:keys [begin-string msg-type body]}]
  (codec/encode {:begin-string begin-string
                 :msg-type msg-type
                 :body (groups/flatten-body body)}))

(defn decode
  "Byte seq -> `[:ok {:begin-string :msg-type :body-length :check-sum
  :body}]` (`:body` group-structured per `dict`) or `[:error kw]`. Framing
  errors (`fix.codec`) are returned before group errors (`fix.groups`) are
  ever reached — an unverified CheckSum is never a safe input to group
  structuring."
  [dict bs]
  (let [[status m] (codec/decode bs)]
    (if (= status :error)
      [status m]
      (let [[gstatus gval] (groups/structure-body (:groups dict) (:body m))]
        (if (= gstatus :error)
          [:error gval]
          [:ok (assoc m :body gval)])))))
