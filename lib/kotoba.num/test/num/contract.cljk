(ns num.contract
  "The backend CONTRACT — one suite, run against any IBackend. The CPU reference
  is the oracle; a live WGSL / CUDA / Metal / ROCm backend is correct iff it
  passes this same suite to f32 tolerance (`WgslBackend ≡ CpuBackend`), exactly as
  the actors assert `MemStore ≡ DatomicStore`. `check` is `(fn [pass? label])`."
  (:require [num.array :as arr]
            [num.core :as nm]
            [num.sparse :as sp]))

(defn approx?
  "Scalar tolerance check (~1e-5). Public: reused by num.deno-gpu-verify (ADR-2607051400
  §Phase 2) so the live-GPU-vs-CPU-oracle cross-check uses the identical tolerance."
  [a b] (< (Math/abs (- (double a) (double b))) 1e-5))

(defn approx-vec?
  "Elementwise tolerance check. Public: see `approx?`."
  [u v] (and (= (count u) (count v)) (every? true? (map approx? u v))))

(defn verify
  "Exercise every op against `backend`, reporting via `(check pass? label)`."
  [backend check]
  ;; level-1
  (let [x (arr/from-vec backend [1 2 3 4] [4])
        y (arr/from-vec backend [10 20 30 40] [4])]
    (check (approx? 300.0 (nm/dot x y)) "dot")
    (check (approx? 5.0 (nm/nrm2 (arr/from-vec backend [3 4] [2]))) "nrm2")
    (check (approx-vec? [12 24 36 48] (arr/->vec (nm/axpy! 2.0 x y))) "axpy!")
    (check (approx-vec? [2 4 6 8] (arr/->vec (nm/scal! 2.0 (arr/from-vec backend [1 2 3 4] [4])))) "scal!"))
  ;; elementwise + reductions
  (let [a (arr/from-vec backend [1 2 3 4] [4])
        b (arr/from-vec backend [4 3 2 1] [4])]
    (check (approx-vec? [5 5 5 5] (arr/->vec (nm/add a b))) "add")
    (check (approx-vec? [-3 -1 1 3] (arr/->vec (nm/sub a b))) "sub")
    (check (approx-vec? [4 6 6 4] (arr/->vec (nm/mul a b))) "mul")
    (check (approx-vec? [0.25 (/ 2.0 3) 1.5 4] (arr/->vec (nm/div a b))) "div")
    (check (approx? 10.0 (nm/sum a)) "sum")
    (check (approx? 4.0 (nm/amax a)) "amax")
    (check (approx? 1.0 (nm/amin a)) "amin"))
  ;; unary elementwise
  (let [c (arr/from-vec backend [0 1 -2 3] [4])]
    (check (approx-vec? [1.0 (Math/exp 1) (Math/exp -2) (Math/exp 3)]
                        (arr/->vec (nm/exp c))) "exp")
    (check (approx-vec? [0 1 0 3] (arr/->vec (nm/relu c))) "relu")
    (check (approx-vec? [0 -1 2 -3] (arr/->vec (nm/neg c))) "neg")
    (check (approx-vec? (mapv #(/ % (+ 1.0 (Math/exp (- %)))) [0 1 -2 3])
                        (arr/->vec (nm/silu c))) "silu"))
  ;; level-2 / level-3
  (let [A (arr/from-vec backend [1 2 3 4] [2 2])          ; [[1 2][3 4]]
        x (arr/from-vec backend [1 1] [2])
        B (arr/from-vec backend [5 6 7 8] [2 2])]         ; [[5 6][7 8]]
    (check (approx-vec? [3 7] (arr/->vec (nm/matvec A x))) "matvec")
    ;; [[1 2][3 4]]·[[5 6][7 8]] = [[19 22][43 50]]
    (check (approx-vec? [19 22 43 50] (arr/->vec (nm/matmul A B))) "matmul"))
  ;; sparse
  (let [csr (sp/dense->csr 2 3 [1 0 2  0 3 0])            ; [[1 0 2][0 3 0]]
        x (arr/from-vec backend [1 1 1] [3])]
    (check (approx-vec? [3 3] (arr/->vec (nm/spmv backend csr x))) "spmv")))
