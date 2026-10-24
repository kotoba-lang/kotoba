(ns num.arrow-simd
  "Explicit Wasm SIMD over a borrowed Arrow float32 values buffer.

  The WebAssembly memory is the owned ingress allocation. Arrow parses a view
  of that memory and returns a values slice with the same backing. This adapter
  passes only its byte offset and length to the SIMD kernel: there is no
  Arrow-to-SIMD materialization."
  (:require [num.arrow-gpu :as arrow-buffer]))

(defn- fail [message data]
  (throw (ex-info message (assoc data :type :num/arrow-simd-refused))))

(defn scale-f32x4!
  "Scale an Arrow float32 column in place with the Wasm `f32x4` kernel.

  Returns the borrowed Float32Array. Its backing must be the module's exported
  memory, making an accidental intermediate allocation a hard failure."
  [wasm-instance column-view scale]
  (let [cpu-view (arrow-buffer/borrow-f32-column column-view)
        exports (.-exports wasm-instance)
        memory (.-memory exports)
        kernel (.-scale_f32x4 exports)]
    (when-not (instance? js/WebAssembly.Memory memory)
      (fail "SIMD module does not export WebAssembly memory" {}))
    (when-not (fn? kernel)
      (fail "SIMD module does not export scale_f32x4" {}))
    (when-not (identical? (.-buffer memory) (.-buffer cpu-view))
      (fail "Arrow values do not borrow the SIMD module memory"
            {:arrow-byte-offset (.-byteOffset cpu-view)
             :arrow-byte-length (.-byteLength cpu-view)}))
    (kernel (.-byteOffset cpu-view) (.-length cpu-view) scale)
    cpu-view))
