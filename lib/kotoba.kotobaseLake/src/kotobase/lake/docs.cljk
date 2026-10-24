(ns kotobase.lake.docs
  "The catalog, as documents on a kotobase graph — both directions, in one
  namespace, in the library both sides depend on.

  `kotobase.lake.catalog/admit` produces quads. A kotobase graph stores
  documents. This is the conversion.

  ## Why both directions live together

  A writer that encoded catalog quads one way and a reader that decoded them
  another would fail by returning `:no-such-object` for an object that is
  right there — a refusal indistinguishable from the one
  `kotobase.lake.acquire` issues when a tenant has no claim, which is the
  single answer in this system that must never be produced by accident.

  ## Why it lives HERE and not in a deploy shell

  It was written in the reader's Worker (`net-kotobase-lake.catalog-docs`)
  because the reader was the only side that existed. The moment an ingest
  path writes these documents, the argument above stops being satisfied by
  keeping them adjacent: the writer is a different Worker, in a different
  repository, and \"one namespace\" only prevents drift if both sides load
  the same one. So the encoding sits in the library both already depend on,
  and the deploy shell re-exports it.

  ## The encoding

  One document per quad SUBJECT, keyed by that subject, whose value is the
  subject's attribute map:

      obj:bafkrei…    -> {\"object/cid\" \"bafkrei…\" \"object/size\" 2427}
      claim:acme|baf… -> {\"claim/object\" \"obj:bafkrei…\" \"claim/tenant\" \"acme\" …}

  Subject-per-document rather than quad-per-document because a subject is
  what both readers ask for: `acquire/holds?` wants one claim's tenant and
  `catalog/object-size` wants one object's size. A quad-per-document layout
  would make each of those a scan of the collection.

  Attribute keys survive as strings. A document written with keyword keys
  (EDN's habit) decodes back to the same string, because `catalog/admit`
  emits strings and `acquire` compares against string literals — a keyword
  that stayed a keyword would compare unequal and, again, look exactly like
  a refusal."
  (:require [kotobase.lake.catalog :as catalog]))

(def default-collection
  "The collection a deployment reads unless it says otherwise. A name rather
  than a convention so that a tenant may keep more than one catalog on one
  ref."
  "lake-catalog")

(defn- attr-name
  "An attribute key as the string `catalog/admit` would have emitted."
  [p]
  (cond
    (string? p) p
    (keyword? p) (subs (str p) 1)
    :else (str p)))

(defn quads->docs
  "Catalog quads -> `{subject {attr value}}`, ready to store one document per
  key. The shape an ingest writer must produce."
  [quads]
  (reduce (fn [m {:keys [s p o]}] (assoc-in m [s (attr-name p)] o)) {} quads))

(defn docs->quads
  "`{subject {attr value}}` -> the quad set `kotobase.lake.acquire` and
  `kotobase.lake.catalog` read.

  A non-map document contributes nothing rather than throwing: a collection
  is shared with whatever else a tenant put there, and one unexpected value
  must not make the whole catalog unreadable."
  [docs]
  (into #{}
        (mapcat (fn [[s attrs]]
                  (when (map? attrs)
                    (map (fn [[p o]] {:s s :p (attr-name p) :o o}) attrs))))
        docs))

(defn admitted->docs
  "The documents an ingest writer must store for one `catalog/admit` result,
  or `nil` when `admit` refused.

  The whole write, expressed once: a caller that reaches for `:quads` and
  encodes them itself is the drift this namespace exists to prevent, and a
  caller that forgets to check `:admitted?` would otherwise store the
  refusal map's absent `:quads` as an empty catalog entry — an object the
  reader then reports as `:no-such-object` while the ingest reported
  success."
  [admitted]
  (when (:admitted? admitted)
    (quads->docs (:quads admitted))))

(defn from-state
  "Catalog quads out of a hydrated LocalStore-shaped state.

  `nil` collection means the default. An absent collection yields an empty
  set, which `acquire/source-for` answers as `:no-such-object` — the correct
  answer for a graph that has catalogued nothing, and the same one it gives
  a caller asking about somebody else's object."
  ([state] (from-state state default-collection))
  ([state coll] (docs->quads (get (:docs state) (or coll default-collection)))))

(defn object-size
  "Size in bytes recorded for `cid`, or nil.

  Taken from the catalog rather than from a HEAD request against the store:
  size is a function of the bytes, `admit` refused the record without it, and
  a HEAD would be a second round trip that could disagree."
  [quads cid]
  (catalog/object-size quads (catalog/object-id cid)))
