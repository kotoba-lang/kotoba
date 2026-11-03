(ns kami.eizo.grade.lut
  "Adobe/Iridas `.cube` 3D LUT format: parser + trilinear sampling.
   Format: an optional `TITLE \"...\"` line, `LUT_3D_SIZE N`, optional
   `DOMAIN_MIN`/`DOMAIN_MAX` lines (defaulted to 0/1 here — a real .cube
   can remap domain, but v0 assumes the common [0,1] case and documents
   the limitation), then N^3 lines of `r g b` floats in the fixed
   iteration order defined by the spec: red fastest, then green, then
   blue (i.e. index = r + g*N + b*N*N)."
  (:refer-clojure :exclude [parse-double parse-long])
  (:require [kotoba.lang.text :as str]
            [kami.eizo.grade.mathutil :as m]))

(defn- parse-double [s]
  #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s)))

(defn- parse-long [s]
  #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10)))

(defn parse-cube
  "Parse `.cube` file text into {:size N :data (vector of [r g b] in
   spec order)}. Ignores comment lines (`#...`) and blank lines."
  [text]
  (let [lines (->> (str/split-lines text)
                    (map str/trim)
                    (remove #(or (str/blank? %) (str/starts-with? % "#"))))
        size-line (first (filter #(str/starts-with? % "LUT_3D_SIZE") lines))
        size (parse-long (str/trim (subs size-line (count "LUT_3D_SIZE"))))
        data-lines (remove #(re-find #"^[A-Z_]" %) lines)
        data (mapv (fn [l]
                     (mapv parse-double (str/split l #"\s+")))
                   data-lines)]
    {:size size :data (vec data)}))

(defn- at [{:keys [size data]} r g b]
  (nth data (+ r (* g size) (* b size size))))

(defn- clamp-idx [i size] (max 0 (min (dec size) (int i))))

(defn sample-lut
  "Trilinear sample of `lut` at normalized [r g b] in [0,1]. Values
   outside [0,1] clamp to the LUT's edge (matches real LUT application)."
  [{:keys [size] :as lut} [r g b]]
  (let [scale (dec size)
        fr (* (max 0.0 (min 1.0 (double r))) scale)
        fg (* (max 0.0 (min 1.0 (double g))) scale)
        fb (* (max 0.0 (min 1.0 (double b))) scale)
        r0 (clamp-idx (m/floor fr) size) r1 (clamp-idx (inc r0) size)
        g0 (clamp-idx (m/floor fg) size) g1 (clamp-idx (inc g0) size)
        b0 (clamp-idx (m/floor fb) size) b1 (clamp-idx (inc b0) size)
        tr (- fr r0) tg (- fg g0) tb (- fb b0)
        lerp (fn [a b t] (+ a (* t (- b a))))
        lerp3 (fn [a b t] (mapv (fn [ai bi] (lerp ai bi t)) a b))
        c000 (at lut r0 g0 b0) c100 (at lut r1 g0 b0)
        c010 (at lut r0 g1 b0) c110 (at lut r1 g1 b0)
        c001 (at lut r0 g0 b1) c101 (at lut r1 g0 b1)
        c011 (at lut r0 g1 b1) c111 (at lut r1 g1 b1)
        c00 (lerp3 c000 c100 tr) c10 (lerp3 c010 c110 tr)
        c01 (lerp3 c001 c101 tr) c11 (lerp3 c011 c111 tr)
        c0 (lerp3 c00 c10 tg) c1 (lerp3 c01 c11 tg)]
    (lerp3 c0 c1 tb)))
