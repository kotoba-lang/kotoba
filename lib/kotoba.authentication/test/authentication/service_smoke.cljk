(ns authentication.service-smoke
  (:require [authentication.identity :as identity]
            [authentication.identity-ports :as ports]
            [authentication.identity-service :as service]))

(def identities (atom {}))
(def users (atom {}))
(def ephemeral (atom {}))

(def identity-store
  (reify ports/IIdentityStore
    (-find-user-by-identity [_ provider subject] (get @identities [provider subject]))
    (-find-user-by-verified-email [_ email]
      (some (fn [[_ v]] (when (= email (:email v)) (:user-id v))) @identities))
    (-create-account! [_ tx]
      (let [user-id (:identity.user/id (first tx))
            profile (second tx)
            tenant-id (:identity.tenant/id (nth tx 2))]
        (swap! identities assoc (identity/identity-key profile)
               {:user-id user-id :email (:identity/email profile)})
        (swap! users assoc user-id {:tenant-id tenant-id})
        (js/Promise.resolve true)))
    (-link-identity! [_ user-id profile _]
      (swap! identities assoc (identity/identity-key profile)
             {:user-id user-id :email (:identity/email profile)})
      (js/Promise.resolve true))
    (-user-view [_ user-id] (get @users user-id))))

(def ephemeral-store
  (reify ports/IEphemeralStore
    (-put-once! [_ key value _]
      (if (contains? @ephemeral key) (js/Promise.resolve false)
        (do (swap! ephemeral assoc key {:version "v1" :value value})
            (js/Promise.resolve "v1"))))
    (-get-value [_ key] (js/Promise.resolve (get @ephemeral key)))
    (-consume! [_ key version]
      (let [record (get @ephemeral key)]
        (if (= version (:version record))
          (do (swap! ephemeral dissoc key) (js/Promise.resolve (:value record)))
          (js/Promise.resolve false))))
    (-delete! [_ key] (swap! ephemeral dissoc key) (js/Promise.resolve true))))

(def app (service/service {:identity-store identity-store
                           :ephemeral-store ephemeral-store
                           :now (constantly 1000)
                           :random-id (let [n (atom 0)] #(swap! n inc))}))

(defn fail! [error] (js/console.error error) (set! (.-exitCode js/process) 1))

(defn ^:export main []
  (let [profile (identity/normalized-profile
                 {:provider :google :provider-subject "g-1"
                  :email "a@example.com" :email-verified? true})]
    (-> (service/begin-oauth! app {:app-id "kotobase" :provider :google
                                   :redirect-uri "https://kotobase.net/auth/oauth/google/callback"
                                   :return-to "/admin"})
        (.then (fn [public]
                 (when (:identity.oauth/pkce-verifier public)
                   (throw (js/Error. "PKCE verifier leaked")))
                 (service/consume-oauth! app (:state public))))
        (.then (fn [transaction]
                 (when-not (:identity.oauth/pkce-verifier transaction)
                   (throw (js/Error. "private OAuth transaction missing")))
                 (service/complete-profile! app {:profile profile
                                                 :application "kotobase"})))
        (.then (fn [result]
                 (when-not (= :create-user (:decision result))
                   (throw (js/Error. "account was not created")))
                 (when-not (:token result) (throw (js/Error. "session missing")))
                 (service/complete-profile! app {:profile profile
                                                 :application "kotobase"})))
        (.then (fn [result]
                 (when-not (= :sign-in (:decision result))
                   (throw (js/Error. "existing identity did not sign in")))
                 (service/rotate-session! app (:token result) {})))
        (.then (fn [rotated]
                 (when-not (:rotated-from-session-id rotated)
                   (throw (js/Error. "rotation lineage missing")))
                 (service/resolve-session! app (:token rotated))))
        (.then (fn [record]
                 (when-not (= "kotobase" (:identity.session/application record))
                   (throw (js/Error. "session audience missing")))
                 (js/console.log "ok - Identity service OAuth, account, sign-in, rotation and session")))
        (.catch fail!))))

(main)
