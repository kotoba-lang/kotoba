(ns manifest-reality.parse
  "west.yml を data にする。**IO はしない** — 呼び出し側が読んだ文字列を受け取る。

   west.yml は `scripts/gen-west-manifest.cljs` の生成物なので、ここでは
   汎用 YAML パーサを使わず生成器と同じ行指向で読む。汎用パーサを使うと
   「生成器が出さない形」まで受理してしまい、gate が実態より緩くなる。

   `projects:` セクションの外に project 形のブロックが混入していても
   拾えるようにしてある — それ自体が検査対象だから (structure/stray)。"
  (:require [kotoba.lang.text :as str]))

(def ^:private block-start #"^    - name: (\S+)\s*$")

(defn- field
  "block の行列から `  <k>: <v>` を引く。インデントは問わない。"
  [lines k]
  (some (fn [l]
          (when-let [m (re-find (re-pattern (str "^\\s*" k ":\\s*(\\S.*)$")) l)]
            (str/trim (second m))))
        lines))

(defn- section-index
  "行番号 → セクション名 (:remotes / :projects / :self / :other)。
   west.yml のトップレベルキーは 2 スペースインデント。"
  [lines]
  (loop [i 0, cur :other, acc []]
    (if (>= i (count lines))
      acc
      (let [l (nth lines i)
            cur' (cond
                   (= l "  remotes:")  :remotes
                   (= l "  projects:") :projects
                   (= l "  self:")     :self
                   (re-find #"^  [a-z-]+:" l) :other
                   :else cur)]
        (recur (inc i) cur' (conj acc cur'))))))

(defn parse-west
  "west.yml の文字列 → {:blocks [...]}。

   各 block は
   {:name :remote :repo-path :revision :path :groups :userdata-rad-rid
    :archived? :datalad? :section :line}
   `:section` は**その block が現れたセクション**。`:projects` 以外に project 形が
   出ていたら構造破損 (実測: loop-jiten が remotes に混入した commit 6ebf4b4b5fc)。"
  [text]
  (let [lines (vec (str/split-lines text))
        sections (section-index lines)
        idxs (keep-indexed (fn [i l] (when (re-find block-start l) i)) lines)
        bounds (map vector idxs (concat (rest idxs) [(count lines)]))]
    {:blocks
     (vec
      (for [[s e] bounds
            :let [body (subvec lines s e)
                  nm (second (re-find block-start (first body)))]]
        {:name nm
         :section (nth sections s :other)
         :line (inc s)
         :remote (field body "remote")
         :repo-path (field body "repo-path")
         :revision (field body "revision")
         :path (field body "path")
         :groups (field body "groups")
         :rad-rid (field body "rad-rid")
         :archived? (boolean (some #(= "archived: true" (str/trim %)) body))
         :datalad? (boolean (some #(= "datalad: true" (str/trim %)) body))}))}))

(defn projects
  "project ブロックだけ (path を持つもの)。remotes の {name,url-base} は除かれる。"
  [{:keys [blocks]}]
  (filterv :path blocks))

(defn path->org [p] (some-> p (str/split #"/") (nth 1 nil)))
(defn path->name [p] (some-> p (str/split #"/") last))
