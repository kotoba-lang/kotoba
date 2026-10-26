(ns kotoba.gpu-clear-host
  "Track B Phase 0 spike (ADR-2607078000): the browser host for the
  `gpu-clear` capability — the first proof that a compiled `.kotoba` guest
  can drive a real WebGPU canvas clear through a genuinely SYNCHRONOUS
  Wasm host-import, with no JSPI / Atomics.wait bridge.

  The trick (not a workaround — this is how the WebGPU spec is actually
  shaped): `navigator.gpu.requestAdapter`/`adapter.requestDevice` are the
  ONLY async calls in this path, and they run once, host-side, BEFORE the
  guest ever executes (`setupGpuClearHost`, an async function the page
  awaits before instantiating the wasm module). Every per-frame WebGPU call
  after that — `device.createCommandEncoder`, `encoder.beginRenderPass`,
  `pass.end`, `device.queue.submit` — is synchronous per spec, so the
  `gpu_clear` host-import function itself never needs to `await` anything,
  which is the one thing a synchronous Wasm host-import fundamentally
  cannot do.

  Wire format: `gpu_clear(rgba8: i32) -> i32`. `rgba8` is a packed
  0xRRGGBBAA 32-bit color as the raw i32 bit pattern the guest passed
  (`kotoba-core-contracts`' `gpu-clear` capability) — unpacked here via
  `>>> 0` (reinterpret the signed i32 as unsigned) then byte-shifted into
  four 0.0-1.0 WebGPU clear-color channels.")

(defn unpack-rgba8
  "Signed i32 bit pattern -> [r g b a] each 0.0-1.0, per gpu-clear's wire
  format (0xRRGGBBAA packed color). Public (not `defn-`) specifically so
  it's directly unit-testable without a GPU -- see
  test/gpu_clear_host_test.cljs."
  [i32-signed]
  (let [u (unsigned-bit-shift-right i32-signed 0)] ; reinterpret as u32
    [(/ (bit-and (unsigned-bit-shift-right u 24) 0xff) 255.0)
     (/ (bit-and (unsigned-bit-shift-right u 16) 0xff) 255.0)
     (/ (bit-and (unsigned-bit-shift-right u 8) 0xff) 255.0)
     (/ (bit-and u 0xff) 255.0)]))

(defn setup-gpu-clear-host
  "Async, host-side, one-time WebGPU device/context setup — call and
  `.then`/await BEFORE instantiating the guest wasm module. Resolves to a
  JS object `{imports: (fn [] importsObject)}`: `imports()` returns the
  `{\"kotoba\": {gpu_clear: fn}}` WebAssembly import object, whose
  `gpu_clear` is genuinely synchronous (see namespace docstring)."
  [canvas]
  (let [gpu (unchecked-get js/navigator "gpu")]
    (if (nil? gpu)
      (js/Promise.reject (js/Error. "setup-gpu-clear-host: navigator.gpu unavailable (no WebGPU support)"))
      (-> (js-invoke gpu "requestAdapter")
          (.then (fn [adapter]
                   (if (nil? adapter)
                     (throw (js/Error. "setup-gpu-clear-host: requestAdapter returned null"))
                     (js-invoke adapter "requestDevice"))))
          (.then (fn [device]
                   (let [ctx (js-invoke canvas "getContext" "webgpu")
                         format (js-invoke gpu "getPreferredCanvasFormat")
                         queue (unchecked-get device "queue")]
                     (js-invoke ctx "configure" #js {"device" device "format" format "alphaMode" "opaque"})
                     #js {"imports"
                          (fn []
                            #js {"kotoba"
                                 #js {"gpu_clear"
                                      (fn [rgba8]
                                        (let [[r g b a] (unpack-rgba8 rgba8)
                                              texture (js-invoke ctx "getCurrentTexture")
                                              view (js-invoke texture "createView")
                                              encoder (js-invoke device "createCommandEncoder")
                                              pass (js-invoke encoder "beginRenderPass"
                                                    #js {"colorAttachments"
                                                         #js [#js {"view" view
                                                                   "loadOp" "clear"
                                                                   "storeOp" "store"
                                                                   "clearValue" #js {"r" r "g" g "b" b "a" a}}]})]
                                          (js-invoke pass "end")
                                          (js-invoke queue "submit" #js [(js-invoke encoder "finish")])
                                          0))}})})))))))
