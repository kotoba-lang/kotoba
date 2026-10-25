(ns character.export
  "GLB export — CharacterMesh -> binary glTF 2.0 (.glb), represented as
  a plain byte vector (see `character.bin`). Restored from the legacy
  kami-engine/kami-character Rust crate's `export.rs` (deleted in
  kotoba-lang/kami-engine PR #82) as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root)."
  (:require [character.material :as material]
            [character.bin :as bin]))

(def material-order [:skin :eye-white :iris :pupil :lip :eyebrow :hair :clothing :eyelash])

(defn- pad4 [v]
  (loop [v v] (if (zero? (mod (count v) 4)) v (recur (conj v 0)))))

(defn- group-parts-by-material
  "Group mesh parts by material, offsetting indices so each group is a
  contiguous vertex buffer. Returns `{material {:vertices [...]
  :indices [...]}}`."
  [parts]
  (reduce
   (fn [groups {:keys [material vertices indices]}]
     (let [existing (get groups material {:vertices [] :indices []})
           offset (count (:vertices existing))]
       (assoc groups material
              {:vertices (into (:vertices existing) vertices)
               :indices (into (:indices existing) (map #(+ % offset) indices))})))
   {} parts))

(defn export-glb
  "Export CharacterMesh to GLB binary (byte vector)."
  [{:keys [parts]} def]
  (let [groups (group-parts-by-material parts)
        {:keys [skin eyes mouth hair clothing]} def
        state
        (reduce
         (fn [{:keys [buf buffer-views accessors primitives materials-json] :as st} mid]
           (let [{:keys [vertices indices]} (get groups mid)]
             (if (empty? vertices)
               st
               (let [mat-idx (count materials-json)
                     pbr (material/for-part mid skin eyes mouth hair clothing)
                     mat-json (str "{\"name\":\"" (:name pbr) "\",\"pbrMetallicRoughness\":{"
                                   "\"baseColorFactor\":[" (apply str (interpose "," (:base-color pbr))) "],"
                                   "\"metallicFactor\":" (:metallic pbr) ",\"roughnessFactor\":" (:roughness pbr) "},"
                                   "\"doubleSided\":true}")
                     v-min (reduce (fn [[mx my mz] {:keys [position]}]
                                     (let [[x y z] position] [(min mx x) (min my y) (min mz z)]))
                                   [Double/MAX_VALUE Double/MAX_VALUE Double/MAX_VALUE] vertices)
                     v-max (reduce (fn [[mx my mz] {:keys [position]}]
                                     (let [[x y z] position] [(max mx x) (max my y) (max mz z)]))
                                   [(- Double/MAX_VALUE) (- Double/MAX_VALUE) (- Double/MAX_VALUE)] vertices)
                     vdata (reduce (fn [vd {:keys [position normal uv]}]
                                     (let [[px py pz] position [nx ny nz] normal [u v] uv]
                                       (-> vd (bin/write-f32-le px) (bin/write-f32-le py) (bin/write-f32-le pz)
                                           (bin/write-f32-le nx) (bin/write-f32-le ny) (bin/write-f32-le nz)
                                           (bin/write-f32-le u) (bin/write-f32-le v))))
                                   [] vertices)
                     vdata (pad4 vdata)
                     v-bv (count buffer-views)
                     v-off (count buf)
                     buf (into buf vdata)
                     buffer-views (conj buffer-views
                                        (str "{\"buffer\":0,\"byteOffset\":" v-off ",\"byteLength\":" (count vdata)
                                             ",\"byteStride\":32,\"target\":34962}"))
                     idata (reduce (fn [id i] (bin/write-u32-le id i)) [] indices)
                     idata-padded (pad4 idata)
                     i-bv (count buffer-views)
                     i-off (count buf)
                     buf (into buf idata-padded)
                     buffer-views (conj buffer-views
                                        (str "{\"buffer\":0,\"byteOffset\":" i-off ",\"byteLength\":" (count idata)
                                             ",\"target\":34963}"))
                     pos-a (count accessors)
                     accessors (conj accessors
                                     (str "{\"bufferView\":" v-bv ",\"componentType\":5126,\"count\":" (count vertices)
                                          ",\"type\":\"VEC3\",\"byteOffset\":0,\"min\":[" (apply str (interpose "," v-min))
                                          "],\"max\":[" (apply str (interpose "," v-max)) "]}"))
                     norm-a (count accessors)
                     accessors (conj accessors
                                     (str "{\"bufferView\":" v-bv ",\"componentType\":5126,\"count\":" (count vertices)
                                          ",\"type\":\"VEC3\",\"byteOffset\":12}"))
                     uv-a (count accessors)
                     accessors (conj accessors
                                     (str "{\"bufferView\":" v-bv ",\"componentType\":5126,\"count\":" (count vertices)
                                          ",\"type\":\"VEC2\",\"byteOffset\":24}"))
                     idx-a (count accessors)
                     accessors (conj accessors
                                     (str "{\"bufferView\":" i-bv ",\"componentType\":5125,\"count\":" (count indices)
                                          ",\"type\":\"SCALAR\"}"))
                     primitives (conj primitives
                                       (str "{\"attributes\":{\"POSITION\":" pos-a ",\"NORMAL\":" norm-a
                                            ",\"TEXCOORD_0\":" uv-a "},\"indices\":" idx-a ",\"material\":" mat-idx "}"))]
                 {:buf buf :buffer-views buffer-views :accessors accessors
                  :primitives primitives :materials-json (conj materials-json mat-json)}))))
         {:buf [] :buffer-views [] :accessors [] :primitives [] :materials-json []}
         material-order)
        {:keys [buf buffer-views accessors primitives materials-json]} state
        json (str "{\"asset\":{\"version\":\"2.0\",\"generator\":\"kami-character\"},\"scene\":0,"
                  "\"scenes\":[{\"nodes\":[0]}],\"nodes\":[{\"mesh\":0,\"name\":\"character\"}],"
                  "\"meshes\":[{\"primitives\":[" (apply str (interpose "," primitives)) "]}],"
                  "\"accessors\":[" (apply str (interpose "," accessors)) "],"
                  "\"bufferViews\":[" (apply str (interpose "," buffer-views)) "],"
                  "\"materials\":[" (apply str (interpose "," materials-json)) "],"
                  "\"buffers\":[{\"byteLength\":" (count buf) "}]}")
        json-bytes (bin/str->bytes json)
        json-bytes (loop [b json-bytes] (if (zero? (mod (count b) 4)) b (recur (conj b 32))))
        glb-len (+ 12 8 (count json-bytes) 8 (count buf))
        out []
        out (-> out
                (bin/write-u32-le 0x46546C67) ; magic "glTF"
                (bin/write-u32-le 2)
                (bin/write-u32-le glb-len)
                (bin/write-u32-le (count json-bytes))
                (bin/write-u32-le 0x4E4F534A) ; "JSON"
                (bin/write-bytes json-bytes)
                (bin/write-u32-le (count buf))
                (bin/write-u32-le 0x004E4942) ; "BIN\0"
                (bin/write-bytes buf))]
    out))
