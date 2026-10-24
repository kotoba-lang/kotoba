(ns engineer-io.stl
  "STL (ASCII + binary) exporter. Restored from kami-eng-io's `stl` module
  (deleted PR #82). A triangle is `{:normal [x y z] :v0 [..] :v1 [..] :v2 [..]}`
  (glam::Vec3 in the original -> plain 3-vectors here)."
  #?(:clj (:import [java.nio ByteBuffer ByteOrder])))

(defn export-ascii
  "Export `triangles` to an ASCII STL string named `name`."
  [name triangles]
  (str "solid " name "\n"
       (apply str
              (for [{[nx ny nz] :normal [v0x v0y v0z] :v0
                     [v1x v1y v1z] :v1 [v2x v2y v2z] :v2} triangles]
                (str "  facet normal " nx " " ny " " nz "\n"
                     "    outer loop\n"
                     "      vertex " v0x " " v0y " " v0z "\n"
                     "      vertex " v1x " " v1y " " v1z "\n"
                     "      vertex " v2x " " v2y " " v2z "\n"
                     "    endloop\n"
                     "  endfacet\n")))
       "endsolid " name "\n"))

#?(:clj
   (defn export-binary
     "Export `triangles` to a binary STL byte array: 80-byte header + u32
     triangle count (LE) + 50 bytes/triangle (12 floats LE + 2 attribute
     bytes). JVM implementation via ByteBuffer."
     [triangles]
     (let [n (count triangles)
           buf (ByteBuffer/allocate (+ 84 (* n 50)))]
       (.order buf ByteOrder/LITTLE_ENDIAN)
       (dotimes [_ 80] (.put buf (byte 0)))
       (.putInt buf n)
       (doseq [{:keys [normal v0 v1 v2]} triangles]
         (doseq [[x y z] [normal v0 v1 v2]]
           (.putFloat buf (float x))
           (.putFloat buf (float y))
           (.putFloat buf (float z)))
         (.put buf (byte 0))
         (.put buf (byte 0)))
       (.array buf))))
