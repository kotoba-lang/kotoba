(ns kotoba.lang.kami-nv-compat.amenominaka.commands
  "Clean-room Kit command stack (omni.kit.commands) — JVM port of
  src/amenominaka/commands.ts. Undoable commands + a CommandStack with
  undo/redo and a bounded history; executing a new command clears the redo
  stack (linear undo, no branching). Each command captures its inverse so
  undo! reverses do!.

  Wave-2 (sub) of the kami-nv-compat TS->CLJC port (ADR-2607020130): the
  amenominaka subdir is split across waves — this namespace (commands) is
  self-contained; the extension.toml parser + Application lifecycle land in
  follow-up waves.

  The TS models targets as plain mutable objects; here a target is an atom
  holding a map, and set-attribute-command mutates it via swap!.")

;; ── ICommand protocol (mirrors the abstract `Command` class) ───────────────

(defprotocol ICommand
  (command-do! [this] "Apply the command's effect.")
  (command-undo! [this] "Reverse command-do!.")
  (command-name [this] "Stable name for history listing."))

;; ── SetAttributeCommand ───────────────────────────────────────────────────

(defn set-attribute-command
  "A command that sets `key` to `value` on the atom-held map `target`; undo!
  restores the prior value (or removes the key if it was absent). Mirrors the
  TS SetAttributeCommand<T>."
  [target key value]
  (let [had-key (volatile! false)
        prev    (volatile! nil)]
    (reify ICommand
      (command-do! [_]
        (let [cur @target]
          (vreset! had-key (contains? cur key))
          (vreset! prev (get cur key))
          (swap! target assoc key value)))
      (command-undo! [_]
        (if @had-key
          (swap! target assoc key @prev)
          (swap! target dissoc key)))
      (command-name [_] "SetAttribute"))))

;; ── CommandStack ──────────────────────────────────────────────────────────

(defprotocol ICommandStack
  (execute! [this cmd] "Apply cmd, push it on the undo stack, clear redo; trim oldest past cap. Throws if do! throws (cmd not pushed).")
  (undo!    [this] "Undo the most recent command; returns it, or nil if empty.")
  (redo!    [this] "Redo the most recently undone command; returns it, or nil if empty.")
  (can-undo? [this])
  (can-redo? [this])
  (history [this] "Names of the undo stack, oldest-first.")
  (clear! [this]))

(defn command-stack
  "Returns a new ICommandStack with a bounded history (default 1000)."
  ([]
   (command-stack 1000))
  ([history-size]
   (let [state (atom {:undo [] :redo [] :history-size history-size})]
     (reify ICommandStack
       (execute! [_ cmd]
         (command-do! cmd)                       ; may throw → not pushed (TS parity)
         (swap! state
                (fn [{:keys [undo history-size]}]
                  (let [undo' (conj undo cmd)]
                    {:undo (if (> (count undo') history-size)
                             (subvec undo' 1)    ; drop oldest
                             undo')
                     :redo []
                     :history-size history-size}))))
       (undo! [_]
         (let [undo (:undo @state)]
           (if (empty? undo)
             nil
             (let [cmd (peek undo)]
               (command-undo! cmd)
               (swap! state (fn [s]
                              (-> s
                                  (update :undo pop)
                                  (update :redo conj cmd))))
               cmd))))
       (redo! [_]
         (let [redo (:redo @state)]
           (if (empty? redo)
             nil
             (let [cmd (peek redo)]
               (command-do! cmd)
               (swap! state (fn [s]
                              (-> s
                                  (update :redo pop)
                                  (update :undo conj cmd))))
               cmd))))
       (can-undo? [_] (some? (seq (:undo @state))))
       (can-redo? [_] (some? (seq (:redo @state))))
       (history  [_] (mapv command-name (:undo @state)))
       (clear!   [_] (swap! state assoc :undo [] :redo []))))))

;; ── global command stack (omni.kit.commands.execute/undo/redo) ────────────

(defonce ^:private global-stack (atom nil))

(defn- global-stack! []
  (or @global-stack (reset! global-stack (command-stack))))

(defn execute [cmd] (execute! (global-stack!) cmd))
(defn undo   []  (undo! (global-stack!)))
(defn redo   []  (redo! (global-stack!)))

(defn reset-stack!
  "Reset the global command stack (test helper; mirrors TS `_resetStack`)."
  []
  (reset! global-stack nil))
