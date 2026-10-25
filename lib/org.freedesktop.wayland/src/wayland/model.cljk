;; Clean-room transcription of the Wayland core protocol's interface surface.
;; Every datom cites its spec section. Names and shapes are transcribed by
;; description from the public wayland.xml (freedesktop, MIT) — no upstream
;; source text is vendored.
(ns wayland.model)

(def core-interfaces
  "The wayland.xml core interfaces this corpus covers, with their requests
   and events. :spec/source is the protocol section the shape comes from."
  [{:interface/name "wl_display"
    :interface/version 1
    :spec/source "wayland core protocol wl_display"
    :requests
    [{:request/name "sync" :request/args [{:arg/name :callback :arg/type :new-id}]
      :request/creates "wl_callback"}
     {:request/name "get_registry" :request/args [{:arg/name :registry :arg/type :new-id}]
      :request/creates "wl_registry"}]
    :events
    [{:event/name "error" :event/args [{:arg/name :object-id :arg/type :object}
                                       {:arg/name :code :arg/type :uint}
                                       {:arg/name :message :arg/type :string}]}
     {:event/name "delete-id" :event/args [{:arg/name :id :arg/type :object}]}]}
   {:interface/name "wl_registry"
    :interface/version 1
    :spec/source "wayland core protocol wl_registry"
    :requests
    [{:request/name "bind" :request/args [{:arg/name :name :arg/type :uint}
                                          {:arg/name :interface :arg/type :string}
                                          {:arg/name :version :arg/type :uint}
                                          {:arg/name :id :arg/type :new-id}]}]
    :events
    [{:event/name "global" :event/args [{:arg/name :name :arg/type :uint}
                                        {:arg/name :interface :arg/type :string}
                                        {:arg/name :version :arg/type :uint}]}
     {:event/name "global_remove" :event/args [{:arg/name :name :arg/type :uint}]}]}
   {:interface/name "wl_callback"
    :interface/version 1
    :spec/source "wayland core protocol wl_callback"
    :requests []
    :events
    [{:event/name "done" :event/args [{:arg/name :callback-data :arg/type :uint}]}]}
   {:interface/name "wl_surface"
    :interface/version 6
    :spec/source "wayland core protocol wl_surface"
    :requests
    [{:request/name "destroy" :request/args []}
     {:request/name "attach" :request/args [{:arg/name :buffer :arg/type :object}
                                            {:arg/name :x :arg/type :int}
                                            {:arg/name :y :arg/type :int}]}
     {:request/name "commit" :request/args []}
     {:request/name "damage" :request/args [{:arg/name :x :arg/type :int}
                                            {:arg/name :y :arg/type :int}
                                            {:arg/name :width :arg/type :int}
                                            {:arg/name :height :arg/type :int}]}]
    :events
    [{:event/name "enter" :event/args [{:arg/name :output :arg/type :object}]}
     {:event/name "leave" :event/args [{:arg/name :output :arg/type :object}]}]}
   {:interface/name "wl_compositor"
    :interface/version 6
    :spec/source "wayland core protocol wl_compositor"
    :requests
    [{:request/name "create_surface" :request/args [{:arg/name :id :arg/type :new-id}]
      :request/creates "wl_surface"}]
    :events []}
   {:interface/name "wl_shm"
    :interface/version 1
    :spec/source "wayland core protocol wl_shm"
    :requests
    [{:request/name "create_pool" :request/args [{:arg/name :id :arg/type :new-id}
                                                 {:arg/name :fd :arg/type :fd}
                                                 {:arg/name :size :arg/type :int}]}]
    :events []}
   {:interface/name "wl_shm_pool"
    :interface/version 1
    :spec/source "wayland core protocol wl_shm_pool"
    :requests
    [{:request/name "create_buffer" :request/args [{:arg/name :id :arg/type :new-id}
                                                   {:arg/name :offset :arg/type :int}
                                                   {:arg/name :width :arg/type :int}
                                                   {:arg/name :height :arg/type :int}
                                                   {:arg/name :stride :arg/type :int}
                                                   {:arg/name :format :arg/type :uint}]}
     {:request/name "destroy" :request/args []}
     {:request/name "resize" :request/args [{:arg/name :size :arg/type :int}]}]
    :events []}
   {:interface/name "wl_buffer"
    :interface/version 1
    :spec/source "wayland core protocol wl_buffer"
    :requests
    [{:request/name "destroy" :request/args []}]
    :events
    [{:event/name "release" :event/args []}]}
   {:interface/name "wl_output"
    :interface/version 4
    :spec/source "wayland core protocol wl_output"
    :requests
    [{:request/name "release" :request/args []}]
    :events
    [{:event/name "geometry" :event/args [{:arg/name :x :arg/type :int}
                                          {:arg/name :y :arg/type :int}
                                          {:arg/name :physical-width :arg/type :int}
                                          {:arg/name :physical-height :arg/type :int}
                                          {:arg/name :subpixel :arg/type :int}
                                          {:arg/name :make :arg/type :string}
                                          {:arg/name :model :arg/type :string}
                                          {:arg/name :transform :arg/type :int}]}
     {:event/name "mode" :event/args [{:arg/name :flags :arg/type :uint}
                                      {:arg/name :width :arg/type :int}
                                      {:arg/name :height :arg/type :int}
                                      {:arg/name :refresh :arg/type :int}]}
     {:event/name "done" :event/args [{:arg/name :name :arg/type :uint}]}
     {:event/name "scale" :event/args [{:arg/name :factor :arg/type :int}]}]}
   {:interface/name "wl_seat"
    :interface/version 8
    :spec/source "wayland core protocol wl_seat"
    :requests
    [{:request/name "get_pointer" :request/args [{:arg/name :id :arg/type :new-id}]
      :request/creates "wl_pointer"}
     {:request/name "get_keyboard" :request/args [{:arg/name :id :arg/type :new-id}]
      :request/creates "wl_keyboard"}
     {:request/name "get_touch" :request/args [{:arg/name :id :arg/type :new-id}]
      :request/creates "wl_touch"}
     {:request/name "release" :request/args []}]
    :events
    [{:event/name "capabilities" :event/args [{:arg/name :capabilities :arg/type :uint}]}
     {:event/name "name" :event/args [{:arg/name :name :arg/type :string}]}]}
   {:interface/name "wl_pointer"
    :interface/version 8
    :spec/source "wayland core protocol wl_pointer"
    :requests
    [{:request/name "set_cursor" :request/args [{:arg/name :serial :arg/type :uint}
                                                {:arg/name :surface :arg/type :object}
                                                {:arg/name :hotspot-x :arg/type :int}
                                                {:arg/name :hotspot-y :arg/type :int}]}
     {:request/name "release" :request/args []}]
    :events
    [{:event/name "enter" :event/args [{:arg/name :serial :arg/type :uint}
                                       {:arg/name :surface :arg/type :object}
                                       {:arg/name :surface-x :arg/type :fixed}
                                       {:arg/name :surface-y :arg/type :fixed}]}
     {:event/name "leave" :event/args [{:arg/name :serial :arg/type :uint}
                                       {:arg/name :surface :arg/type :object}]}
     {:event/name "motion" :event/args [{:arg/name :time :arg/type :uint}
                                        {:arg/name :surface-x :arg/type :fixed}
                                        {:arg/name :surface-y :arg/type :fixed}]}
     {:event/name "button" :event/args [{:arg/name :serial :arg/type :uint}
                                        {:arg/name :time :arg/type :uint}
                                        {:arg/name :button :arg/type :uint}
                                        {:arg/name :state :arg/type :uint}]}
     {:event/name "axis" :event/args [{:arg/name :time :arg/type :uint}
                                      {:arg/name :axis :arg/type :uint}
                                      {:arg/name :value :arg/type :fixed}]}]}
   {:interface/name "wl_keyboard"
    :interface/version 8
    :spec/source "wayland core protocol wl_keyboard"
    :requests
    [{:request/name "release" :request/args []}]
    :events
    [{:event/name "keymap" :event/args [{:arg/name :format :arg/type :uint}
                                        {:arg/name :fd :arg/type :fd}
                                        {:arg/name :size :arg/type :uint}]}
     {:event/name "enter" :event/args [{:arg/name :serial :arg/type :uint}
                                       {:arg/name :surface :arg/type :object}
                                       {:arg/name :keys :arg/type :array}]}
     {:event/name "leave" :event/args [{:arg/name :serial :arg/type :uint}
                                       {:arg/name :surface :arg/type :object}]}
     {:event/name "key" :event/args [{:arg/name :serial :arg/type :uint}
                                     {:arg/name :time :arg/type :uint}
                                     {:arg/name :key :arg/type :uint}
                                     {:arg/name :state :arg/type :uint}]}
     {:event/name "modifiers" :event/args [{:arg/name :serial :arg/type :uint}
                                           {:arg/name :mods-depressed :arg/type :uint}
                                           {:arg/name :mods-latched :arg/type :uint}
                                           {:arg/name :mods-locked :arg/type :uint}
                                           {:arg/name :group :arg/type :uint}]}]}
   {:interface/name "wl_touch"
    :interface/version 8
    :spec/source "wayland core protocol wl_touch"
    :requests
    [{:request/name "release" :request/args []}]
    :events
    [{:event/name "down" :event/args [{:arg/name :serial :arg/type :uint}
                                      {:arg/name :time :arg/type :uint}
                                      {:arg/name :surface :arg/type :object}
                                      {:arg/name :id :arg/type :int}
                                      {:arg/name :x :arg/type :fixed}
                                      {:arg/name :y :arg/type :fixed}]}
     {:event/name "up" :event/args [{:arg/name :serial :arg/type :uint}
                                    {:arg/name :time :arg/type :uint}
                                    {:arg/name :id :arg/type :int}]}
     {:event/name "motion" :event/args [{:arg/name :time :arg/type :uint}
                                        {:arg/name :id :arg/type :int}
                                        {:arg/name :x :arg/type :fixed}
                                        {:arg/name :y :arg/type :fixed}]}
     {:event/name "frame" :event/args []}
     {:event/name "cancel" :event/args []}]}])

(defn interface [name]
  (first (filter #(= name (:interface/name %)) core-interfaces)))

(defn request [iface-name request-name]
  (first (filter #(= request-name (:request/name %))
                 (:requests (interface iface-name)))))

(defn event [iface-name event-name]
  (first (filter #(= event-name (:event/name %))
                 (:events (interface iface-name)))))

(def wire-types
  "wayland core protocol §2.2 — the wire argument types. :fd is the one type
   this corpus models but cannot carry: the descriptor travels out of band."
  #{:int :uint :fixed :string :object :new-id :array :fd})
