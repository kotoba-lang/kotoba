(ns kobo.editor
  (:require [kotoba.lang.text :as str]))

(def aiueos-known-keys
  #{:aiueos/component
    :aiueos/kind
    :aiueos/trust
    :aiueos/imports
    :aiueos/exports
    :aiueos/effects
    :aiueos/requires
    :aiueos/grants
    :aiueos/entry
    :aiueos/args
    :aiueos/wasm
    :aiueos/wasm-sha256
    :aiueos/wasm-cid
    :aiueos/memory-pages
    :aiueos/fuel
    :aiueos/publishes
    :aiueos/subscribes})

(defn buffer
  ([path text] (buffer path text {}))
  ([path text attrs]
   (merge {:kobo.buffer/path path
           :kobo.buffer/text text
           :kobo.buffer/dirty? false}
          attrs)))

(defn replace-text [buf text]
  (assoc buf
         :kobo.buffer/text text
         :kobo.buffer/dirty? true))

(defn patch
  ([path old-text new-text] (patch path old-text new-text {}))
  ([path old-text new-text attrs]
   (merge {:kobo.patch/path path
           :kobo.patch/old-text old-text
           :kobo.patch/new-text new-text}
          attrs)))

(defn apply-patch [buf p]
  (when-not (= (:kobo.buffer/path buf) (:kobo.patch/path p))
    (throw (ex-info "patch path does not match buffer"
                    {:buffer-path (:kobo.buffer/path buf)
                     :patch-path (:kobo.patch/path p)})))
  (when-not (= (:kobo.buffer/text buf) (:kobo.patch/old-text p))
    (throw (ex-info "patch old text does not match buffer"
                    {:path (:kobo.buffer/path buf)})))
  (replace-text buf (:kobo.patch/new-text p)))

(defn diagnostic [severity code message attrs]
  (merge {:kobo.diagnostic/severity severity
          :kobo.diagnostic/code code
          :kobo.diagnostic/message message}
         attrs))

(defn edn-diagnostics [path value]
  (cond
    (not (map? value))
    [(diagnostic :error :expected-map "EDN document must be a map"
                 {:kobo.diagnostic/path path})]

    :else
    []))

(defn aiueos-manifest-diagnostics [path manifest]
  (let [unknown (->> (keys manifest)
                     (filter #(and (keyword? %) (= "aiueos" (namespace %))))
                     (remove aiueos-known-keys)
                     sort
                     vec)
        missing (remove #(contains? manifest %)
                        [:aiueos/component :aiueos/kind :aiueos/trust])]
    (vec
     (concat
      (edn-diagnostics path manifest)
      (for [k unknown]
        (diagnostic :error :unknown-aiueos-key
                    (str "Unknown aiueos manifest key " k)
                    {:kobo.diagnostic/path path
                     :kobo.diagnostic/key k}))
      (for [k missing]
        (diagnostic :error :missing-aiueos-key
                    (str "Missing required aiueos manifest key " k)
                    {:kobo.diagnostic/path path
                     :kobo.diagnostic/key k}))))))

(defn search-buffer [buf query]
  (let [text (:kobo.buffer/text buf)
        lines (str/split-lines text)]
    (->> lines
         (map-indexed vector)
         (keep (fn [[idx line]]
                 (when (str/includes? line query)
                   {:kobo.search/path (:kobo.buffer/path buf)
                    :kobo.search/line (inc idx)
                    :kobo.search/text line})))
         vec)))
