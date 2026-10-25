(ns amqp.performative
  "The nine AMQP 1.0 performatives and the `error` composite type —
  OASIS AMQP Version 1.0 Part 2 (Transport) §2.7 \"Performatives\" and
  §2.8.14 \"Error\". Every field name, type and mandatory/optional/default
  flag below is transcribed **verbatim** from the spec's own `<field>`
  tables, fetched and grepped out of
  docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-transport-v1.0-os.html
  on 2026-08-30 — not recalled from memory, because a performative's field
  *order* is its wire encoding (each performative is a described list, and
  a list is positional) and a misremembered order produces a codec that
  agrees with itself and nothing else.

  A performative is `0x00 descriptor list`: a described type (`amqp.types`)
  whose descriptor is the performative's code as a `ulong` (encoded
  compactly, as `smallulong`, by `amqp.types/encode-value` since every code
  here is under 256) and whose value is a `list` of the fields below, in
  order, trailing nulls omitted. §2.8.14, `SIZE — CATEGORY — DESCRIPTOR —
  Header for each performative` gives the codes; §2.7.1 through §2.7.9 give
  the field lists.

  ## What `source`, `target` and `delivery-state` are here

  `attach`'s `source`/`target` fields and `transfer`/`disposition`'s
  `state` field are each themselves a described-type value defined
  elsewhere in the spec (§3.5.3 Source, §3.5.4 Target, §3.4 Delivery
  State) with their own multi-field composite layouts — a second full
  subsystem this library does not model. They are passed through
  **opaquely**: give `encode-performative` an already-built `amqp.types`
  tagged value (typically a `:described` one) or `nil`, and
  `decode-performative` gives one back the same way. A caller that needs a
  real `source`/`target` builds it with `amqp.types/encode-value` directly,
  using descriptor `[:ulong 0x28]` (source) or `[:ulong 0x29]` (target).
  That is a real, bounded gap — not a hidden one."
  (:require [amqp.types :as t]))

;; ── field-spec tables ────────────────────────────────────────────────────
;; [field-key kind mandatory? default]. `kind` selects the native<->tagged
;; conversion in `field->tagged`/`tagged->field` below.

(def performative-specs
  {:open
   {:code 0x10
    :fields [[:container-id :string true nil]
             [:hostname :string false nil]
             [:max-frame-size :uint false 4294967295]
             [:channel-max :ushort false 65535]
             [:idle-time-out :uint false nil]
             [:outgoing-locales :symbol-array false []]
             [:incoming-locales :symbol-array false []]
             [:offered-capabilities :symbol-array false []]
             [:desired-capabilities :symbol-array false []]
             [:properties :fields-map false {}]]}
   :begin
   {:code 0x11
    :fields [[:remote-channel :ushort false nil]
             [:next-outgoing-id :uint true nil]
             [:incoming-window :uint true nil]
             [:outgoing-window :uint true nil]
             [:handle-max :uint false 4294967295]
             [:offered-capabilities :symbol-array false []]
             [:desired-capabilities :symbol-array false []]
             [:properties :fields-map false {}]]}
   :attach
   {:code 0x12
    :fields [[:name :string true nil]
             [:handle :uint true nil]
             [:role :role true nil]
             [:snd-settle-mode :ubyte false 2]
             [:rcv-settle-mode :ubyte false 0]
             [:source :opaque false nil]
             [:target :opaque false nil]
             [:unsettled :opaque false nil]
             [:incomplete-unsettled :boolean false false]
             [:initial-delivery-count :uint false nil]
             [:max-message-size :ulong false nil]
             [:offered-capabilities :symbol-array false []]
             [:desired-capabilities :symbol-array false []]
             [:properties :fields-map false {}]]}
   :flow
   {:code 0x13
    :fields [[:next-incoming-id :uint false nil]
             [:incoming-window :uint true nil]
             [:next-outgoing-id :uint true nil]
             [:outgoing-window :uint true nil]
             [:handle :uint false nil]
             [:delivery-count :uint false nil]
             [:link-credit :uint false nil]
             [:available :uint false nil]
             [:drain :boolean false false]
             [:echo :boolean false false]
             [:properties :fields-map false {}]]}
   :transfer
   {:code 0x14
    :fields [[:handle :uint true nil]
             [:delivery-id :uint false nil]
             [:delivery-tag :binary false nil]
             [:message-format :uint false nil]
             [:settled :boolean false nil]
             [:more :boolean false false]
             [:rcv-settle-mode :ubyte false nil]
             [:state :opaque false nil]
             [:resume :boolean false false]
             [:aborted :boolean false false]
             [:batchable :boolean false false]]}
   :disposition
   {:code 0x15
    :fields [[:role :role true nil]
             [:first :uint true nil]
             [:last :uint false nil]
             [:settled :boolean false false]
             [:state :opaque false nil]
             [:batchable :boolean false false]]}
   :detach
   {:code 0x16
    :fields [[:handle :uint true nil]
             [:closed :boolean false false]
             [:error :opaque false nil]]}
   :end
   {:code 0x17
    :fields [[:error :opaque false nil]]}
   :close
   {:code 0x18
    :fields [[:error :opaque false nil]]}
   :error
   {:code 0x1D
    :fields [[:condition :symbol true nil]
             [:description :string false nil]
             [:info :fields-map false {}]]}})

(def code->performative
  (into {} (map (fn [[k v]] [(:code v) k])) performative-specs))

;; ── native Clojure value <-> `amqp.types` tagged value ──────────────────────

(defn- native->fields-map-entry [v]
  (cond
    (string? v) [:string v]
    (boolean? v) [:boolean v]
    (and (integer? v) (>= v 0)) [:uint v]
    (integer? v) [:int v]
    :else [:string (str v)]))

(defn- field->tagged [kind v]
  (case kind
    :opaque v
    (when (some? v)
      (case kind
        :string [:string v]
        :symbol [:symbol v]
        :ushort [:ushort v]
        :uint [:uint v]
        :ulong [:ulong v]
        :ubyte [:ubyte v]
        :boolean [:boolean v]
        :binary [:binary v]
        :role [:boolean (= v :receiver)]
        :symbol-array (cond (empty? v) nil
                             (= 1 (count v)) [:symbol (first v)]
                             :else [:array :symbol (vec v)])
        :fields-map (if (empty? v) nil
                        [:map (mapv (fn [[k mv]] [[:symbol (name k)] (native->fields-map-entry mv)])
                                    v)])))))

(defn- tagged->field [kind tagged]
  (if (= kind :opaque)
    tagged
    (when tagged
      (let [[tag payload] tagged]
        (case kind
          (:string :symbol :ushort :uint :ulong :ubyte :boolean :binary) payload
          :role (if payload :receiver :sender)
          :symbol-array (case tag
                          :symbol [payload]
                          :array (let [[_ _elem items] tagged] (vec items))
                          [])
          :fields-map (if (= tag :map)
                        (into {} (map (fn [[[_ k] [_ v]]] [(keyword k) v])) payload)
                        {}))))))

;; ── encode / decode a performative's field list ─────────────────────────────

(defn encode-performative
  "`perf-key` is one of `:open :begin :attach :flow :transfer :disposition
  :detach :end :close`, `fields` a Clojure map keyed by the field names in
  `performative-specs`. Missing mandatory fields are a named error;
  trailing fields equal to `nil` (never given, or given as `nil`
  explicitly) are dropped from the end of the encoded list — the wire
  optimization the spec's own field tables describe as \"if the trailing
  fields are null, they may be omitted.\" Returns
  `{:status :ok :bytes […]}` or `{:status :error :reason …}`."
  [perf-key fields]
  (if-let [spec (get performative-specs perf-key)]
    (let [items (mapv (fn [[k kind mandatory? _default]]
                         (let [v (get fields k)]
                           (if (and mandatory? (nil? v))
                             {:status :error :reason :amqp/missing-mandatory-field
                              :performative perf-key :field k}
                             (or (field->tagged kind v) [:null]))))
                       (:fields spec))]
      (if-let [err (first (filter map? items))]
        err
        (let [trimmed (vec (reverse (drop-while #(= [:null] %) (reverse items))))
              list-r (t/encode-value [:list trimmed])]
          (if (= :error (:status list-r))
            list-r
            (t/encode-value [:described [:ulong (:code spec)] [:list trimmed]])))))
    {:status :error :reason :amqp/unknown-performative :performative perf-key}))

(defn decode-performative
  "Decodes one described-list value (already extracted by `amqp.frame` and
  `amqp.types/decode-value`) into `{:status :ok :performative perf-key
  :fields {…}}`. Rejects a descriptor that does not resolve to a known
  performative code (`:amqp/unknown-performative`) and a value that is not
  a `:described list` at all (`:amqp/not-a-performative`) — a `transfer`
  frame decoded as if it might be a bare `open` field list would silently
  read the wrong offsets into the wrong types."
  [tagged-value]
  (let [[tag descriptor value] tagged-value]
    (if (not= tag :described)
      {:status :error :reason :amqp/not-a-performative :got tag}
      (let [[dtag code] descriptor]
        (if (not (contains? #{:ulong :uint} dtag))
          {:status :error :reason :amqp/bad-descriptor :got dtag}
          (if-let [perf-key (code->performative code)]
            (let [[vtag items] value]
              (if (not= vtag :list)
                {:status :error :reason :amqp/not-a-performative :got vtag}
                (let [spec (get performative-specs perf-key)
                      n (count items)
                      decoded (map-indexed
                               (fn [i [k kind _mandatory? default]]
                                 [k (if (< i n)
                                      (let [item (nth items i)]
                                        (if (= item [:null]) default (tagged->field kind item)))
                                      default)])
                               (:fields spec))
                      fields (into {} decoded)
                      missing (first (filter (fn [[k kind mandatory? _]]
                                                (and mandatory? (nil? (get fields k))))
                                              (:fields spec)))]
                  (if missing
                    {:status :error :reason :amqp/missing-mandatory-field
                     :performative perf-key :field (first missing)}
                    {:status :ok :performative perf-key :fields fields}))))
            {:status :error :reason :amqp/unknown-performative :code code}))))))

;; ── §2.8.14 error, reused for `detach`/`end`/`close`/`disposition`'s
;;    `:error` field, which the field tables above pass through opaquely ────

(defn encode-error
  "`fields` is `{:condition \"amqp:not-found\" :description \"…\" :info
  {…}}` (`:condition` mandatory). Returns an `amqp.types` tagged value
  suitable to hand straight to `encode-performative` as a `:error` field, or
  a named error."
  [fields]
  (let [r (encode-performative :error fields)]
    (if (= :error (:status r)) r
        (t/decode-value (:bytes r) 0))))

(defn decode-error
  "Inverse of `encode-error` — takes the tagged value already produced by
  `amqp.types/decode-value` (e.g. from a decoded `:error` field) and
  returns `{:status :ok :fields {…}}` or a named error."
  [tagged-value]
  (let [r (decode-performative tagged-value)]
    (if (= :error (:status r)) r
        {:status :ok :fields (:fields r)})))
