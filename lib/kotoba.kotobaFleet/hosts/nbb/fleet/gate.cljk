(ns fleet.gate
  "The governor's admission rules for a sandboxed agent proposal — pure, so the
  rules can be tested without a fleet node, a model, or a git tree.

  Everything here re-derives a fact the agent could have gotten wrong or lied
  about. The agent reports its own test results and its own sandbox state; the
  governor treats both as claims. In particular **isolation is admitted here,
  not asserted on the node**: a payload that ran with the exec backing disabled,
  or whose own startup probe leaked, is rejected even when its tests are green.
  Opting out is a property of the work-unit, never of the runtime."
  (:require [kotoba.lang.text :as str]
            [fleet.kcm :as kcm]))

(defn diff-files
  "Paths touched by a unified diff (from its `diff --git a/… b/…` headers)."
  [diff]
  (->> (str/split-lines (or diff ""))
       (keep #(second (re-find #"^diff --git a/(\S+) b/" %)))
       distinct
       vec))

(defn reasons
  "Why this proposal must NOT be materialized. Empty vector = admissible.

  ctx:
    :payload            the agent's returned payload
    :agent              the proposing agent id
    :holder             who actually holds the lease right now
    :pin                the commit the dispatcher built the sandbox from
    :protected-paths    path prefixes the fleet refuses to let an agent touch
    :allow-unsandboxed? work-unit opt-out for :exec-backing != :sandbox-exec
    :patch-applies?     true iff the patch applies to the pinned tree (nil when
                        the caller had no pinned tree to check against)"
  [{:keys [payload agent holder pin protected-paths allow-unsandboxed? patch-applies?
           kcm-spec]}]
  (let [p payload
        files (diff-files (:diff p))
        leaked (get-in p [:exec-probe :leaked])]
    (cond-> []
      (not= holder agent)
      (conj (str "proposer does not hold the lease (holder=" holder ")"))

      (str/blank? (:diff p)) (conj "empty diff")

      (not= pin (:pin p)) (conj "payload pin != dispatched pin")

      (some (fn [f] (some #(str/starts-with? f %) protected-paths)) files)
      (conj (str "touches a protected path: " files))

      (not= 0 (get-in p [:tests :final-exit]))
      (conj (str "tests not green on the node (exit="
                 (get-in p [:tests :final-exit]) ")"))

      (= :error (:stop p)) (conj (str "agent errored: " (:error p)))

      (and (not= :sandbox-exec (:exec-backing p)) (not allow-unsandboxed?))
      (conj (str "exec backing was " (pr-str (:exec-backing p))
                 ", not :sandbox-exec (set :allow-unsandboxed-exec to override)"))

      (seq leaked)
      (conj (str "exec backing leaked: " (pr-str leaked)))

      (nil? patch-applies?) (conj "no pinned tree to verify the patch against")

      (false? patch-applies?)
      (conj "patch does not apply cleanly to the pinned tree")

      (and (kcm/kcm? kcm-spec)
           (not= :kotoba-capability-machine (:machine p)))
      (conj "KCM work ran outside the Kotoba Capability Machine")

      (and (kcm/kcm? kcm-spec)
           (not= (kcm/machine-id kcm-spec) (:machine-id p)))
      (conj "KCM machine identity does not match the dispatched closure/policy")

      (and (kcm/kcm? kcm-spec)
           (not= kcm/contract-version (:kcm-contract p)))
      (conj "KCM contract version does not match"))))
