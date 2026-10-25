(ns rdap.jcard
  "jCard (RFC 7095) — vCard 4.0 in JSON — for RDAP `entity` objects.

  The shape is unusual enough to get wrong silently:

      [\"vcard\", [ [name, parameters, type, value], … ]]

  A two-element array whose first element is the literal string `\"vcard\"` and
  whose second is an array of four-element property arrays. Every property is
  four elements even when three of them are trivial: `parameters` is `{}` when
  there are none, and `type` names the vCard value type (`\"text\"`, `\"uri\"`)
  rather than being optional.

  Two rules that are load-bearing:

  - **`version` must be first and must be `\"4.0\"`** (RFC 7095 §3.3). A jCard
    without it is not a jCard, and parsers reject the whole entity rather than
    the property.
  - **`adr` has a seven-element value array** in a fixed order: post office
    box, extended address, street, locality, region, postal code, country.
    Fields that do not apply are empty strings, not omitted — the position *is*
    the meaning, so a five-element array silently relabels the country as the
    postal code.

  Building this by hand at each call site is how registries end up with
  entities that differ structurally from each other. It is built here instead."
  (:require [kotoba.lang.text :as str]))

(defn- prop
  ([name value] (prop name {} "text" value))
  ([name type value] (prop name {} type value))
  ([name params type value] [name params type value]))

(defn adr
  "The seven-element `adr` value array (RFC 6350 §6.3.1), in order. Missing
  components are the empty string because position carries the meaning."
  [{:keys [po-box extended street locality region postal-code country]}]
  [(or po-box "") (or extended "") (or street "") (or locality "")
   (or region "") (or postal-code "") (or country "")])

(defn vcard
  "Build a jCard from ordinary keys. Properties whose value is absent are
  omitted entirely rather than emitted empty — an `email` property with an
  empty string asserts the entity has a blank address."
  [{:keys [name org email phone address kind]}]
  ["vcard"
   (into [(prop "version" "text" "4.0")]
         (keep identity)
         [(prop "fn" "text" (or name org ""))
          (when kind (prop "kind" "text" (clojure.core/name kind)))
          (when org (prop "org" "text" org))
          (when email (prop "email" "text" email))
          (when phone (prop "tel" {"type" ["voice"]} "uri"
                            (if (str/starts-with? phone "tel:") phone (str "tel:" phone))))
          (when address (prop "adr" {} "text" (adr address)))])])

(defn value-of
  "Read one property's value back out of a jCard — for tests and for a client
  consuming someone else's RDAP. Returns nil when absent, so a caller can tell
  a missing property from an empty one."
  [vcard-array property]
  (some (fn [[n _params _type v]] (when (= n property) v))
        (second vcard-array)))
