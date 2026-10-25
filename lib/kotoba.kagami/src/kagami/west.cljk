(ns kagami.west
  "Parser/emitter for the west.yml dialect emitted by scripts/gen-west-manifest.cljs.

  This is NOT a general YAML parser. The generator's output is line-oriented and
  deterministic, so parse/emit is a bijection over that dialect: `emit` after
  `parse` must reproduce the input byte-for-byte (Phase 0 acceptance criterion,
  ADR-2607160005). Header (everything before the `  projects:` line) and footer
  (the `  self:` block) are carried verbatim; project entries are parsed into
  repo entities (see kagami.db) and re-emitted in the generator's field order:
  name, remote, revision, path, clone-depth?, groups, submodules?, userdata?.

  Submodules appear in two generator forms:
  - `submodules: true`  (recurse all)
  - `submodules:` + indented `- path: <rel>` list (selective exclude form from
    gen-west-manifest.cljs when submodule-excludes is set)."
  (:require [kotoba.lang.text :as str]))

(def ^:private projects-line "  projects:")

(defn- parse-groups [s]
  ;; "groups: [a, b]" -> ["a" "b"]
  (let [inner (-> s (str/replace #"^\[" "") (str/replace #"\]$" ""))]
    (if (str/blank? inner)
      []
      (mapv str/trim (str/split inner #",")))))

(defn- field-line? [line]
  (str/starts-with? line "      "))

(defn- parse-entry-lines
  "One project block (vector of lines, first is `    - name: X`) -> repo entity."
  [lines]
  (loop [entity {:repo/name (str/trim (subs (first lines) (count "    - name: ")))}
         [line & more] (rest lines)]
    (if (nil? line)
      entity
      (let [t (str/trim line)]
        (cond
          (str/starts-with? t "remote: ")
          (recur (assoc entity :repo/remote (subs t (count "remote: "))) more)

          (str/starts-with? t "repo-path: ")
          (recur (assoc entity :repo/repo-path (subs t (count "repo-path: "))) more)

          (str/starts-with? t "revision: ")
          (recur (assoc entity :repo/revision (subs t (count "revision: "))) more)

          (str/starts-with? t "path: ")
          (recur (assoc entity :repo/path (subs t (count "path: "))) more)

          (str/starts-with? t "clone-depth: ")
          (recur (assoc entity :repo/clone-depth
                        (#?(:clj Long/parseLong :cljs js/parseInt)
                         (subs t (count "clone-depth: "))))
                 more)

          (str/starts-with? t "groups: ")
          (recur (assoc entity :repo/groups (parse-groups (subs t (count "groups: ")))) more)

          (= t "submodules: true")
          (recur (assoc entity :repo/submodules? true) more)

          ;; selective submodule path list (gen-west-manifest exclude form):
          ;;   submodules:
          ;;     - path: 50-infra/.../lib/forge-std
          (= t "submodules:")
          (recur (assoc entity :repo/submodules? true :repo/submodule-paths []) more)

          (str/starts-with? t "- path: ")
          (recur (update entity :repo/submodule-paths (fnil conj [])
                         (subs t (count "- path: ")))
                 more)

          (= t "userdata:")
          (recur (assoc entity :repo/userdata {}) more)

          (str/starts-with? t "datalad: ")
          (recur (assoc-in entity [:repo/userdata :datalad]
                           (= "true" (subs t (count "datalad: "))))
                 more)

          (str/starts-with? t "annex-remote: ")
          (recur (assoc-in entity [:repo/userdata :annex-remote]
                           (subs t (count "annex-remote: ")))
                 more)

          (str/starts-with? t "archived: ")
          (recur (assoc-in entity [:repo/userdata :archived]
                           (= "true" (subs t (count "archived: "))))
                 more)

          ;; Radicle 実登録の RID(rad:z...)。正本は superproject の
          ;; manifest/repos.edn :manifest.repos/rad-rids で、west.yml は
          ;; その projection — reconcile はここから fleet-db へ吸収する。
          (str/starts-with? t "rad-rid: ")
          (recur (assoc-in entity [:repo/userdata :rad-rid]
                           (subs t (count "rad-rid: ")))
                 more)

          :else
          (throw (ex-info "unrecognized west.yml project field (generator dialect drift?)"
                          {:line line :entity entity})))))))

(defn- parse-remotes
  "Header lines -> [{:remote/name .. :remote/url-base ..} ...]"
  [header-lines]
  (loop [remotes [] pending nil [line & more :as all] header-lines]
    (cond
      (nil? line) remotes
      (str/starts-with? (str/trim line) "- name: ")
      (recur remotes {:remote/name (subs (str/trim line) (count "- name: "))} more)
      (and pending (str/starts-with? (str/trim line) "url-base: "))
      (recur (conj remotes (assoc pending :remote/url-base
                                  (subs (str/trim line) (count "url-base: "))))
             nil more)
      (str/starts-with? line "  defaults:") remotes
      :else (recur remotes pending more))))

(defn parse
  "west.yml text -> {:fleet/header str, :fleet/footer str,
                     :fleet/remotes [..], :fleet/repos [entity ..]}"
  [text]
  (let [lines (str/split text #"\n" -1)          ;; -1: keep trailing empty strings
        [header-lines rest-lines] (split-with #(not= % projects-line) lines)
        _ (when (empty? rest-lines)
            (throw (ex-info "no `  projects:` section found" {})))
        body (rest rest-lines)                    ;; after "  projects:"
        entry-start? #(str/starts-with? % "    - name: ")
        ;; footer = first line after the last entry block that is neither an
        ;; entry field nor an entry start (i.e. "" / "  self:" ...)
        [entry-lines footer-lines]
        (loop [taken [] [line & more :as all] body]
          (cond
            (nil? line) [taken []]
            (or (entry-start? line) (field-line? line)) (recur (conj taken line) more)
            :else [taken (vec all)]))
        entries (loop [out [] cur nil [line & more] entry-lines]
                  (cond
                    (nil? line) (if cur (conj out cur) out)
                    (entry-start? line) (recur (if cur (conj out cur) out) [line] more)
                    :else (recur out (conj cur line) more)))]
    {:fleet/header  (str/join "\n" (concat header-lines [projects-line]))
     :fleet/footer  (str/join "\n" footer-lines)
     :fleet/remotes (parse-remotes header-lines)
     :fleet/repos   (mapv parse-entry-lines entries)}))

(defn emit-entry
  "repo entity -> project block lines, in the generator's field order."
  [{:repo/keys [name remote repo-path revision path clone-depth groups
                submodules? submodule-paths userdata]}]
  (cond-> [(str "    - name: " name)
           (str "      remote: " remote)]
    repo-path   (conj (str "      repo-path: " repo-path))
    :always     (into [(str "      revision: " revision)
                       (str "      path: " path)])
    clone-depth (conj (str "      clone-depth: " clone-depth))
    groups      (conj (str "      groups: [" (str/join ", " groups) "]"))
    (seq submodule-paths)
    (into (into ["      submodules:"]
                (map (fn [p] (str "        - path: " p)) submodule-paths)))
    (and submodules? (empty? submodule-paths))
    (conj "      submodules: true")
    userdata    (into (cond-> ["      userdata:"]
                        (contains? userdata :datalad)
                        (conj (str "        datalad: " (:datalad userdata)))
                        (contains? userdata :annex-remote)
                        (conj (str "        annex-remote: " (:annex-remote userdata)))
                        (contains? userdata :archived)
                        (conj (str "        archived: " (:archived userdata)))
                        (contains? userdata :rad-rid)
                        (conj (str "        rad-rid: " (:rad-rid userdata)))))))

(defn emit
  "Inverse of `parse` — byte-exact over the generator dialect."
  [{:fleet/keys [header footer repos]}]
  (str/join "\n" (concat [header]
                         (mapcat emit-entry repos)
                         [footer])))

(defn remote-url
  "Resolve an entity's clone URL from the parsed remotes."
  [db entity]
  (let [base (some #(when (= (:remote/name %) (:repo/remote entity))
                      (:remote/url-base %))
                   (:fleet/remotes db))]
    (when-not base
      (throw (ex-info "unknown remote" {:repo (:repo/name entity)})))
    ;; west semantics: repo-path overrides name for the upstream repo name
    (str base "/" (or (:repo/repo-path entity) (:repo/name entity)))))

(defn find-repo [db name]
  (some #(when (= name (:repo/name %)) %) (:fleet/repos db)))
