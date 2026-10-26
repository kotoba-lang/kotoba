(ns kuro.terminal
  (:require [kotoba.lang.text :as str]))

(def isolation-none
  "この repo が提供する隔離の実態。

   `:none` は「隔離が無い」という**記録された事実**であって既定値ではない。
   receipt にこれが載るのは、後から audit する人が『どの backing で走ったのか』
   を receipt だけで判定できるようにするため —— 隔離の有無を書かない receipt は、
   隔離されていたかのように読まれる。

   実際に confine する backing（container / microVM / aiueos surface provider）が
   接続されたら、その host が自分の値を入れる。"
  :none)

(def terminal-modes
  {:terminal-repo
   {:kuro/mode :terminal-repo
    :kuro/label "repo"
    :kuro/default-capabilities #{"repo/read" "tmp/write" "log/write"}
    :kuro/host? false}

   :terminal-build
   {:kuro/mode :terminal-build
    :kuro/label "build"
    :kuro/default-capabilities #{"repo/read" "repo/write" "tmp/write" "cache/read" "cache/write" "net/fetch" "log/write"}
    :kuro/host? false}

   :terminal-agent
   {:kuro/mode :terminal-agent
    :kuro/label "agent"
    :kuro/default-capabilities #{"repo/read" "tmp/write" "log/write" "agent/checkpoint"}
    :kuro/host? false}

   :terminal-host
   {:kuro/mode :terminal-host
    :kuro/label "host"
    :kuro/default-capabilities #{"host/shell"}
    :kuro/host? true}})

(defn mode? [x]
  (contains? terminal-modes x))

(defn command-argv? [argv]
  (and (vector? argv)
       (seq argv)
       (every? #(and (string? %) (not (str/blank? %))) argv)))

(defn command
  ([argv] (command argv {}))
  ([argv attrs]
   (when-not (command-argv? argv)
     (throw (ex-info "command argv must be a non-empty vector of non-blank strings"
                     {:argv argv})))
   (merge {:kuro/type :kuro/command
           :kuro/argv argv}
          attrs)))

(defn session
  ([id repo-root-cid mode] (session id repo-root-cid mode {}))
  ([id repo-root-cid mode attrs]
   (when-not (mode? mode)
     (throw (ex-info "unknown terminal mode" {:mode mode})))
   (let [spec (terminal-modes mode)
         signed? (:kuro/signed-opt-in? attrs)]
     (when (and (:kuro/host? spec) (not signed?))
       (throw (ex-info "terminal-host requires signed opt-in"
                       {:mode mode
                        :reason :signed-opt-in-required})))
     (merge {:kuro/type :kuro/session
             :kuro/session-id id
             :kuro/repo-root-cid repo-root-cid
             :kuro/mode mode
             :kuro/cwd "."
             :kuro/events []
             :kuro/grant {:capabilities (:kuro/default-capabilities spec)}}
            attrs))))

(defn effective-capabilities [sess]
  (set (get-in sess [:kuro/grant :capabilities] #{})))

(defn command-allowed? [sess required-capabilities]
  (let [granted (effective-capabilities sess)
        required (set required-capabilities)]
    (empty? (remove granted required))))

(defn denial [sess required-capabilities]
  (let [granted (effective-capabilities sess)
        missing (vec (sort (remove granted (set required-capabilities))))]
    (when (seq missing)
      {:kuro/allowed? false
       :kuro/reason :missing-capabilities
       :kuro/missing missing
       :kuro/session-id (:kuro/session-id sess)})))

(defn append-event [sess event]
  (update sess :kuro/events conj event))

(defn receipt
  "Build a terminal receipt from host-supplied result data.

  This function does not run a command and does not compute cryptographic hashes.
  The host may include digest fields such as :stdout-cid, :stderr-cid, or
  :patch-cids in result.

  Result keys outside the selected set are dropped on purpose: a receipt is a
  fixed shape, so one host cannot smuggle fields another host will not produce.
  The bounded-execution keys (:timed-out? :truncated? :duration-ms :error) are
  part of that shape because a receipt that records exit 124 without saying
  \"the deadline killed it\" reads as a command that chose to fail.

  Host-supplied keys are namespaced into :kuro/* on the way in, so the whole
  receipt is one namespace. It used to carry :kuro/mode next to a bare :stdout;
  receipt-fact puts this map inside a kotoba fact, where an unnamespaced :stdout
  is a name every other producer can also claim."
  [sess cmd result]
  (let [exit-code (:exit-code result)
        kuro-ns (fn [m] (into {} (map (fn [[k v]] [(keyword "kuro" (name k)) v])) m))]
    (when-not (integer? exit-code)
      (throw (ex-info "receipt result requires integer :exit-code" {:result result})))
    (merge {:kuro/type :kuro/receipt
            ;; 何が実際に enforce したか。host が :isolation を渡さなければ
            ;; :none —— 黙って省略させない（省略された receipt は、隔離されて
            ;; いたかのように読まれる）。
            :kuro/isolation (:isolation result isolation-none)
            :kuro/session-id (:kuro/session-id sess)
            :kuro/repo-root-cid (:kuro/repo-root-cid sess)
            :kuro/mode (:kuro/mode sess)
            :kuro/cwd (:kuro/cwd sess)
            :kuro/argv (:kuro/argv cmd)
            :kuro/effective-capabilities (effective-capabilities sess)
            :kuro/exit-code exit-code}
           (kuro-ns
            (select-keys result [:stdout :stderr :stdout-cid :stderr-cid :patch-cids
                                 :stdout-bytes :stderr-bytes :dropped-bytes :isolation
                                 :started-at :finished-at :duration-ms
                                 :timed-out? :truncated? :error])))))

(defn receipt-fact [receipt]
  {:kotoba/type :kuro/terminal-receipt
   :kotoba/id [:kuro/receipt (:kuro/session-id receipt) (:kuro/argv receipt)]
   :kuro/receipt receipt})
