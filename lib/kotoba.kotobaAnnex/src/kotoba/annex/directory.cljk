(ns kotoba.annex.directory
  "ローカルディレクトリ backed の store（実 git-annex 検証用 / kotobase 未接続時の
   fallback）。key を階層化してファイルに保存。kotobase store と同じ store 契約。"
  (:require ["fs" :as fs]
            ["path" :as path]))

(defn- key->path [dir key]
  ;; key の先頭 2+2 文字でシャーディング（git-annex の dirhash 相当の簡易版）
  (let [safe (.replace key #"[^A-Za-z0-9._-]" "_")
        a (subs safe 0 (min 2 (count safe)))
        b (subs safe (min 2 (count safe)) (min 4 (count safe)))]
    (path/join dir a b safe)))

(defn directory-store [dir]
  {:store!   (fn [key bytes]
               (let [p (key->path dir key)]
                 (fs/mkdirSync (path/dirname p) #js {:recursive true})
                 (fs/writeFileSync p bytes)
                 true))
   :retrieve (fn [key]
               (let [p (key->path dir key)]
                 (when (fs/existsSync p) (fs/readFileSync p))))
   :present? (fn [key] (if (fs/existsSync (key->path dir key)) :yes :no))
   :remove!  (fn [key]
               (let [p (key->path dir key)]
                 (when (fs/existsSync p) (fs/rmSync p))
                 true))
   :init!    (fn [] (fs/mkdirSync dir #js {:recursive true}) true)
   :prepare! (fn [_config] (fs/mkdirSync dir #js {:recursive true}) true)})
