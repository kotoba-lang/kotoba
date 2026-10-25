# kotoba-lang/org-threejs

Independent ClojureScript bindings for Three.js. This library evolves beside,
not inside, `kami-webgpu` and `kami-webgl`.

- `org-threejs.core`: Scene, camera, WebGLRenderer, lifecycle loop.
- `org-threejs.webgpu`: optional Three.js WebGPURenderer.
- `org-threejs.gltf`: official GLTFLoader as a Promise.
- `org-threejs.vrm`: `@pixiv/three-vrm` loader, update, normalization, and disposal.
- `org-threejs.interop`: EDN vectors/quaternions and Object3D helpers.

Three.js remains the scene graph and renderer authority for consumers of this
library. Kami render-IR, shader graphs, and GPU resources are intentionally not
translated implicitly. Explicit adapters may be added in separate namespaces.

```clojure
(require '[org-threejs.core :as three]
         '[org-threejs.vrm :as vrm])

(let [scene (three/scene)]
  (-> (vrm/load! "/avatar.vrm")
      (.then (fn [avatar]
               (vrm/rotate-vrm0! avatar)
               (.add scene (vrm/scene avatar))))))
```

Call `(vrm/update! avatar (.getDelta clock))` once per frame. On replacement,
remove its scene node and call `(vrm/dispose! avatar)`. `org-threejs` does not
depend on or mutate kami renderer state; an application chooses one rendering
authority for each canvas.

Install and test with `npm install && npm test`.
