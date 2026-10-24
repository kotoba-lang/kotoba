(ns kotoba.raytrace.gpu
  "GPU-uploadable layout for the LBVH — the data the WGSL software-BVH
   compute traversal would bind as storage buffers. 1:1 port of kami-rt's
   `gpu.rs`: `GpuNode`/`GpuTri` field order preserved so a host adapter can
   pack these straight into the same `#[repr(C)]` byte layout (std430,
   16-byte rows) the original WGSL `BvhNode`/`Tri` structs expect.

   This whole namespace is pure CPU-side data packing, same as gpu.rs was —
   note the Rust doc comment on gpu.rs already says so: \"Packing is pure +
   unit-tested; the actual buffer upload + dispatch lives in kami-render
   (needs a `wgpu::Device`)\". kami-rt never contained GPU dispatch code, so
   there is nothing adapter-only to leave out of *this* port either. The
   JVM-only `pack-node`/`pack-tri` below add genuine byte-exact ByteBuffer
   packing (mirroring the Rust `bytemuck::Pod` 48-byte layout) purely as a
   host convenience — still no GPU call, just `java.nio.ByteBuffer`, which
   has no cljs equivalent, hence the reader-conditional split.")

(defn node->gpu
  "48-byte-equivalent GpuNode: {:min :left :max :right :start :count}."
  [{:keys [aabb left right start count]}]
  {:min (:min aabb) :left left
   :max (:max aabb) :right right
   :start start :count count})

(defn tri->gpu
  "48-byte-equivalent GpuTri: {:v0 :id :v1 :v2}, positions + stable id, in
   Morton-sorted traversal order (assigned by `to-gpu`)."
  [{:keys [v0 v1 v2 id]}]
  {:v0 v0 :id id :v1 v1 :v2 v2})

(defn to-gpu
  "Pack `bvh` into GPU buffers: the node array (root at 0) and the triangle
   array already in Morton-sorted traversal order, so the WGSL leaf range
   [start,start+count) indexes straight into it."
  [{:keys [nodes tri-order tris]}]
  {:nodes (mapv node->gpu nodes)
   :tris (mapv (fn [i] (tri->gpu (nth tris i))) tri-order)})

#?(:clj
   (defn pack-node
     "Byte-exact 48-byte little-endian packing of a GpuNode, matching the
      Rust `#[repr(C)]` layout: min[3]f32 left:u32 max[3]f32 right:u32
      start:u32 count:u32 _pad[2]u32. JVM-only host convenience."
     [{:keys [min left max right start count]}]
     (let [buf (java.nio.ByteBuffer/allocate 48)]
       (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
       (doseq [c min] (.putFloat buf (float c)))
       (.putInt buf (int left))
       (doseq [c max] (.putFloat buf (float c)))
       (.putInt buf (int right))
       (.putInt buf (int start))
       (.putInt buf (int count))
       (.putInt buf (int 0))
       (.putInt buf (int 0))
       (.array buf))))

#?(:clj
   (defn pack-tri
     "Byte-exact 48-byte little-endian packing of a GpuTri, matching the
      Rust `#[repr(C)]` layout: v0[3]f32 id:u32 v1[3]f32 _p1:u32 v2[3]f32
      _p2:u32. JVM-only host convenience."
     [{:keys [v0 id v1 v2]}]
     (let [buf (java.nio.ByteBuffer/allocate 48)]
       (.order buf java.nio.ByteOrder/LITTLE_ENDIAN)
       (doseq [c v0] (.putFloat buf (float c)))
       (.putInt buf (int id))
       (doseq [c v1] (.putFloat buf (float c)))
       (.putInt buf (int 0))
       (doseq [c v2] (.putFloat buf (float c)))
       (.putInt buf (int 0))
       (.array buf))))
