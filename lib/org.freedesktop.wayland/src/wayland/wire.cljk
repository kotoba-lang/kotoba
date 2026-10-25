;; Message application against the object table: the protocol's sequencing
;; discipline. wayland core protocol §2.5 (Requests), §2.6 (Events).
(ns wayland.wire
  (:require [wayland.model :as model]
            [wayland.objects :as objects]))

;; wl_display error codes, §2.6
(def display-error-codes
  {:invalid-object 0
   :invalid-method 1
   :no-memory 2
   :implementation 3})

(defn- next-client-id [table]
  (let [n (:next-client-id table)]
    (loop [id n]
      (if (or (contains? (:objects table) id)
              (contains? (:dead-ids table) id))
        (recur (inc id))
        id))))

(defn wire-step
  "Apply one decoded message to the object table.
   msg: {:kind :request|:event :interface name :request/name|:event/name n
         :object-id target :new-ids [iface...]}
   Returns {:table table' :replies [messages]} or throws :wayland-error.

   Rules enforced (all from the core protocol):
   - target id must be live (else :invalid-object)
   - the target's interface must carry the request/event (else :invalid-method)
   - :new-id args allocate fresh ids, never reusing dead ones"
  [table msg]
  (let [id (:object-id msg)
        obj (objects/object-of table id)]
    (cond
      (or (nil? obj) (not= :live (:state obj)))
      (throw (ex-info "request to unknown or dead object"
                      {:phase :wayland/wire-step :error :invalid-object :id id}))
      :else
      (let [iface-name (:interface/name obj)
            iface (model/interface iface-name)
            label (case (:kind msg) :request :request/name :event/name)
            m (first (filter #(= (get msg label) (label %))
                             (case (:kind msg)
                               :request (:requests iface)
                               :event (:events iface))))]
        (when (nil? m)
          (throw (ex-info "interface does not carry this message"
                          {:phase :wayland/wire-step :error :invalid-method
                           :interface iface-name :message msg})))
        (let [new-ifaces (:new-ids msg)
              [table' ids]
              (reduce (fn [[t acc] ifn]
                        (let [nid (next-client-id t)]
                          [(objects/create t nid ifn 1) (conj acc nid)]))
                      [table []]
                      new-ifaces)]
          ;; the target message itself applied: table is state + allocation
          {:table table'
           :allocated ids
           :applied {label (get msg label)
                     :interface iface-name
                     :object-id id}})))))

(defn destroy-step
  "The teardown path: wl_display.delete-id / explicit destroy. Returns the
   updated table; the deleted id never comes back for this connection."
  [table id]
  (let [table' (objects/destroy table id)]
    table'))
