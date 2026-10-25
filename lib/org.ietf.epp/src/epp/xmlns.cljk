(ns epp.xmlns
  "EPP XML namespaces, and the resolution step every EPP parser needs and most
  skip.

  `xml.parse` turns `<domain:create>` into `:domain/create` by splitting on the
  colon — the prefix becomes the keyword's namespace. That is the right shape,
  but the prefix is *not* the identity. XML namespaces are identified by URI,
  and the prefix bound to a URI is the document author's free choice. All three
  of these are the same element:

      <domain:create xmlns:domain=\"urn:ietf:params:xml:ns:domain-1.0\">
      <d:create      xmlns:d=\"urn:ietf:params:xml:ns:domain-1.0\">
      <create        xmlns=\"urn:ietf:params:xml:ns:domain-1.0\">

  A parser that matches on `:domain/create` accepts the first and silently fails
  to recognize the other two. Registrars really do send the second — a client
  library that shortens prefixes is not doing anything wrong — and the third is
  what you get from any generator that uses default namespaces. The failure is
  quiet: the command parses as XML, matches nothing, and comes back as \"unknown
  command\" to a registrar whose XML is perfectly valid.

  So `canonicalize` resolves prefixes against the `xmlns` declarations actually
  in scope and rewrites every tag to a canonical keyword. After it runs, EPP
  core elements are unprefixed (`:command`, `:login`) and object mappings carry
  a fixed namespace (`:domain/create`, `:host/info`), whatever the wire said.

  Namespace declarations are scoped: a binding on an element applies to that
  element and its descendants, and an inner declaration shadows an outer one.
  That is why this is a walk with an environment and not a lookup of the root's
  attributes."
  (:require [kotoba.lang.text :as str]
            [xml.parse :as xp]))

(def uris
  "URI → canonical keyword namespace. `nil` means \"unprefixed\" — the EPP core
  namespace, whose elements are the frame structure itself."
  {"urn:ietf:params:xml:ns:epp-1.0"      nil
   "urn:ietf:params:xml:ns:eppcom-1.0"   "eppcom"
   "urn:ietf:params:xml:ns:domain-1.0"   "domain"
   "urn:ietf:params:xml:ns:host-1.0"     "host"
   "urn:ietf:params:xml:ns:contact-1.0"  "contact"
   "urn:ietf:params:xml:ns:rgp-1.0"      "rgp"
   "urn:ietf:params:xml:ns:secDNS-1.1"   "secDNS"})

(def canonical-prefix
  "The prefix this library *emits* for each canonical namespace. Emitting a
  stable prefix is not required by the spec but makes responses diffable and
  makes fixture tests meaningful."
  {"domain" "domain" "host" "host" "contact" "contact"
   "rgp" "rgp" "secDNS" "secDNS" "eppcom" "eppcom"})

(def epp-uri "urn:ietf:params:xml:ns:epp-1.0")

(def object-uri
  "Canonical namespace → the URI to declare when emitting it."
  (into {} (map (fn [[u p]] [p u])) (dissoc uris epp-uri)))

(defn- declarations
  "The `xmlns` bindings introduced by this element: prefix (or nil for the
  default namespace) → URI."
  [el]
  (reduce-kv (fn [m k v]
               (cond
                 (= k "xmlns") (assoc m nil v)
                 (str/starts-with? k "xmlns:") (assoc m (subs k 6) v)
                 :else m))
             {}
             (xp/el-attrs el)))

(defn- rename
  "Rewrite one tag against the in-scope bindings. An unrecognized URI keeps the
  document's own prefix rather than being dropped — an extension this library
  does not know about should survive to a caller that might, and losing it
  silently is worse than passing it through."
  [tag env]
  (let [prefix (namespace tag)
        local (name tag)
        uri (get env prefix)]
    (if (and uri (contains? uris uri))
      (if-let [ns' (get uris uri)] (keyword ns' local) (keyword local))
      ;; No binding in scope: an unprefixed tag inside an EPP document is EPP
      ;; core by convention even when the declaration is missing, which some
      ;; clients do omit. A prefixed one keeps its prefix.
      (if prefix tag (keyword local)))))

(defn canonicalize
  "Resolve namespace prefixes throughout a parsed tree and strip the `xmlns`
  attributes, which have done their job. Text nodes pass through untouched."
  ([el] (canonicalize el {}))
  ([el env]
   (if-not (vector? el)
     el
     (let [env' (merge env (declarations el))
           attrs (into {} (remove (fn [[k _]] (or (= k "xmlns")
                                                  (str/starts-with? k "xmlns:"))))
                       (xp/el-attrs el))
           children (mapv #(canonicalize % env') (xp/el-children el))]
       (into (if (seq attrs)
               [(rename (xp/el-tag el) env') attrs]
               [(rename (xp/el-tag el) env')])
             children)))))

(defn parse
  "Parse an EPP frame's XML and canonicalize it in one step. This is the only
  entry point callers should use — a tree that skipped `canonicalize` matches
  by prefix and will disagree with itself across clients."
  [xml-string]
  (some-> (xp/parse xml-string) canonicalize))
