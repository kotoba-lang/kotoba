(ns fix.groups
  "Repeating groups: NoXXX count tags whose value says how many times a
  fixed set of fields repeats immediately afterward (FIX.5.0 SP2 Volume 1,
  'Repeating Groups').

  Two rules matter here, and both are enforced, not assumed:

  1. **The NoXXX field's value is authoritative for how many entries
     follow** — a decoder has to consume exactly that many, no more, no
     less; running past the declared count (or running out of fields before
     reaching it) is `:fix/group-count-mismatch`.
  2. **Every group instance must begin with the same field — the group's
     first defined member tag — even when that field would otherwise be
     optional.** This is what lets a decoder tell where one entry ends and
     the next begins without an explicit length: it scans for the
     recurrence of that one delimiter tag. An entry that starts with any
     other member tag is not just malformed, it is genuinely ambiguous —
     a decoder that skips the rule can misattribute a field from entry 2 to
     entry 1 whenever an optional field is simply absent from entry 1 — so
     it is `:fix/group-missing-delimiter`, not silently accepted.

  This only handles one level of grouping (no group nested inside another
  group's entries) — every message this library's dictionary and test
  suite cover only ever nests one level deep, and a second level would need
  the member-tag/first-tag bookkeeping below to be recursive rather than
  flat. Extending it is straightforward; it just isn't done, and a nested
  NoXXX tag inside an entry is treated as an ordinary field, not detected
  as an error."
  (:require [fix.bytes :as b]))

(defn flatten-body
  "The body a caller writes — `[tag value]` pairs interleaved with
  `{:group tag :entries [[[tag value] ...] ...]}` maps — flattened to the
  wire's flat field order. No dictionary needed in this direction: a group
  map already carries its own tag and entries, and the NoXXX count is
  simply `(count entries)`, computed rather than asked for so it can never
  disagree with what actually got encoded."
  [body]
  (reduce (fn [acc item]
            (if (map? item)
              (let [{:keys [group entries]} item]
                (into (conj acc [group (str (count entries))])
                      cat
                      entries))
              (conj acc item)))
          []
          body))

(defn- split-one-entry
  "Consumes one group entry starting at `fields`' first element (already
  known to carry `first-tag`): that field, plus every following field whose
  tag is a member of the group and isn't `first-tag` again. Returns
  `[entry-fields remaining-fields]`."
  [member-tags first-tag fields]
  (loop [acc [(first fields)] remaining (rest fields)]
    (if-let [entry (first remaining)]
      (let [[tag _] entry]
        (if (and (contains? member-tags tag) (not= tag first-tag))
          (recur (conj acc entry) (rest remaining))
          [acc remaining]))
      [acc remaining])))

(defn- take-entries [n first-tag member-tags fields]
  (loop [remaining fields entries [] k 0]
    (cond
      (= k n) {:status :ok :entries entries :remaining remaining}
      (empty? remaining) {:status :error :reason :fix/group-count-mismatch}
      :else
      (let [[tag _] (first remaining)]
        (if (not= tag first-tag)
          {:status :error :reason :fix/group-missing-delimiter}
          (let [[entry rest*] (split-one-entry member-tags first-tag remaining)]
            (recur rest* (conj entries entry) (inc k))))))))

(defn structure-body
  "Flat `[tag value]` pairs -> the same shape `flatten-body` accepts, with
  every tag in `groups` (a dictionary's `:groups` table, `{count-tag
  {:member-tags [first-tag & rest]}}`) expanded into a `{:group :entries}`
  map. `[:ok body]` or `[:error kw]` — `:fix/malformed-field` if a NoXXX
  field's own value isn't a valid count, otherwise whatever `take-entries`
  found wrong."
  [groups fields]
  (loop [remaining fields out []]
    (if (empty? remaining)
      [:ok out]
      (let [[tag val] (first remaining)
            gdef (get groups tag)]
        (if (nil? gdef)
          (recur (rest remaining) (conj out [tag val]))
          (let [n (b/parse-uint val)]
            (if (nil? n)
              [:error :fix/malformed-field]
              (let [first-tag (first (:member-tags gdef))
                    member-set (set (:member-tags gdef))
                    r (take-entries n first-tag member-set (rest remaining))]
                (if (= (:status r) :ok)
                  (recur (:remaining r) (conj out {:group tag :entries (:entries r)}))
                  [:error (:reason r)])))))))))
