(ns kami.backend.browser
  "Browser KAMI GPU host adapter.

  CLJS owns the concrete `KamiCljHost` WASM/WebGPU interop. CLJ keeps an explicit
  platform-bound stub so the namespace remains requireable in JVM audits without
  pretending a GPU/browser host exists there."
  (:require [kami.gpu :as gpu]
            #?(:cljs [cljs.core.async :refer [go]])))

#?(:cljs
   (do
     (defn- ->u8 [buffer]
       (js/Uint8Array. (into-array buffer)))

     (defn- ->f32 [xs]
       (js/Float32Array. (into-array xs)))

     (defn- ->u32 [xs]
       (js/Uint32Array. (into-array xs)))

     (defrecord BrowserBackend [host]
       gpu/IGpuBackend
       (register-mesh! [_ id vertices indices]
         (.register_mesh ^js host id (->f32 vertices) (->u32 indices)))
       (register-material! [_ id params]
         (.register_material ^js host id (->f32 (or params []))))
       (register-shader! [_ id wgsl layout]
         (.register_shader ^js host id wgsl (or layout "")))
       (register-texture! [_ id width height rgba]
         (.register_texture ^js host id width height (->u8 rgba)))
       (register-text! [_ id text size]
         (.register_text ^js host id text size))
       (submit-frame! [_ packed]
         (.submit_frame ^js host
                        (js/JSON.stringify (clj->js (:meta packed)))
                        (->u8 (:buffer packed))))
       (resize! [_ w h]
         (.resize ^js host w h)))

     (defn make
       "Create a browser GPU backend bound to canvas id `:canvas`.

       Returns a channel that yields the backend once `KamiCljHost.create`
       resolves. `:host-ctor` lets callers inject the wasm class; by default the
       adapter uses global `js/KamiCljHost`."
       [{:keys [canvas host-ctor]}]
       (go
         (let [el (.getElementById js/document canvas)
               ctor (or host-ctor js/KamiCljHost)
               host (js/await (.create ^js ctor el))]
           (->BrowserBackend host)))))

   :clj
   (defn make [opts]
     (throw (ex-info "kami.backend.browser/make requires a browser ClojureScript host"
                     {:opts (keys opts)}))))
