(ns upf.domain
  "UPF (Unified Power Format, IEEE 1801) power domain model — a simplified
  subset of `create_power_domain`: domain name + hierarchical scope, plus a
  longest-prefix instance-to-domain lookup mirroring UPF's nested-scope
  semantics (an instance under a more deeply nested domain's scope belongs
  to that domain, not a less specific enclosing ancestor domain)."
  (:require [kotoba.lang.text :as str]))

(defn create-power-domain
  "Build a power domain map: `name` is the domain identifier, `scope` is a
  collection of hierarchical instance-path-prefix strings the domain covers
  (UPF's `-elements` list on `create_power_domain`)."
  [name scope]
  {:name name :scope (vec scope)})

(defn- prefix-match-length
  "Length of `prefix` when it matches `instance-path` at a hierarchy
  boundary (exact match, or `instance-path` nested under `prefix/...`);
  nil when `prefix` does not cover `instance-path` at all."
  [prefix instance-path]
  (when (or (= prefix instance-path)
            (str/starts-with? instance-path (str prefix "/")))
    (count prefix)))

(defn instance-domain
  "Given a `domains` registry (a collection of `create-power-domain` maps)
  and an `instance-path` string, return the `:name` of the domain whose
  scope most specifically covers that instance.

  Longest-prefix-match: when more than one domain's scope covers the
  instance (nested domains), the domain with the longest matching scope
  entry wins — e.g. a domain scoped to `top/cpu/core` is preferred over one
  scoped to `top/cpu` for instance `top/cpu/core/alu`. Returns nil when no
  domain's scope covers the instance."
  [domains instance-path]
  (let [candidates (keep (fn [{:keys [name scope]}]
                            (when-let [lengths (seq (keep #(prefix-match-length % instance-path) scope))]
                              [(apply max lengths) name]))
                          domains)]
    (when (seq candidates)
      (second (apply max-key first candidates)))))
