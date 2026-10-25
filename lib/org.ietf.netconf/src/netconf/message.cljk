(ns netconf.message
  "RFC 6241 NETCONF Protocol — message layer: <hello>, <rpc>, <rpc-reply>,
  <rpc-error>. XML shape built/parsed via kotoba-lang/xml's hiccup<->XML
  codec (`xml.core`/`xml.parse`); this namespace only shapes the fixed
  message-layer envelope RFC 6241 §4 and §8.1 define.

  Uses `xml.core/compact` (no inserted whitespace), not `xml.core/xml`
  (indented): every element this namespace builds either wraps other
  elements or wraps a single VALUE that is compared, not displayed — a
  capability URI, a message-id, a session-id, an error-tag. That is
  exactly the case `xml.core`'s own README calls out for `compact` over
  `xml` (its EPP clTRID example): indentation whitespace inserted into
  `<capability>...</capability>`'s text content would make it compare
  unequal to the same URI sent without it, e.g. against
  RFC 6241 §8.1's own `<hello>` example, which happens to indent
  `<capability>` onto its own line.

  Operation-payload content (<filter>/<config>/<data>) is YANG-modeled
  (RFC 7950) and OPAQUE to this codec — see netconf.operations and the
  README's YANG-scoping note. Callers pass already-built hiccup for it;
  this namespace never inspects it."
  (:require [kotoba.lang.text :as str]
            [xml.core :as xml]
            [xml.parse :as parse]))

(def netconf-ns
  "RFC 6241 §3.1 — the NETCONF XML namespace. Distinct from the base
  CAPABILITY URI below, which is a different string in a different URN
  scheme (RFC 6241 §8, easy to conflate)."
  "urn:ietf:params:xml:ns:netconf:base:1.0")

(def base-capability-1-1
  "RFC 6241 §8.1: \"Each peer MUST send at least the base NETCONF
  capability, urn:ietf:params:netconf:base:1.1.\" This is the capability
  whose presence on BOTH sides selects RFC 6242 §4.2 chunked framing
  (netconf.framing) over the deprecated §4.3 end-of-message framing."
  "urn:ietf:params:netconf:base:1.1")

;; RFC 6241 §4.3 — the four error-type / conceptual-layer values.
(def error-types #{"transport" "rpc" "protocol" "application"})

;; RFC 6241 §4.3 — error-severity. ("Note that there are no <error-tag>
;; values defined in this document that utilize the \"warning\"
;; enumeration. This is reserved for future use.")
(def error-severities #{"error" "warning"})

;; RFC 6241 Appendix A — the complete, normative error-tag enumeration
;; (also mirrored in the ErrorTag simpleType of Appendix B's XSD).
(def error-tags
  #{"in-use" "invalid-value" "too-big" "missing-attribute" "bad-attribute"
    "unknown-attribute" "missing-element" "bad-element" "unknown-element"
    "unknown-namespace" "access-denied" "lock-denied" "resource-denied"
    "rollback-failed" "data-exists" "data-missing" "operation-not-supported"
    "operation-failed" "partial-operation" "malformed-message"})

(defn- blank? [s] (or (nil? s) (str/blank? s)))

(defn- parse-int-str [s]
  #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10)))

;; ------------------------------------------------------------- hello

(defn hello->xml
  "RFC 6241 §8.1 <hello>. `h` is
  {:netconf/capabilities [uri ...], :netconf/session-id nil-or-pos-int}.
  A client's <hello> MUST NOT include <session-id>; a server's MUST —
  this function doesn't know which peer it's building for, so it just
  includes <session-id> iff you pass one. Throws (caller-controlled
  input) if `capabilities` is empty; §8.1 requires at least the base
  capability."
  [{:keys [netconf/capabilities netconf/session-id]}]
  (when (empty? capabilities)
    (throw (ex-info "hello requires at least one capability (RFC 6241 §8.1)"
                     {:netconf/error :hello-missing-capabilities})))
  (xml/compact
    (cond-> [:hello {"xmlns" netconf-ns}
             (into [:capabilities] (map (fn [c] [:capability c])) capabilities)]
      session-id (conj [:session-id (str session-id)]))))

(defn xml->hello
  "Never throws. [:ok {:netconf/capabilities [...] :netconf/session-id
  n-or-nil}] or [:error kw]."
  [xml-str]
  (let [el (parse/parse xml-str)]
    (cond
      (not (vector? el)) [:error :hello-not-an-element]
      (not= :hello (parse/el-tag el)) [:error :hello-wrong-tag]
      :else
      (let [caps-el (parse/find-child el :capabilities)
            caps (mapv (comp str/trim parse/el-text) (parse/find-children caps-el :capability))
            sess-el (parse/find-child el :session-id)]
        (if (empty? caps)
          [:error :hello-missing-capabilities]
          [:ok {:netconf/capabilities caps
                :netconf/session-id (when sess-el (parse-int-str (str/trim (parse/el-text sess-el))))}])))))

;; --------------------------------------------------------------- rpc

(defn rpc->xml
  "RFC 6241 §4.1 <rpc>. `operation-el` is an already-built hiccup element
  for the operation being invoked — netconf.operations builds these for
  the nine standard operations; any other operation-specific element can
  be passed the same way. Throws if `message-id` is blank: §4.1's XSD
  makes the attribute mandatory."
  [message-id operation-el]
  (when (blank? message-id)
    (throw (ex-info "rpc requires a non-blank message-id (RFC 6241 §4.1)"
                     {:netconf/error :rpc-missing-message-id})))
  (xml/compact [:rpc {"message-id" message-id "xmlns" netconf-ns} operation-el]))

(defn xml->rpc
  "Never throws. [:ok {:netconf/message-id s :netconf/operation el}] or
  [:error kw]. `:netconf/operation` is the opaque parsed operation
  element (e.g. [:get-config ...]) — pass it to netconf.operations if you
  want it interpreted, or walk it yourself."
  [xml-str]
  (let [el (parse/parse xml-str)]
    (cond
      (not (vector? el)) [:error :rpc-not-an-element]
      (not= :rpc (parse/el-tag el)) [:error :rpc-wrong-tag]
      :else
      (let [mid (parse/el-attr el "message-id")
            op (first (parse/el-elements el))]
        (cond
          (blank? mid) [:error :rpc-missing-message-id]
          (nil? op) [:error :rpc-missing-operation]
          :else [:ok {:netconf/message-id mid :netconf/operation op}])))))

;; --------------------------------------------------------- rpc-reply

(defn- error->hiccup
  "RFC 6241 §4.3 <rpc-error>: error-type/error-tag/error-severity are
  mandatory (in that order, per Appendix B's XSD sequence); the rest are
  optional. `error-info` is opaque hiccup — Appendix A's per-error-tag
  mandatory content (e.g. lock-denied's <session-id>) is the caller's to
  build, since it varies by error-tag and this namespace doesn't
  special-case individual tags."
  [{:keys [netconf/error-type netconf/error-tag netconf/error-severity
           netconf/error-app-tag netconf/error-path netconf/error-message
           netconf/error-info]}]
  (when-not (contains? error-types error-type)
    (throw (ex-info "unknown error-type (RFC 6241 §4.3)"
                     {:netconf/error :rpc-error-unknown-error-type :error-type error-type})))
  (when-not (contains? error-tags error-tag)
    (throw (ex-info "unknown error-tag (RFC 6241 Appendix A)"
                     {:netconf/error :rpc-error-unknown-error-tag :error-tag error-tag})))
  (when-not (contains? error-severities error-severity)
    (throw (ex-info "unknown error-severity (RFC 6241 §4.3)"
                     {:netconf/error :rpc-error-unknown-error-severity :error-severity error-severity})))
  (into [:rpc-error]
        (remove nil?)
        [[:error-type error-type]
         [:error-tag error-tag]
         [:error-severity error-severity]
         (when error-app-tag [:error-app-tag error-app-tag])
         (when error-path [:error-path error-path])
         (when error-message [:error-message error-message])
         error-info]))

(defn rpc-reply-ok->xml
  "RFC 6241 §4.2 <rpc-reply> carrying <ok/> — the positive response most
  operations (edit-config, copy-config, delete-config, lock, unlock,
  close-session, kill-session) use."
  [message-id]
  (when (blank? message-id)
    (throw (ex-info "rpc-reply requires a non-blank message-id (RFC 6241 §4.2)"
                     {:netconf/error :rpc-reply-missing-message-id})))
  (xml/compact [:rpc-reply {"message-id" message-id "xmlns" netconf-ns} [:ok]]))

(defn rpc-reply-data->xml
  "RFC 6241 §7.1/§7.7 <rpc-reply> carrying <data>...</data> — the
  positive response for get-config/get. `data-el` is opaque,
  caller-supplied hiccup (YANG-modeled content, out of scope — see
  README)."
  [message-id data-el]
  (when (blank? message-id)
    (throw (ex-info "rpc-reply requires a non-blank message-id (RFC 6241 §4.2)"
                     {:netconf/error :rpc-reply-missing-message-id})))
  (xml/compact [:rpc-reply {"message-id" message-id "xmlns" netconf-ns} [:data data-el]]))

(defn rpc-reply-error->xml
  "RFC 6241 §4.2/§4.3 <rpc-reply> carrying one or more <rpc-error>
  elements. `errors` is a seq of maps shaped for `error->hiccup` above."
  [message-id errors]
  (when (blank? message-id)
    (throw (ex-info "rpc-reply requires a non-blank message-id (RFC 6241 §4.2)"
                     {:netconf/error :rpc-reply-missing-message-id})))
  (when (empty? errors)
    (throw (ex-info "an error rpc-reply needs >= 1 rpc-error (RFC 6241 §4.3: \"A server MUST return an <rpc-error> element if any error conditions occur\")"
                     {:netconf/error :rpc-reply-empty-errors})))
  (xml/compact (into [:rpc-reply {"message-id" message-id "xmlns" netconf-ns}]
                      (map error->hiccup) errors)))

(defn- xml->rpc-error [el]
  {:netconf/error-type (parse/el-text (parse/find-child el :error-type))
   :netconf/error-tag (parse/el-text (parse/find-child el :error-tag))
   :netconf/error-severity (parse/el-text (parse/find-child el :error-severity))
   :netconf/error-app-tag (some-> (parse/find-child el :error-app-tag) parse/el-text)
   :netconf/error-path (some-> (parse/find-child el :error-path) parse/el-text)
   :netconf/error-message (some-> (parse/find-child el :error-message) parse/el-text)
   :netconf/error-info (parse/find-child el :error-info)})

(defn xml->rpc-reply
  "Never throws. [:ok {:netconf/message-id s-or-nil :netconf/result r}]
  or [:error kw], where `r` is :ok, {:netconf/data el}, or
  {:netconf/errors [error-map ...]}.

  `:netconf/message-id` may be nil: RFC 6241 §4.3's own example shows the
  one case where a server legitimately omits it (replying to an <rpc>
  that itself omitted message-id) — \"only in this case is it acceptable
  for the NETCONF peer to omit the message-id attribute in the
  <rpc-reply> element\"."
  [xml-str]
  (let [el (parse/parse xml-str)]
    (cond
      (not (vector? el)) [:error :rpc-reply-not-an-element]
      (not= :rpc-reply (parse/el-tag el)) [:error :rpc-reply-wrong-tag]
      :else
      (let [mid (parse/el-attr el "message-id")
            errs (parse/find-children el :rpc-error)
            data-el (parse/find-child el :data)
            ok-el (parse/find-child el :ok)]
        (cond
          (some? ok-el) [:ok {:netconf/message-id mid :netconf/result :ok}]
          (seq errs) [:ok {:netconf/message-id mid
                            :netconf/result {:netconf/errors (mapv xml->rpc-error errs)}}]
          (some? data-el) [:ok {:netconf/message-id mid :netconf/result {:netconf/data data-el}}]
          :else [:error :rpc-reply-empty-body])))))
