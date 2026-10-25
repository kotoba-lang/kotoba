(ns vultr.instances
  "Vultr compute instance listing/lookup (read-only) -- what is actually
  running and what it costs, for the cost-inventory pass a per-instance
  audit needs before any plan/instance change is decided.

  Deliberately excludes start/stop/reinstall/delete or any other
  instance-lifecycle write: see this repo's ADR-0001 for why those stay a
  human-approved dashboard/API action, not a library call."
  (:require [vultr.client :as client]))

#?(:clj
(defn list-instances
  "Paginated instance listing. `opts` may include :cursor, :per-page,
  :label, :tag, :region, :main-ip to narrow the listing."
  ([] (list-instances {}))
  ([{:keys [cursor per-page label tag region main-ip] :as http-opts}]
   (:instances
    (client/request! "/instances"
                     (assoc (apply dissoc http-opts [:cursor :per-page :label :tag :region :main-ip])
                            :query (cond-> {}
                                     cursor (assoc :cursor cursor)
                                     per-page (assoc :per_page per-page)
                                     label (assoc :label label)
                                     tag (assoc :tag tag)
                                     region (assoc :region region)
                                     main-ip (assoc :main_ip main-ip))))))))

#?(:clj
(defn get-instance
  ([instance-id] (get-instance instance-id {}))
  ([instance-id http-opts]
   (:instance (client/request! (str "/instances/" instance-id) http-opts)))))
