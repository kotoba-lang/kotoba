(ns browser.profile
  "Profiles partition browser state by account, storage, and permission grants.")

(def default-permissions
  #{:dom/render :dom/event :input/event :net/fetch :log/write :clock/monotonic})

(def internal-origin "kotoba://shell")

(defn new-profile
  [{:keys [id account name storage-partition permissions] :as opts}]
  {:profile/id (or id "default")
   :profile/account-id (:account/id account)
   :profile/name (or name "Default")
   :profile/storage-partition (or storage-partition (str "profile:" (or id "default")))
   ;; default-permissions is materialized into internal-origin's own
   ;; EXPLICIT grant set here, rather than permission? OR-ing it in
   ;; unconditionally at check time (the previous approach) -- the OR
   ;; form made the six internal defaults permanently ungrantable AND
   ;; unrevocable: revoke-permission only ever mutates the explicit set,
   ;; so disj-ing a default capability that was never actually IN that
   ;; set was a silent no-op, and permission?'s OR branch kept firing
   ;; regardless. Confirmed via direct REPL reproduction before this
   ;; fix. A fresh profile's internal-origin permissions are unchanged
   ;; (still implicitly granted, matching every existing caller/test),
   ;; but now genuinely revocable like any other origin's grants.
   :profile/permissions (update (or permissions {}) internal-origin
                                (fnil into #{}) default-permissions)
   :profile/history []
   :profile/meta (dissoc opts :id :account :name :storage-partition :permissions)})

(defn grant-permission
  [profile origin capability]
  (update-in profile [:profile/permissions origin] (fnil conj #{}) capability))

(defn revoke-permission
  [profile origin capability]
  (update-in profile [:profile/permissions origin] disj capability))

(defn permission?
  [profile origin capability]
  (contains? (get-in profile [:profile/permissions origin] #{}) capability))

(defn permission-decision
  [profile origin capability]
  (if (permission? profile origin capability)
    {:permission/decision :allow
     :origin origin
     :capability capability
     :profile/id (:profile/id profile)}
    {:permission/decision :deny
     :origin origin
     :capability capability
     :profile/id (:profile/id profile)
     :reason :permission/not-granted}))

(defn storage-key
  [profile origin k]
  [(:profile/storage-partition profile) origin k])

(defn remember-navigation
  [profile {:keys [url title]}]
  (update profile :profile/history conj
          {:url url :title title :at (count (:profile/history profile))}))

(defn browser-state
  [{:keys [account profiles active-profile-id] :as opts}]
  {:browser/account account
   :browser/profiles (vec profiles)
   :browser/active-profile-id (or active-profile-id
                                  (some :profile/id profiles)
                                  "default")
   :browser/meta (dissoc opts :account :profiles :active-profile-id)})

(defn active-profile
  [state]
  (first (filter #(= (:profile/id %) (:browser/active-profile-id state))
                 (:browser/profiles state))))
